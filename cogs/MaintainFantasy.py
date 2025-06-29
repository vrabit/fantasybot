from discord.ext import  tasks,commands

from pathlib import Path

from yfpy.query import YahooFantasySportsQuery
from fantasy import fantasyQuery
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import os
import asyncio
import logging

logger = logging.getLogger(__name__)


class MaintainFantasy(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

        self._first_run = True
        self._ready = False

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._player_ids_filename = 'player_ids.csv'


    ###################################################
    # Setup fantasy object       
    ###################################################

    @tasks.loop(minutes=1)
    async def token_expiration(self):
        timestamp = float(os.getenv('YAHOO_TOKEN_TIME', 0))
        issued_utc = datetime.fromtimestamp(timestamp=timestamp, tz=ZoneInfo('UTC'))
        now_utc = datetime.now(tz=ZoneInfo("UTC"))

        delta = (now_utc - issued_utc).total_seconds() 
        time_remaining = 3600 - delta 

        if self._first_run:
            logger.info("Initializing Fantasy Object")
            await self.refresh_fantasy()
            load_dotenv(self.parent_dir / 'yfpyauth' / '.env', override=True)
            self._first_run = False
            logger.info(f"[MaintainFantasy] - {time_remaining}")
            return

        if time_remaining < 60: 
            if time_remaining >= 0:
                logger.info(f"[MaintainFantasy] - Token about to expire: Expires in {time_remaining}")
                await asyncio.sleep(time_remaining + 1)
            else:
                logger.info(f"[MaintainFantasy] - Token Expired: Refreshing token NOW. {time_remaining}")

            await self.refresh_fantasy()
            load_dotenv(self.parent_dir / 'yfpyauth' / '.env', override=True)
        elif time_remaining < 180:
            logger.info(f"[MaintainFantasy] - Token Valid: {time_remaining:.2f} seconds remaining until token refresh.")


    async def refresh_fantasy(self):
        """Refresh the fantasy object every hour."""
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
                
                if yahoo_query is None:
                    raise ValueError('Failed to initialize YahooFantasySportsQuery')
                
            except Exception as e:
                logger.error(f'[MaintainFantasy] - Error: {e}')
                logger.error('[MaintainFantasy] - Verify elements within yfpyauth/config.json and yfpyauth/private.json')
                await self.bot.close()
                return
            
            # Set bot state to the new fantasy query object
            self.bot.state.fantasy_query = fantasyQuery(yahoo_query)

            # Set current League
            self.bot.state.league = self.bot.state.fantasy_query.get_league()['league']

        logger.info('[MaintainFantasy] - .. Done')


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
        self.token_expiration.start()
        #await self.wait_for_fantasy()
        logger.info('[MaintainFantasy] - Yahoo Fantasy Initialized\n  ..')


    ###################################################
    # Loop Error Handling          
    ###################################################

    @token_expiration.error
    async def token_expiration_error(self,error):
        logger.info(f'[MaintainFantasy][token_expiration] - Error: {error}\n')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        self.token_expiration.cancel()
        logger.info('[MaintainFantasy] - Cog Unload')



async def setup(bot):
    await bot.add_cog(MaintainFantasy(bot))