import discord
from discord import app_commands
from discord.ext import tasks,commands

import os
import asyncio

from collections import deque
from pathlib import Path
from bet_vault.vault import Vault

import utility

class MaintainVault(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready_to_init = False
        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        # file managers
        self._persistent_manager = self.bot.state.persistent_manager

        # vault 
        self._vault:Vault = self.bot.state.vault
        self._initial_bank_funds = 100

        # files
        self._members_filename = 'members.json'
        self._vault_accounts_filename = 'vault_accounts.json'
        self._vault_contracts_filename = 'vault_contracts.json'


    ###################################################
    # Manual Slash Commands        
    ###################################################

    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='add_money', description='Add funds to user account')
    @app_commands.describe(discord_user="User's Discord Tag", amount="Amount to add.")
    async def add_money(self,interaction:discord.Interaction, discord_user:discord.User, amount:int):
        await interaction.response.defer()
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
        fantasy_id_to = await self._vault.fantasy_id_by_discord_id(str(discord_user_to.id))
        fantasy_id_from = await self._vault.fantasy_id_by_discord_id(str(discord_user_from.id))
        if fantasy_id_to is None or fantasy_id_from is None:
            await interaction.followup.send('Error: User not found.')
        else:
            await self._vault.transfer_money(to_fantasy_id=fantasy_id_to, from_fantasy_id=fantasy_id_from, amount = amount)
            balance_info_to = await self._vault.bank_account_info_by_discord_id(str(discord_user_to.id))
            balance_info_from = await self._vault.bank_account_info_by_discord_id(str(discord_user_from.id))
            await interaction.followup.send(f'```{balance_info_to}```\n```{balance_info_from}```')



    ###################################################
    # Error Handling         
    ###################################################

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):

        message = ""
        if isinstance(error, app_commands.CommandNotFound):
            message = "This command does not exist."
        elif isinstance(error, app_commands.CheckFailure):
            message = "You do not have permission to use this command."
        else:
            message = "An error occurred. Please try again."
            print(f"[MaintainVault] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            print(f"[MaintainVault] - Failed to send error message: {e}")


    ###################################################
    # Setup          
    ###################################################
    async def init_contracts(self):
        contracts_raw = await self._persistent_manager.load_json(self._vault_contracts_filename)
        if not contracts_raw:
            return deque()
        else:
            contracts:deque[Vault.Contract] = deque()
            for key, value in contracts_raw:
                contract:Vault.Contract = {}
                contract[key] = Vault.Contract(
                    value.get('challenger'), 
                    value.get('challengee'), 
                    value.get('expiration'),
                    value.get('executed'),
                    value.get('amount')
                )
                deque.append(contract)
            return contracts

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
        
    async def get_member_info(self, id):
        members:list[dict] = await self._persistent_manager.load_json(filename = self._members_filename)
        for entry in members:
            if entry.get('id') == id:
                return entry

        raise AttributeError('[MaintainVault][get_member_info] - Error: Unable to find member data.')

    async def load_and_update_accounts(self, accounts_raw) -> dict[str, Vault.BankAccount]:

        accounts:dict[str,Vault.BankAccount] = {}
        for key, value in accounts_raw.items():
            member_info = await self.get_member_info(value.get('fantasy_id'))

            bank_account = Vault.BankAccount(
            member_info.get('id'),
            value.get('discord_tag'),
            value.get('discord_id'),
            value.get('fantasy_id'),
            value.get('money')
            )
            accounts[key] = bank_account
        return accounts

    async def init_accounts(self):
        accounts_raw = await self._persistent_manager.load_json(self._vault_accounts_filename)
        if not accounts_raw:
            return await self.construct_new_bank_accounts()
        else:
            return await self.load_and_update_accounts(accounts_raw)

    async def init_vault(self):
        try:
            contracts:deque = await self.init_contracts()
            accounts:dict[str,Vault.BankAccount] = await self.init_accounts()
            await self._vault.initialize(
                file_manager=self._persistent_manager, 
                contracts_filename = self._vault_contracts_filename,
                accounts_filename= self._vault_accounts_filename,
                accounts = accounts, 
                contracts = contracts
            )
            await self._vault.store_all()
            self._ready = True
        except Exception as e:
            print('[MaintainVault][Initialization] - Failed to initialize contracts and accounts.')
            print(f'[MaintainVault][Initialization] - Error: {e}')


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


    @commands.Cog.listener()
    async def on_ready(self): 
        await self.wait_for_fantasy_and_memlist()
        await self.init_vault()
        print('[MaintainVault] - Initialized MaintainVault')


    ####################################################
    # Handle Load
    ####################################################

    async def cog_load(self):
        print('[MaintainVault] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)

    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        print('[MaintainVault] - Cog Unload')



async def setup(bot):
    await bot.add_cog(MaintainVault(bot))