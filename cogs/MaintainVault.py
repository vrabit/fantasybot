import discord
from discord import app_commands
from discord.ext import tasks,commands

import os
import asyncio

from pathlib import Path

import utility

class MaintainVault(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        # file managers
        self._persistent_manager = self.bot.state.persistent_manager

        # files
        self._vault_accounts_filename = 'vault_accounts.json'
        self._vault_contracts_filename = 'vault_contracts.json'


    ###################################################
    # Manual Commands        
    ###################################################

    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='add_money', description='Add funds to user account')
    @app_commands.describe(discord_user="User's Discord Tag", amount="Amount to add.")
    async def add_money(self,interaction:discord.Interaction, discord_user:discord.User, amount:int):
        await interaction.response.defer()


        await interaction.followup.send('temp')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='deduct_money', description='Deduct funds to user account')
    @app_commands.describe(discord_user="User's Discord Tag", amount="Amount to deduct.")
    async def deduct_money(self, interaction:discord.Interaction, discord_user:discord.User, amount:int):
        await interaction.response.defer()


        await interaction.followup.send('temp')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='transfer_money', description='Transfer funds to user account')
    @app_commands.describe(discord_user_from="User's Discord Tag to deduct.", discord_user_to="User's Discord Tag to add.", amount="Amount to transfer.")
    async def transfer_money(self, interaction:discord.Interaction, discord_user_from:discord.User, discord_user_to:discord.User, amount:int):
        await interaction.response.defer()


        await interaction.followup.send('temp')


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
        await self._persistent_manager.load_json(self._vault_accounts_filename)

        
    async def init_accounts(self):
        await self._persistent_manager.load_json(self._vault_accounts_filename)

    async def init_vault(self):
        await self.init_accounts()
        await self.init_contracts()
        
    async def wait_for_fantasy_and_memlist(self):
        while not self._ready:
            async with self.bot.state.fantasy_query_lock:
                fantasy_query = self.bot.state.fantasy_query
            async with self.bot.state.memlist_ready_lock:
                memlist_ready = self.bot.state.memlist_ready
            if memlist_ready and fantasy_query is not None:
                self._ready = True
            else:
                await asyncio.sleep(1)   


    @commands.Cog.listener()
    async def on_ready(self): 
        await self.init_vault()
        await self.wait_for_fantasy_and_memlist()
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