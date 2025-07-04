import discord
from discord.ext import tasks, commands

from pathlib import Path
import asyncio

import os
from collections import deque
from yfpy.models import Team
import feedparser
import utility

import logging
logger = logging.getLogger(__name__)

class RSSHandler(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        self._rssURL = 'https://www.rotowire.com/rss/news.php?sport=NFL'
        self.update_interval = 600.0
    
        self.MAX_QUEUE = 30

        self.feed_queue:deque = deque(maxlen=self.MAX_QUEUE)
        self.feed_queue_lock = asyncio.Lock()

        self._members_filename = 'members.json'
        self._private_filename = 'private.json'
        self._rss_queue_filename = 'rss_queue.json'


    ###################################################
    # RSS Helpers          
    ###################################################

    async def save_queue(self):
        logger.info('[RSSHandler] - Saving Feed Queue')
        async with self.feed_queue_lock:
            serialized_feed_queue = list(self.feed_queue)
            await self.bot.state.persistent_manager.write_json(filename = self._rss_queue_filename, data=serialized_feed_queue)
        logger.info('[RSSHandler] - Done')


    async def load_queue(self):
        feed_queue = await self.bot.state.persistent_manager.load_json(filename = self._rss_queue_filename)
        return deque(feed_queue)


    async def fetch_rss(self,session,url):
        logger.info('[RSSHandler] - Fetching RSS')
        async with session.get(url) as response:
            response_text = await response.text()
            return response_text


    async def send_rss(self,value):
        logger.info('[RSSHandler] - Sending RSS')
        async with self.bot.state.news_channel_id_lock:
            local_id = self.bot.state.news_channel_id
        
        # Set News channel
        channel = self.bot.get_channel(int(local_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(local_id))
            except Exception as e:
                logger.error(f'f[RSSHandler][send_rss] - Error{e}')
                return

        logger.info(f'[RSSHandler] - Send channel : {channel}')
        title = next(iter(value))
        detail=value[title][0]
        page_url=value[title][1]

        embed = discord.Embed(title = title, url=page_url, description = '', color = self.emb_color)

        embed.add_field(name = '', value=detail)
        message = await channel.send(embed = embed)
        await message.create_thread(name=title, auto_archive_duration=1440)


    async def verify_news_channel(self):
        async with self.bot.state.news_channel_id_lock:
            self.bot.state.news_channel_id = self.bot.state.news_channel_id or await self.setup_RSS()

            if self.bot.state.news_channel_id is None:
                logger.info('[RSSHandler] - No news channel ID found within private_data.json')
                return False
            else:
                logger.info(f'[RSSHandler] - News channel ID set to {self.bot.state.news_channel_id}')
                return True


    @tasks.loop(minutes=10)
    async def poll_rss(self,url='https://www.rotowire.com/rss/news.php?sport=NFL'):

        channel_set = await self.verify_news_channel()
        if not channel_set:
            logger.info('[RSSHandler][Poll_RSS] - News channel not set')
            return

        logger.info('[RSSHandler][Poll_RSS] - Started')
        loaded_queue = await self.load_queue()
        async with self.feed_queue_lock:
            self.feed_queue = loaded_queue

        async with self.bot.state.session.get(url) as response:
            response_text = await response.text()
            
            content = feedparser.parse(response_text)
            if content.bozo:
                logger.warning('[RSSHandler][Poll_RSS] - Error parsing RSS feed')
                return

            async with self.feed_queue_lock:
                for entry in content.entries:    
                    if len(self.feed_queue) <= 0:
                        self.feed_queue.append({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                        await self.send_rss({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                    else:
                        found = False
                        for dict_entry in self.feed_queue:
                            if entry.get('title') in dict_entry:
                                found = True
                                break
                        if not found:
                            self.feed_queue.append({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                            await self.send_rss({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                            
        logger.info('[RSSHandler][Poll_RSS] - .. Done')
        await self.save_queue()


    ###################################################
    # Handle Startup          
    ###################################################

    async def setup_RSS(self):
        # load private data 
        data = await self.bot.state.discord_auth_manager.load_json(filename = self._private_filename)
        #await utility.get_private_discord_data_async()

        raw_data = data.get('news_channel_id')
        if raw_data is None:
            logger.warning('[RSSHandler] - No news channel ID found within private_data.json')
            return None
        else:
            try:
                int(raw_data)
            except ValueError:
                logger.error('[RSSHandler] - Invalid news channel ID')
                return None
        return int(data.get('news_channel_id'))

    
    async def compose_memlist(self, team_list:list[Team]) -> list[dict]:
        members = []
        try:
            for team in team_list:
                entry = {}
                entry['name'] = utility.ensure_str(team.name)
                entry['id'] = str(team.team_id)
                members.append(entry)

        except Exception as e:
            logger.error(f'[RSSHandler][init_memlist] - Error: {e}')
            return []
        
        return members


    async def update_names(self, team_list:list[Team]) -> list[dict]:
        members_list = await self.bot.state.persistent_manager.load_json(self._members_filename)

        for team in team_list:
            for member in members_list:
                if int(team.team_id) == int(member.get('id')):
                    member.update({'name':utility.ensure_str(team.name)})
        return members_list


    async def update_memlist(self, team_list:list[Team]) -> None:
        if await self.bot.state.persistent_manager.path_exists(self._members_filename):
            # update player names in list
            members_list = await self.update_names(team_list)
        else:
            # compose new member list and store it
            members_list = await self.compose_memlist(team_list)

        await self.bot.state.persistent_manager.write_json(filename=self._members_filename, data=members_list)


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
        logger.info('[RSSHandler] - RSS Setup .. ')

        async with self.bot.state.fantasy_query_lock:
            team_list:list[Team] =self.bot.state.fantasy_query.get_teams()

        await self.update_memlist(team_list)
        async with self.bot.state.memlist_ready_lock:
            self.bot.state.memlist_ready = True

        self.poll_rss.start(self._rssURL)
        logger.info('[RSSHandler] - Ready')


    ###################################################
    # Loop Error Handling          
    ###################################################

    @poll_rss.error
    async def poll_rss_error(self,error):
        logger.error(f'[RSSHandler][poll_rss] - Error: {error}\n')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[RSSHandler] - Cog Unload')
        self.poll_rss.cancel()


async def setup(bot):
    await bot.add_cog(RSSHandler(bot))