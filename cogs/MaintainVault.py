import discord
from discord import app_commands
from discord.ext import tasks,commands
from typing import Any

import os
import asyncio

from collections import deque
from pathlib import Path
from bet_vault.vault import Vault
from datetime import datetime, timedelta, date

from yfpy.models import GameWeek, Matchup

from cogs_helpers import FantasyHelper
import utility

import logging
logger = logging.getLogger(__name__)


class MaintainVault(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.bot_name = bot.user.name
        
        self.gold_color = discord.Color.gold()
        self.pink_color = discord.Color.pink()
        self.loser_role_name = 'King Chump'

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready_to_init = False
        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        # file managers
        self._persistent_manager = self.bot.state.persistent_manager
        self._vault_manager = self.bot.state.vault_manager

        # vault 
        self._vault:Vault = None
        self._initial_bank_funds = 100
        self._default_wager_amount = 10
        self._default_wager_bonus = 0

        # files
        self._members_filename = 'members.json'
        self._vault_accounts_filename = 'vault_accounts.json'
        self._vault_slap_contracts_filename = 'vault_slap_contracts.json'
        self._vault_wager_contracts_filename = 'vault_wager_contracts.json'



    ###################################################
    # Create Role 
    ###################################################

    async def create_role(self, guild:discord.guild, role_name:str, color:discord.Color):
        role = await guild.create_role(
            name=role_name,
            colour=discord.Color.from_rgb(100, 200, 255),
            hoist=True,
            mentionable=True,
            reason='Created a role for FantasyBot',
        )

        bot_member = guild.me
        bot_top_role = max(bot_member.roles, key=lambda r: r.position)
        new_position = bot_top_role.position - 1

        await guild.edit_role_positions(positions={role: new_position})


    ###################################################
    # Assign Role 
    ###################################################

    async def get_slaps_channel(self):
        async with self.bot.state.slaps_channel_id_lock:
            local_id = self.bot.state.slaps_channel_id

        if local_id is None:
            logger.warning('[SlapChallenge] - Channel not set.')
            return None
       
        # get channel for message and guild.roles
        channel = self.bot.get_channel(int(local_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(local_id))
            except Exception as e:
                logger.error(f'[FantasyQuery][get_slaps_channel] - Error: {e}')
                return None
        return channel


    async def get_member_by_id(self,guild: discord.Guild, user_id: int):
        member = guild.get_member(user_id)

        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except Exception as e:
                logger.error(f'[MaintainVault][get_member_by_id] - Error:{e}')
                return None
        return member


    async def assign_role(self, discord_member_id:int, role_name:str):
        channel = await self.get_slaps_channel()
        if channel is None:
            logger.warning('[MaintainVault][assign_role] - Unable to retrive Slaps Channel.')
            return

        guild = channel.guild
        roles = guild.roles
        role = discord.utils.get(roles, name = role_name)
        if role is None:
            await self.create_role(guild, self.loser_role_name, self.gold_color)
        
        member = await self.get_member_by_id(guild, int(discord_member_id))
        if member is None:
            logger.warning('[MaintainVault][assign_role] - Failed to fetch discord member from discord_id.')
            return

        try:
            await member.add_roles(role)
            logger.info(f'[MaintainVault] - {member.display_name} assigned {role_name}')
        except discord.Forbidden:
            logger.error(f'[MaintainVault] - Do not have the necessary permissions to assign {role_name} role')
        except discord.HTTPException as e:
            logger.error(f'[MaintainVault] - Failed to assign {role_name} role. Error: {e}')


    async def remove_role_members(self, role_name:str):
        channel = await self.get_slaps_channel()

        if channel is None:
            logger.warning('[MaintainVault] - Unable to retrive Slaps Channel.')
            return
        
        guild = channel.guild
        role = discord.utils.get(guild.roles, name = role_name)
        if role is None:
            logger.warning('[MaintainVault] - Role doesn\'t exist.')
            return

        if role is not None:
            for member in role.members:
                await member.remove_roles(role)
        

    ###################################################
    # Format matchup dict
    ###################################################

    async def format_matchups_to_dict(self, matchups_list:list[Matchup]):
        data_dict = {}
        try:
            for matchup in matchups_list:
                if len(matchup.teams) > 1:
                    entry_1 = {}
                    team_1_id = str(matchup.teams[0].team_id)
                    entry_1['team_id'] =  team_1_id
                    entry_1['team_opponent_id'] = str(matchup.teams[1].team_id)
                    entry_1['total_points'] = round(matchup.teams[0].team_points.total, 2)
                    entry_1['week_start'] = matchup.week_start
                    entry_1['week_end'] = matchup.week_end
                    entry_1['winner'] = matchup.winner_team_key
                    entry_1['week'] = matchup.week
                    data_dict[team_1_id] = entry_1

                    entry_2 = {}
                    team_2_id = str(matchup.teams[1].team_id)
                    entry_2['team_id'] = team_2_id
                    entry_2['team_opponent_id'] = str(matchup.teams[0].team_id)
                    entry_2['total_points'] = round(matchup.teams[1].team_points.total, 2)
                    entry_2['week_start'] = matchup.week_start
                    entry_2['week_end'] = matchup.week_end
                    entry_2['winner'] = matchup.winner_team_key
                    entry_2['week'] = matchup.week
                    data_dict[team_2_id] = entry_2
                else:
                    entry = {}
                    team_1_id = str(matchup.teams[0].team_id)
                    entry['team_id'] =  team_1_id
                    entry['team_opponent_id'] = None
                    entry['total_points'] = round(matchup.teams[0].team_points, 2)
                    entry['week_start'] = matchup.week_start
                    entry['week_end'] = matchup.week_end
                    entry['winner'] = matchup.winner_team_key
                    entry['week'] = matchup.week
                    data_dict[team_1_id] = entry

            return data_dict
        except Exception as e:
            raise ValueError(f"Failed to construct data from Matchup_list. \n Error: {e}")


    async def get_matchup_data(self, week) -> dict[str:int]:
        async with self.bot.state.fantasy_query_lock:
            matchups_list:list[Matchup] = self.bot.state.fantasy_query.get_scoreboard(week).matchups
        
        if matchups_list is None:
            raise ValueError('match_ups list is None.')
        return await self.format_matchups_to_dict(matchups_list)


    ###################################################
    # Execute Contracts 
    ###################################################

    async def execute_wager(self, contract:Vault.GroupWagerContract, week_dict:dict[str:Any]):
        if await contract.empty():
            logger.info('[MaintainVault] - No Predictions to account to parse.')
            contract.executed = True
            return
        logger.info('[MaintainVault][execute_wager] - Evaluating Wager Winner.')


        # data
        matchup_1_dict = week_dict.get(contract.team_1_id)
        matchup_2_dict = week_dict.get(contract.team_2_id)

        # points
        team_1_total_points = matchup_1_dict.get('total_points')
        team_2_total_points = matchup_2_dict.get('total_points')
        total_points = team_1_total_points + team_2_total_points

        # winner
        if team_1_total_points > team_2_total_points:
            winner_id = contract.team_1_id
        elif team_1_total_points < team_2_total_points:
            winner_id = contract.team_2_id
        else:
            logger.info(f'[MaintainVault][execute_wager] - Tie: Refunding {contract.team_1_id}-{contract.team_2_id} matchup.')
            await contract.refund()
            return

        winner_list = [prediction for prediction in contract.predictions if prediction.prediction_team == winner_id]
        print(winner_list)
        if winner_list:
            closest_prediction:Vault.GroupWagerContract.Prediction = min(winner_list, key=lambda p: abs(p.prediction_points - total_points)) #copy
            logger.info(f'[MaintainVault][execute_wager] - Team {closest_prediction.gambler.discord_tag} wins {contract.winnings} tokens.')
            await contract.execute_contract(winner=closest_prediction.gambler)


    async def execute_slap(self, contract:Vault.SlapContract, week_dict:dict[str:Any]):
        challenger_id = str(contract.challenger.fantasy_id)
        challengee_id = str(contract.challengee.fantasy_id)

        challenger_dict = week_dict.get(challenger_id)
        challengee_dict = week_dict.get(challengee_id)

        if challenger_dict.get('total_points') > challengee_dict.get('total_points'):
            await contract.execute_contract(contract.challenger)
            await self.assign_role(int(contract.challengee.discord_id), self.loser_role_name)
        elif challenger_dict.get('total_points') < challengee_dict.get('total_points'):
            await contract.execute_contract(contract.challengee)
            await self.assign_role(int(contract.challenger.discord_id), self.loser_role_name)   
        else:
            await contract.refund()
        
        contract.executed = True
        

    async def execute_by_contract_type(self, contract_type):
        CONTRACT_EXECUTORS = {
            Vault.SlapContract.__name__ : self.execute_slap,
            Vault.GroupWagerContract.__name__ : self.execute_wager,
        }

        prev_week = None
        while await self._vault.ready_to_execute(contract_type=contract_type):
            contract = await self._vault.get_next_contract(contract_type=contract_type)
            current_week = contract.week

            if prev_week is None or prev_week != current_week:
                week_dict = await self.get_matchup_data(current_week)
                prev_week = current_week

            executor = CONTRACT_EXECUTORS.get(contract_type)
            if executor is None:
                raise ValueError("contract_type is invalid.")
            
            await executor(contract, week_dict)

            await self._vault.pop_contract(contract_type=contract_type)
            await self.store_all()

    async def execute_all_contracts(self):
        logger.info("[MaintainVault] - Executing all Conracts")
        await self.execute_by_contract_type(contract_type=Vault.SlapContract.__name__)
        await self.execute_by_contract_type(contract_type=Vault.GroupWagerContract.__name__)


    ###################################################
    # Create Contract Commands        
    ###################################################

    @app_commands.command(name='wager', description="Place a wager on one of this week's matchups.")
    @app_commands.describe(discord_user="Player's Discord Tag", points_prediction="Total, 'COMBINED', points at end of matchup.")
    async def wager(self, interaction:discord.Interaction, discord_user:discord.User, points_prediction:int):
        await interaction.response.defer(ephemeral=True)
        if not await Vault.ready_to_execute(contract_type=Vault.GroupWagerContract.__name__):
            await self.create_current_week_wagers()
        
        gambler:Vault.BankAccount = await Vault.bank_account_by_discord_id(str(interaction.user.id))
        prediction_bank_account:Vault.BankAccount = await Vault.bank_account_by_discord_id(discord_id=str(discord_user.id))
        wager:Vault.GroupWagerContract = await Vault.get_wager(fantasy_id = prediction_bank_account.fantasy_id)

        if gambler is None:
            await interaction.followup.send('Your BankAccount was not found.')
            return
        
        if wager is None:
            await interaction.followup.send('Matchup not found.')
            return
        
        try:
            await wager.add_prediction(gambler=gambler, prediction_id=prediction_bank_account.fantasy_id, prediction_points=points_prediction, amount = self._default_wager_amount)
        except Exception as e:
            message = f"Add predictin failed. Error: {e}"
            logger.warning(message)
            await interaction.followup.send(message)
            return
        await self.store_all()

        message = f"{interaction.user.mention} successfully placed {self._default_wager_amount} tokens on {prediction_bank_account.discord_tag}."
        logger.info(message)
        await interaction.followup.send(message)


    ###################################################
    # Manual Slash Commands        
    ###################################################

    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='execute_contracts', description='manually execute contracts.')
    async def execute_contracts(self,interaction:discord.Interaction):
        await interaction.response.defer()
        if not self._ready:
            await interaction.followup.send('Failed startup. try again.')
            return
        try:
            await self.execute_all_contracts()
        except Exception as e:
            await interaction.followup.send(f'Error: Failed to execute. {e}')
        await interaction.followup.send('Done.')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='add_money', description='Add funds to user account')
    @app_commands.describe(discord_user="User's Discord Tag", amount="Amount to add.")
    async def add_money(self,interaction:discord.Interaction, discord_user:discord.User, amount:int):
        await interaction.response.defer()
        if not self._ready:
            await interaction.followup.send('Failed startup. try again.')
            return

        fantasy_id = await self._vault.fantasy_id_by_discord_id(str(discord_user.id))
        if fantasy_id is None:
            await interaction.followup.send('Error: User not found.')
        else:
            await self._vault.add_money(fantasy_id=fantasy_id, amount = amount)
            balance_info = await self._vault.bank_account_info_by_discord_id(str(discord_user.id))
            await interaction.followup.send(f'```{balance_info}```')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='deduct_money', description='Deduct funds to user account')
    @app_commands.describe(discord_user="User's Discord Tag", amount="Amount to deduct.")
    async def deduct_money(self, interaction:discord.Interaction, discord_user:discord.User, amount:int):
        await interaction.response.defer()
        if not self._ready:
            await interaction.followup.send('Failed startup. try again.')
            return

        fantasy_id = await self._vault.fantasy_id_by_discord_id(str(discord_user.id))
        if fantasy_id is None:
            await interaction.followup.send('Error: User not found.')
        else:
            await self._vault.deduct_money(fantasy_id=fantasy_id, amount = amount)
            balance_info = await self._vault.bank_account_info_by_discord_id(str(discord_user.id))
            await interaction.followup.send(f'```{balance_info}```')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='transfer_money', description='Transfer funds to user account')
    @app_commands.describe(discord_user_from="User's Discord Tag to deduct.", discord_user_to="User's Discord Tag to add.", amount="Amount to transfer.")
    async def transfer_money(self, interaction:discord.Interaction, discord_user_from:discord.User, discord_user_to:discord.User, amount:int):
        await interaction.response.defer()
        if not self._ready:
            await interaction.followup.send('Failed startup, try again.')
            return

        fantasy_id_to = await self._vault.fantasy_id_by_discord_id(str(discord_user_to.id))
        fantasy_id_from = await self._vault.fantasy_id_by_discord_id(str(discord_user_from.id))
        if fantasy_id_to is None or fantasy_id_from is None:
            await interaction.followup.send('Error: User not found.')
        else:
            await self._vault.transfer_money(to_fantasy_id=fantasy_id_to, from_fantasy_id=fantasy_id_from, amount = amount)
            balance_info_to = await self._vault.bank_account_info_by_discord_id(str(discord_user_to.id))
            balance_info_from = await self._vault.bank_account_info_by_discord_id(str(discord_user_from.id))
            await self._vault_manager.write_pickle(filename=self._vault_pickle_filename, data=self._vault)
            await interaction.followup.send(f'```{balance_info_to}```\n```{balance_info_from}```')


    ###################################################
    # Create this weeks contracts        
    ###################################################

    async def create_wagers_from_matchup_data(self, data_dict):
        for key, value in data_dict.items():
            await Vault.create_contract(
                team_1_id=value.get('team_id'),
                team_2_id=value.get('team_opponent_id'),
                expiration_date=datetime.strptime(value.get('week_end'), '%Y-%m-%d'),
                week=value.get('week'),
                amount = self._default_wager_bonus,
                contract_type=Vault.GroupWagerContract.__name__
            )
            await self.store_all()


    async def check_wager_ready(self) -> bool:
        if await Vault.ready_to_execute(contract_type=Vault.GroupWagerContract.__name__):
            logger.info("Last Week's wagers must be executed.")
            await self.execute_all_contracts()
        
        if await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__):
            logger.info("Current week contracts already created.")
            return False
        return True


    async def create_current_week_wagers(self):
        async with self.bot.state.league_lock:
            league = self.bot.state.league
        current_week = league.current_week

        if not await self.check_wager_ready():
            return
        
        data_dict = await self.get_matchup_data(current_week)
        await self.create_wagers_from_matchup_data(data_dict)


    @tasks.loop(minutes=1440)
    async def update_wagers(self):
        await self.create_current_week_wagers()
        

    ###################################################
    # Error Handling         
    ###################################################

    @update_wagers.error
    async def update_wagers_error(self,error):
        logger.error(f'[MaintainVault][update_wagers] - Error: {error}')

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        message = ""
        if isinstance(error, app_commands.CommandNotFound):
            message = "This command does not exist."
        elif isinstance(error, app_commands.CheckFailure):
            message = "You do not have permission to use this command."
        else:
            message = "An error occurred. Please try again."

        logger.error(f"[MaintainVault] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[MaintainVault] - Failed to send error message: {e}")


    ###################################################
    # Setup          
    ###################################################

    async def construct_new_bank_accounts(self) -> dict[str,Vault.BankAccount]:
        members:list[dict] = await self._persistent_manager.load_json(filename = self._members_filename)

        if not members:
            raise AttributeError('[MaintainVault][construct_new_bank_accounts] - Error: expected members.json to be populated.' )
        else:
            accounts:dict[str, Vault.BankAccount] = {}
            for entry in members:
                if entry.get('discord_id') is None:
                    raise ValueError('[MaintainVault][construct_new_bank_accounts] - Error: Use bind commands to bind yahoo_id to discord_tag.')

                bank_account = Vault.BankAccount(
                    entry.get('name'),
                    utility.id_to_mention(entry.get('discord_id')),
                    entry.get('discord_id'),
                    entry.get('id'),
                    self._initial_bank_funds
                )
                accounts[entry.get('id')] = bank_account
            return accounts
        
    async def get_member_dict(self, fantasy_id:str):
        members:list[dict] = await self._persistent_manager.load_json(filename = self._members_filename)
        for member in members:
            if member.get('id') == fantasy_id:
                return member


    async def update_account_names(self):
        for key, value in Vault.accounts.items():
            member = await self.get_member_dict(key)
            value.name = member.get('name')


    ####################################################
    # Load and store accounts/contracts
    ####################################################

    async def store_accounts(self):
        serialized_accounts = await self._vault.serialize_accounts()
        await self._vault_manager.write_json(self._vault_accounts_filename, serialized_accounts)


    async def store_contracts(self):
        serialized_slap_contracts = await self._vault.serialize_contracts(contract_type=Vault.SlapContract.__name__)
        serialized_wager_contracts = await self._vault.serialize_contracts(contract_type=Vault.GroupWagerContract.__name__)
        await self._vault_manager.write_json(self._vault_slap_contracts_filename, serialized_slap_contracts)
        await self._vault_manager.write_json(self._vault_wager_contracts_filename, serialized_wager_contracts)


    async def store_all(self):
        await self.store_accounts()
        await self.store_contracts()

    async def load_filename(self, filename):
        data = await self._vault_manager.load_json(filename)
        if data:
            return data
        return None

    async def load_all(self) -> Vault:
        serialized_accounts = await self.load_filename(self._vault_accounts_filename)
        serialized_slap_contracts = await self.load_filename(self._vault_slap_contracts_filename)
        serialized_wager_contracts = await self.load_filename(self._vault_wager_contracts_filename)

        if not serialized_accounts:
            return None

        new_vault = Vault()
        await new_vault.initialize_from_serialized(accounts=serialized_accounts, slap_contracts=serialized_slap_contracts, wager_contracts=serialized_wager_contracts)
        return new_vault


    async def init_vault(self):
        loaded_vault = await self.load_all()
        if loaded_vault is None:
            try:
                loaded_vault = Vault()
                accounts:dict[str,Vault.BankAccount] = await self.construct_new_bank_accounts()
                await loaded_vault.initialize(accounts=accounts)

            except Exception as e:
                logger.error('[MaintainVault][Initialization] - Failed to initialize new Vault.')
                logger.error(f'[MaintainVault][Initialization] - Error: {e}')
                return
        else:
            await self.update_account_names()

        self.bot.state.vault = loaded_vault
        self._vault = self.bot.state.vault
        await self.store_accounts()
        self._ready = True


    async def wait_for_fantasy_and_memlist(self):
        while not self._ready_to_init:
            async with self.bot.state.fantasy_query_lock:
                fantasy_query = self.bot.state.fantasy_query
            async with self.bot.state.memlist_ready_lock:
                memlist_ready = self.bot.state.memlist_ready
            if memlist_ready and fantasy_query is not None:
                self._ready_to_init = True
            else:
                await asyncio.sleep(1)   


    async def create_and_store_contract(self):
        expiration = datetime.today() - timedelta(days=4)
        try:
            await Vault.create_contract(
                challenger_fantasy_id='3',
                challengee_fantasy_id='5',
                amount=10, 
                expiration_date=expiration, 
                week=4, 
                contract_type=Vault.SlapContract.__name__
            )
            await self.store_all()
        except Exception as e:
            logger.error(f'[MaintainVault][create_and_store] - Failed to create Contract. Error:{e}')
            
        
    @commands.Cog.listener()
    async def on_ready(self): 
        await self.wait_for_fantasy_and_memlist()
        await self.init_vault()
        logger.info('[MaintainVault] - Initialized MaintainVault')

        self.update_wagers.start()
        ## temporary for testing ##
        #await self.create_and_store_contract()


    ####################################################
    # Handle Load
    ####################################################

    async def cog_load(self):
        logger.info('[MaintainVault] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[MaintainVault] - Cog Unload')



async def setup(bot):
    await bot.add_cog(MaintainVault(bot))