import discord
from discord.ext import tasks, commands

from pathlib import Path
import asyncio
import json
import os
from collections import deque

import aiohttp 
import feedparser

import utility


class RSSHandler(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        self.rssURL = 'https://www.rotowire.com/rss/news.php?sport=NFL'
        self.update_interval = 600.0
    
        self.news_channel_id = self.setup_RSS()
        self.news_id_lock = asyncio.Lock()

        self.MAX_QUEUE = 30
        self.RSS_QUEUE_FILE = 'rss_queue.json'
        self.feed_queue = deque(maxlen=self.MAX_QUEUE)
        self.feed_queue_lock = asyncio.Lock()

        if not self.poll_rss.is_running():
            self.poll_rss.start()
            print('[RSSHandler] - Polling Started')


    ###################################################
    # RSS Helpers          
    ###################################################

    async def save_queue(self,filename='rss_queue.json'):
        async with self.feed_queue_lock:
            with open(self.parent_dir / 'persistent_data' / filename, 'w') as file:
                json.dump(list(self.feed_queue), file, indent = 4)

    async def load_queue(self,filename='rss_queue.json'):
        if not os.path.exists(self.parent_dir / 'persistent_data' / filename):
            return deque(maxlen=self.MAX_QUEUE)
        else:
            with open(self.parent_dir / 'persistent_data' / filename, 'r') as file:
                entries = json.load(file)
                return deque(entries, maxlen=self.MAX_QUEUE)

    async def fetch_rss(self,session,url):
        print('[RSSHandler] - Fetching RSS')
        async with session.get(url) as response:
            response_text = await response.text()
            return response_text

    async def send_rss(self,value):
        print('[RSSHandler] - Sending RSS')
        async with self.news_id_lock:
            local_id = self.news_channel_id
        
        # Set News channel
        channel = self.bot.get_channel(int(local_id))
        if channel is None:
            channel = await self.bot.fetch_channel(int(local_id))

        print(f'[RSSHandler] - Send channel : {channel}')
        title = next(iter(value))
        detail=value[title][0]
        page_url=value[title][1]


        embed = discord.Embed(title = title, url=page_url, description = '', color = self.emb_color)

        embed.add_field(name = '', value=detail)
        message = await channel.send(embed = embed)
        thread = await message.create_thread(name=title, auto_archive_duration=1440)

    @tasks.loop(minutes=10)
    async def poll_rss(self,url='https://www.rotowire.com/rss/news.php?sport=NFL'):
        # wait to make sure session is set up
        await asyncio.sleep(10)
        print('[RSSHandler][Poll_RSS] - Started')

        loaded_queue = await self.load_queue('rss_queue.json')
        async with self.feed_queue_lock:
            self.feed_queue = loaded_queue

        #response = await self.fetch_rss(self.session,url)
        async with self.bot.state.session.get(url) as response:
            response_text = await response.text()
            
            content = feedparser.parse(response_text)
            if content.bozo:
                print('[RSSHandler][Poll_RSS] - Error parsing RSS feed')
                return

            async with self.feed_queue_lock:
                for entry in content.entries:    
                    if len(self.feed_queue) == 0:
                        await self.send_rss({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                        self.feed_queue.append({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                    else:
                        found = False
                        for dict_entry in self.feed_queue:
                            if entry.get('title') in dict_entry:
                                found = True
                                break
                        if not found:
                            await self.send_rss({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                            self.feed_queue.append({entry.get('title'):(entry.get('summary'),entry.get('link'))})
        
        print('[RSSHandler][Poll_RSS] - .. Done')
        await self.save_queue('rss_queue.json')


    ###################################################
    # Handle Startup          
    ###################################################

    def setup_RSS(self):
        # load private data 
        data = utility.get_private_data()

        raw_data = data.get('news_channel_id')
        if raw_data is None:
            print('[RSSHandler] - No news channel ID found')
            return None
        else:
            try:
                int(raw_data)
            except ValueError:
                print('[RSSHandler] - Invalid news channel ID')
                return None
        return int(data.get('news_channel_id'))

    @commands.Cog.listener()
    async def on_ready(self):
        print('[RSSHandler] - RSS Setup .. ')

        async with self.bot.state.fantasy_query_lock:
            utility.init_memlist(self.bot.fantasy_query.get_teams())
            print('[RSSHandler] - Initialize Member List')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        print('[RSSHandler] - Cog Unload')
        self.poll_rss.cancel()
        self.bot.loop.create_task(self.save_queue())


async def setup(bot):
    await bot.add_cog(RSSHandler(bot))