import discord
from discord.ext import  tasks,commands

from pathlib import Path

from yfpy import utils
from yfpy.models import League, Transaction

from datetime import datetime
import utility
import asyncio

import json

import logging
logger = logging.getLogger(__name__)


class TransactionsLog(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready = False

        self.emb_color = self.bot.state.emb_color

        self._transactions_filename = 'transactions.json'
        self._private_filename = 'private.json'

        self.transactions:dict = None


    ###################################################
    # Check Transactions for new Entries      
    ###################################################
   
    async def trade_transaction_string(self, transaction_data:dict):
        string = (
            f'{'Source Team:':<20}{transaction_data.get('source_team_name')}\n' 
            f'{'Source Type:':<20}{transaction_data.get('source_type')}\n' 
            f'{'Destination Team:':<20}{transaction_data.get('destination_team_name')}\n'
            f'{'Destination Type:':<20}{transaction_data.get('destination_type')}\n'
            f'{'Type:':<20}{transaction_data.get('type')}'
            )
        return string

    
    async def drop_transaction_string(self,transaction_data:dict):
        string = (
            f'{'Source Team:':<20}{transaction_data.get('source_team_name')}\n' 
            f'{'Source Type:':<20}{transaction_data.get('source_type')}\n'  
            f'{'Destination Type:':<20}{transaction_data.get('destination_type')}\n'
            f'{'Type:':<20}{transaction_data.get('type')}'
            )
        return string


    async def add_transaction_string(self,transaction_data:dict):
        string = (
            f'{'Destination Team:':<20}{transaction_data.get('destination_team_name')}\n' 
            f'{'Source Type:':<20}{transaction_data.get('source_type')}\n'
            f'{'Destination Type:':<20}{transaction_data.get('destination_type')}\n'
            f'{'Type:':<20}{transaction_data.get('type')}'
            )
        return string


    async def compose_player_string(self, player:dict, embed:discord.Embed):
        """Compose a string for the player."""
        transaction_data:dict = player.get('transaction_data')

        name_info:dict = player.get('name')
        name = name_info.get('full')
        
        player_string = (f'{'Position Type:':<20}{player.get('position_type')}\n'
            f'{'Player ID:':<20}{player.get('player_id')}\n')
        #embed.add_field(name=name,value=f'```{player_string}```', inline=False)

        # collect appropriate information for string
        transaction_data_string = ''
        if transaction_data:
            if transaction_data.get('type') == 'trade':
                transaction_data_string = await self.trade_transaction_string(transaction_data)
            elif transaction_data.get('type') == 'add':
                transaction_data_string = await self.add_transaction_string(transaction_data) 
            elif transaction_data.get('type') == 'drop':
                transaction_data_string = await self.drop_transaction_string(transaction_data)
            else:
                logger.warning('[TransactionLog][compose_player_string] - Error: Unhandled transaction type.')

        # compose transaction field        
        embed.add_field(name=f'{name}', value=f"```{player_string}{transaction_data_string}```", inline=False)
     

    async def parse_players(self,players:list[dict] | dict, embed:discord.Embed):
        try:
            if isinstance(players,dict):
                await self.compose_player_string(players.get('player'),embed)

            else:
                for player in players:
                    await self.compose_player_string(player.get('player'),embed)
        except Exception as e:
            logger.error(f'[TransactionLog] - Error: {e}')
            

    async def post_transaction(self, transaction_id:str):
        """Post a transaction to the transactions channel."""
        logger.info('[TransactionLog] - Posting Transaction')
        async with self.bot.state.transactions_channel_id_lock:
            local_id = self.bot.state.transactions_channel_id
        
        channel = self.bot.get_channel(int(local_id))
        if channel is None:
            channel = await self.bot.fetch_channel(int(local_id))

        logger.info(f'[TransactionLog] - send channel : {channel}')

        # Unpack transaction
        transaction:dict = await self.unpack_transaction(str(transaction_id))
        if transaction is None:
            logger.warning(f'[TransactionLog] - Transaction not found: {transaction_id}')
            return
        
        
        current_date = datetime.fromtimestamp(transaction.get('timestamp'))
        description_string =( f'{'Type:':<20}{transaction.get('type')} \n'
                f'{'Status:':<20}{transaction.get('status')}' ) 
        embed = discord.Embed(title = f'Transaction ID: {transaction.get('transaction_id')}', url='', 
                              description = f'```{description_string}```', timestamp=current_date,color = self.emb_color)

        if transaction.get('type') == 'commish':
            logger.info('[TransactionLog] - Commissioner Transaction')
        else:
            logger.info('[TransactionLog] - Player Transaction')
            await self.parse_players(transaction.get('players'),embed)

        await channel.send(embed = embed)


    async def add_new_transactions(self,transaction):
        """Check if a transaction is new."""
        if not self.transactions or str(transaction.transaction_id) not in self.transactions:
            # Convert to dict entry with transaction_id as key
            dict_entry = utils.jsonify_data(transaction)

            # Add transaction to self.transactions
            self.transactions[str(transaction.transaction_id)] = dict_entry
            logger.info(f'[TransactionsLog] - New transaction found: {transaction.transaction_id}')

            # Post transaction to channel
            await self.post_transaction(transaction.transaction_id)
            
            return False
        else:
            logger.info(f'[TransactionsLog] - Transaction already exists: {transaction.transaction_id}')
            return True


    async def update_transactions(self):
        """Get recent transactions."""
        start = 0
        found = False
        while found is False:
            async with self.bot.state.fantasy_query_lock:
                league:League = self.bot.state.fantasy_query.check_recent_transactions(start=start)['league']
            transactions:Transaction = league.transactions

            if league is None or transactions is None:
                logger.info('[TransactionsLog] - No transactions found')
                break

            for transaction in transactions:
                found = await self.add_new_transactions(transaction)
                
                if int(transaction.transaction_id) <= 1:
                    found = True
                
                if found:
                    break

            # Increment start by 25
            start += 25

            # Pace api calls
            await asyncio.sleep(10)
            
        # Update transactions .json file
        await self.bot.state.persistent_manager.write_json(filename=self._transactions_filename, data=self.transactions)
        #utility.store_transactions(self.transactions, self.filename)


    async def unpack_transaction(self, transaction_id:str):
        """Unpack a transaction"""
        if transaction_id in self.transactions:
            try:
                transactions_string = utils.unpack_data(self.transactions[transaction_id], parent_class=Transaction)
                transaction_dict = json.loads(transactions_string)
                return transaction_dict
            except Exception as e:
                logger.error(f'[TransactionsLog] - Error unpacking transaction: {e}')
                return None
        else:
            return None
        

    async def verify_transactions_channel(self):
        async with self.bot.state.transactions_channel_id_lock:
            self.bot.state.transactions_channel_id = self.bot.state.transactions_channel_id or await self.setup_Transactions()

            if self.bot.state.transactions_channel_id is None:
                logger.warning('[TransactionsLog] - No Transactions channel ID found within private_data.json')
                return False
            else:
                return True


    @tasks.loop(minutes=10)
    async def check_transactions(self):
        """Check for new transactions every 10 minutes."""
        channel_set = await self.verify_transactions_channel()
        if not channel_set:
            logger.warning('[TransactionsLog][Check_Transactions] - Transactions channel not set')
            return
        
        # Load transactions from file
        self.transactions = await self.bot.state.persistent_manager.load_json(filename=self._transactions_filename)

        # Get check_if_new_entry
        await self.update_transactions()
        logger.info('[TransactionsLog] - .. Done')


    ###################################################
    # Loop Error Handling          
    ###################################################

    @check_transactions.error
    async def check_transactions_error(self,error):
        logger.error(f'[TransactionsLog][check_transactions] - Error: {error} \n')


    ###################################################
    # Setup          
    ###################################################
    
    async def setup_Transactions(self):
        # load private data 
        data = await self.bot.state.discord_auth_manager.load_json(filename = self._private_filename)
        #utility.get_private_discord_data_async()

        raw_data = data.get('transactions_channel_id')
        if raw_data is None:
            logger.warning('[TransactionLog] - No Transactions channel ID found within private_data.json')
            return None
        else:
            try:
                int(raw_data)
            except ValueError:
                logger.error('[TransactionsLog] - Invalid Transactions channel ID')
                return None
        return int(data.get('transactions_channel_id'))
    

    async def wait_for_fantasy(self):
        while not self._ready:
            async with self.bot.state.fantasy_query_lock:
                fantasy_query = self.bot.state.fantasy_query
            if fantasy_query is not None:
                self._ready = True
            else:
                await asyncio.sleep(1)
        

    @commands.Cog.listener()
    async def on_ready(self):
        await self.wait_for_fantasy()
        self.check_transactions.start()
        logger.info('[TransactionsLog] - Ready')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        self.check_transactions.cancel()
        logger.info('[TransactionsLog] - Cog Unload')



async def setup(bot):
    await bot.add_cog(TransactionsLog(bot))