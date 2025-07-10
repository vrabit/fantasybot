import discord
from discord import app_commands
from discord.ext import  commands

from pathlib import Path

from yfpy.models import League, Player

import asyncio
import os

import logging
logger = logging.getLogger(__name__)

class PlayerIDs(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready = False

        self._players = None
        self._players_lock = asyncio.Lock()

        self._player_data_filename = bot.state.player_data_filename
        self._player_data_filepath = self.parent_dir / 'persistent_data'/ bot.state.player_data_filename
        self.player_ids_filename = bot.state.player_ids_filename


    ###################################################
    # Helpers        
    ###################################################

    async def add_new_player(self,player:Player):
        if not self._players or str(player.player_id) not in self._players:
            self._players[str(player.player_id)] = str(player.name.full)
            return False
        else:
            logger.warning(f'[playerIDs] - Player {player.name.full}: {player.player_id} already exists in player list.')
            return True


    async def request_player_info(self):
        start = 0
        found = False
        while found is False:
            async with self.bot.state.fantasy_query_lock:
                league:League = self.bot.state.fantasy_query.get_players(start=start)['league']
            players_list:list[Player] = league.players

            # check if null or empty league or players_list
            if league is None or players_list is None or not players_list:
                logger.warning('[PlayerIDs] - Empty playerlist')
                break

            logger.info(f'[PlayerIds] - Collecting players from {start} to {start + 24}')
            for player in players_list:
                found = await self.add_new_player(player)

                if found:
                    break

            await self.bot.state.persistent_manager.write_json(self._player_data_filename, self._players)
            start += 25

            # pace requests to avoid rate limit
            await asyncio.sleep(2)
            

    ############################################################################
    # Collect all player IDs from yahoo, should only be run once per season      
    ############################################################################

    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name="create_player_csv", description= "create a CSV file with data from /collect_IDs command")
    async def create_player_csv(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self._players is not None:
            # Update player csv data file
            await self.bot.state.persistent_manager.write_simple_csv(filename=self.player_ids_filename, data=self._players)
            #utility.store_players(self._players)
                      
            await interaction.followup.send('Player CSV file Created', ephemeral=True)
        else:
            await interaction.followup.send('No player data found. Please run /collect_IDs first.', ephemeral=True)


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name="store_player_info", description= "Request and store ALL NFL player Info in batches")
    async def collect_IDs(self, interaction: discord.Interaction):
        await interaction.response.send_message('Collection Triggered')
        logger.info(f'Collection Triggered: Will be stored within {self._player_data_filepath}')
        await self.request_player_info()
        

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
        logger.error(f"[PlayerIDs] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[PlayerIDs] - Failed to send error message: {e}")


    ###################################################
    # Handle Load          
    ###################################################

    async def cog_load(self):
        logger.info('[PlayersIDs] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


    ###################################################
    # Setup          
    ###################################################
    
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

        async with self._players_lock:
            self._players = await self.bot.state.persistent_manager.load_json(self._player_data_filename)
        logger.info('[PlayerIDs] - Ready')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[PlayerIDs] - Cog Unload')



async def setup(bot):
    await bot.add_cog(PlayerIDs(bot))