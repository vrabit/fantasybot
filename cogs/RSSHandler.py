import discord
from discord.ext import tasks, commands

from pathlib import Path
import asyncio
import json
import os
from collections import deque
from yfpy.models import Team
import feedparser

import utility


class RSSHandler(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        self.rssURL = 'https://www.rotowire.com/rss/news.php?sport=NFL'
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
        print('[RSSHandler] - Saving Feed Queue')
        async with self.feed_queue_lock:
            serialized_feed_queue = list(self.feed_queue)
            await self.bot.state.persistent_manager.write_json(filename = self._rss_queue_filename, data=serialized_feed_queue)
        print('[RSSHandler] - Done')


    async def load_queue(self):
        feed_queue = await self.bot.state.persistent_manager.load_json(filename = self._rss_queue_filename)
        return deque(feed_queue)

    async def fetch_rss(self,session,url):
        print('[RSSHandler] - Fetching RSS')
        async with session.get(url) as response:
            response_text = await response.text()
            return response_text


    async def send_rss(self,value):
        print('[RSSHandler] - Sending RSS')
        async with self.bot.state.news_channel_id_lock:
            local_id = self.bot.state.news_channel_id
        
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
        await message.create_thread(name=title, auto_archive_duration=1440)


    async def verify_news_channel(self):
        async with self.bot.state.news_channel_id_lock:
            self.bot.state.news_channel_id = self.bot.state.news_channel_id or await self.setup_RSS()

            if self.bot.state.news_channel_id is None:
                print('[RSSHandler] - No news channel ID found within private_data.json')
                return False
            else:
                print(f'[RSSHandler] - News channel ID set to {self.bot.state.news_channel_id}')
                return True


    @tasks.loop(minutes=10)
    async def poll_rss(self,url='https://www.rotowire.com/rss/news.php?sport=NFL'):

        channel_set = await self.verify_news_channel()
        if not channel_set:
            print('[RSSHandler][Poll_RSS] - News channel not set')
            return

        print('[RSSHandler][Poll_RSS] - Started')
        loaded_queue = await self.load_queue()
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
            print('[RSSHandler] - No news channel ID found within private_data.json')
            return None
        else:
            try:
                int(raw_data)
            except ValueError:
                print('[RSSHandler] - Invalid news channel ID')
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
            print(f'[RSSHandler][init_memlist] - Error: {e}')
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
        while self.bot.state.fantasy_query is None:
            asyncio.sleep(1)   


    @commands.Cog.listener()
    async def on_ready(self):
        await self.wait_for_fantasy()
        print('[RSSHandler] - RSS Setup .. ')

        async with self.bot.state.fantasy_query_lock:
            team_list:list[Team] =self.bot.state.fantasy_query.get_teams()

        await self.update_memlist(team_list)

        self.poll_rss.start()
        self._ready = True
        print('[RSSHandler] - Ready')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        print('[RSSHandler] - Cog Unload')
        self.poll_rss.cancel()
        self.bot.loop.create_task(self.save_queue())


async def setup(bot):
    await bot.add_cog(RSSHandler(bot))