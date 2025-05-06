import discord
from discord.ext import tasks, commands

from pathlib import Path

import json

from yfpy.query import YahooFantasySportsQuery
from fantasy import fantasyQuery

class MaintainFantasy(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.refresh_fantasy.start()

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent

    ###################################################
    # Refresh fantasy every 4 hours         
    ###################################################

    @tasks.loop(minutes=60)
    async def refresh_fantasy(self):
        print('[MaintainFantasy] - Refreshing Fantasy Object')
        async with self.bot.state.fantasy_query_lock:
            # set directory location of private.json for authentication
            auth_dir = self.parent_dir / 'yfpyauth' 

            with open(auth_dir / 'config.json', 'r') as file:
                config_data = json.load(file)

            with open(auth_dir / 'private.json') as file:
                private_data = json.load(file)

            # game_id = None, defaults to the game ID for the current year.
            yahoo_query = YahooFantasySportsQuery(
                auth_dir,
                config_data.get('league_id'),
                config_data.get('game_code'),
                game_id = config_data.get('game_id'),
                offline=False,
                all_output_as_json_str=False,
                consumer_key=private_data.get('consumer_key'),
                consumer_secret=private_data.get('consumer_secret')
            )

            self.bot.fantasy_query = fantasyQuery(yahoo_query)
        print('[MaintainFantasy] - .. Done')


    ###################################################
    # Setup          
    ###################################################
    
    @commands.Cog.listener()
    async def on_ready(self):
        
        print('[MaintainFantasy] - Yahoo Fantasy Initialized\n  ..')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        self.refresh_fantasy.cancel()
        print('[MaintainFantasy] - Cog Unload')



async def setup(bot):
    await bot.add_cog(MaintainFantasy(bot))