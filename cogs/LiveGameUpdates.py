import discord
from discord import app_commands
from discord.ext import commands

import asyncio

from pathlib import Path
from bet_vault.vault import Vault
from difflib import get_close_matches
from datetime import datetime

import logging
logger = logging.getLogger(__name__)

class LiveGameUpdates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent

        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        # file managers
        #self._persistent_manager = self.bot.state.persistent_manager
        self._live_manager = self.bot.state.live_manager

        # session
        self._session = bot.state.session

        # ESPN api links
        self._nfl_team_info_url = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams'

        # filenames
        self._team_info_filename = 'espn_team_info.json'

        # loaded data
        self._team_value_map = None
        self._team_value_map_lock = asyncio.Lock()
        self._nfl_team_info = None


    ###################################################
    # Manual Slash Commands        
    ###################################################

    @app_commands.command(name='nfl_team_schedule', description='List team schedule.')
    @app_commands.describe(team_name="NFL team name. ie. 'Jets'")
    async def nfl_team_schedule(self, interaction:discord.Interaction, team_name:str):
        await interaction.response.defer()
        if not self._ready:
            raise AttributeError('[LiveGameUpdates] - Failed initializaztion.')

        async with self._team_value_map_lock:
            closest_key = get_close_matches(team_name, self._team_value_map, n=1, cutoff=0.6)

        if len(closest_key) == 0:
            await interaction.followup.send('Failed to match team.')
            return

        info:dict = await self.return_team_info(closest_key[0])

        url = f'{self._nfl_team_info_url}/{int(info.get('id'))}/schedule'
        raw_data = await self.fetch_no_retry(url)
        event_str = await self.raw_schedule_data_to_str(raw_data)

        await interaction.followup.send(f'```{event_str}```')



    ###################################################
    # Helpers        
    ###################################################

    async def return_team_info(self, team_name):
        async with self._team_value_map_lock:
            return self._team_value_map.get(team_name)


    async def fetch_no_retry(self, url):
        async with self._session.get(url) as response:
            if response.status == 200:
                try: 
                    data_json = await response.json()
                    if data_json is not None:
                        return data_json
                except Exception as e:
                    logger.error(f"JSON decode error: {e}")
            else:
                logger.info(f'[LiveGameUpdates][fetch_no_retry] - Error:{response.status}')
        return None


    async def raw_schedule_data_to_str(self, raw_data):
        if raw_data is None:
            raise ValueError('raw_data is None.')
        
        events = raw_data.get('events')
        complete_str = ''
        for event in events:
            date = datetime.fromisoformat(event.get('date').replace("Z", "+00:00"))
            complete_str += f'{event.get('name')}\n' + f'{date}\n' + f'Game ID: {event.get('id')} \n\n'
        return complete_str


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

        logger.error(f"[LiveGameUpdates] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[LiveGameUpdates] - Failed to send error message: {e}")


    ###################################################
    # Handle Startup          
    ###################################################

    async def team_list_from_espn_sport(self, data_json):
        sports_dict = data_json.get('sports')[0]
        leagues_dict = sports_dict.get('leagues')[0]
        teams_list = leagues_dict.get('teams')
        return teams_list


    async def fetch_with_retry(self, retries=5, delay=300):
        for attempt in range(retries):
            async with self._session.get(self._nfl_team_info_url) as response:
                if response.status == 200:
                    try:
                        data_json = await response.json()
                        if data_json is not None:
                            return data_json
                    except Exception as e:
                        logger.error(f"Attempt {attempt + 1}: JSON decode error:", e)
                else:
                    logger.info(f"Attempt {attempt + 1}: Request failed with status {response.status}")

            logger.info(f"Waiting {delay} seconds before retrying...")     
            await asyncio.sleep(delay)
        logger.info('Max retries reached, Failed to retrieve data.')
        return None


    async def save_team_information(self):
        loaded = await self._live_manager.load_json(filename = self._team_info_filename)
        if loaded:
            self._nfl_team_info = loaded
            logger.info('[LiveGameUpdates] - Data successfully loaded.')
            return

        data_json = await self.fetch_with_retry()

        if not data_json:
            logger.warning('[LiveGameUpdates] - Error: ESPN turn retuned None.')
            return
        
        team_list = await self.team_list_from_espn_sport(data_json)
        self._nfl_team_info = team_list
        await self._live_manager.write_json(filename = self._team_info_filename, data = team_list)


    async def load_team_value_map(self):
        team_info_map = {}
        excluded_keys = {'logos', 'isAllStar', 'isActive', 'links'} 

        for entry in self._nfl_team_info:
            team_dict = entry.get('team')
            team_info_map[team_dict.get('name')] = {key:value for key, value in team_dict.items() if key not in excluded_keys}

        async with self._team_value_map_lock:
            self._team_value_map = team_info_map


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
        await self.save_team_information()
        await self.load_team_value_map()
        self._ready = True
        logger.info('[LiveGameUpdates] - Initialized LiveGameUpdates')


    ####################################################
    # Handle Load
    ####################################################

    async def cog_load(self):
        logger.info('[LiveGameUpdates] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[LiveGameUpdates] - Cog Unload')


async def setup(bot):
    await bot.add_cog(LiveGameUpdates(bot))