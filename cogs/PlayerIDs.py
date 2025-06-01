import discord
from discord import app_commands
from discord.ext import  commands

from pathlib import Path

from yfpy.models import League, Player

import asyncio
import os



class PlayerIDs(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready = False

        self._players = None
        self._players_lock = asyncio.Lock()

        self.filepath = self.parent_dir / 'persistent_data'/ 'player_data.json'
        self.filename = 'player_data.json'
        self.csv_filename = 'player_ids.csv'


    ###################################################
    # Helpers        
    ###################################################

    async def add_new_player(self,player:Player):
        if not self._players or str(player.player_id) not in self._players:
            self._players[str(player.player_id)] = str(player.name.full)
            return False
        else:
            print(f'[playerIDs] - Player {player.name.full}: {player.player_id} already exists in player list.')
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
                print('[PlayerIDs] - Empty playerlist')
                break

            print(f'[PlayerIds] - Collecting players from {start} to {start + 24}')
            for player in players_list:
                found = await self.add_new_player(player)

                if found:
                    break

            await self.bot.state.persistent_manager.write_json(self.filename, self._players)
            #utility.store_player_ids(self._players, self.filename)
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
            await self.bot.state.persistent_manager.write_simple_csv(filename=self.csv_filename, data=self._players)
            #utility.store_players(self._players)
                      
            await interaction.followup.send('Player CSV file Created', ephemeral=True)
        else:
            await interaction.followup.send('No player data found. Please run /collect_IDs first.', ephemeral=True)


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name="store_player_info", description= "Request and store ALL NFL player Info in batches")
    async def collect_IDs(self, interaction: discord.Interaction):
        await interaction.response.send_message('Collection Triggered')
        print(f'Collection Triggered: Will be stored within {self.filepath}')
        await self.request_player_info()
        

    ###################################################
    # Error Handling         
    ###################################################

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandNotFound):
            await interaction.response.send_message("This command does not exist.", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        else:
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            # Log the error or print details for debugging
            print(f"[PlayerIDs] - Error: {error}")


    ###################################################
    # Handle Load          
    ###################################################

    async def cog_load(self):
        print('[PlayersIDs] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


    ###################################################
    # Setup          
    ###################################################
    
    async def wait_for_fantasy(self):
        while self.bot.state.fantasy_query is None:
            asyncio.sleep(1)
        self._ready = True
        

    @commands.Cog.listener()
    async def on_ready(self):
        await self.wait_for_fantasy()

        async with self._players_lock:
            self._players = await self.bot.state.persistent_manager.load_json(self.filename)
        #await utility.load_player_ids(self.filename)
        print('[PlayerIDs] - Ready')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        print('[PlayerIDs] - Cog Unload')



async def setup(bot):
    await bot.add_cog(PlayerIDs(bot))