from discord.ext import  tasks,commands

from pathlib import Path

from yfpy.query import YahooFantasySportsQuery
from fantasy import fantasyQuery

import os
import utility

class MaintainFantasy(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.refresh_fantasy.start()

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent


    ###################################################
    # Setup fantasy object       
    ###################################################

    @tasks.loop(minutes=60)
    async def refresh_fantasy(self):
        """Refresh the fantasy object every hour."""
        print('[MaintainFantasy] - Initializing Fantasy Object')
        async with self.bot.state.fantasy_query_lock:
            # set directory location of private.json for authentication
            auth_dir = self.parent_dir / 'yfpyauth' 

            try:
                # game_id = None, defaults to the game ID for the current year.
                yahoo_query = YahooFantasySportsQuery(
                    league_id = os.getenv('LEAGUE_ID'),
                    game_code = os.getenv('GAME_CODE').lower(),
                    game_id = os.getenv('GAME_ID'),
                    yahoo_consumer_key=os.getenv('CONSUMER_KEY'),
                    yahoo_consumer_secret=os.getenv('CONSUMER_SECRET'),
                    save_token_data_to_env_file=True,
                    env_file_location=auth_dir,
                )
            except Exception as e:
                print(f'[MaintainFantasy] - Error initializing Yahoo Fantasy Sports Query: {e}')
                print('[MaintainFantasy] - Verify elements within yfpyauth/config.json and yfpyauth/private.json')
                await self.bot.close()
                return
            
            players_dict = await utility.load_players_async()
            
            # Set bot state to the new fantasy query object
            self.bot.state.fantasy_query = fantasyQuery(yahoo_query,players_dict)

            # Set current League
            self.bot.state.league = self.bot.state.fantasy_query.get_league()['league']


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