import discord
from discord.utils import get
from discord import app_commands
from discord.ext import commands

import asyncio
import os
from datetime import date, datetime, time

from pathlib import Path
import logging
logger = logging.getLogger(__name__)

class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent

        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color


    ###################################################
    # Manual Slash Commands        
    ###################################################

    @app_commands.command(name='emote', description='Post an emote')
    @app_commands.describe(emote="emote_name")
    async def emote(self, interaction:discord.Interaction, emote:str):
        await interaction.response.defer()

        emoji = discord.utils.get(interaction.guild.emojis, name=emote)
        if emoji:
            await interaction.followup.send(f"{emoji}")
        else:
            await interaction.followup.send("Emoji not found.")

    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))  
    @app_commands.command(name='top_10', description='Find the top 10 posts in this text channel.')
    async def find_top_posts(self, interaction:discord.Interaction):
        await interaction.response.defer()

        if interaction.guild is None:
            await interaction.followup.send("This command must be used within a text channel.", ephemeral=True)
            return

        channel:discord.TextChannel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Text channel missing.", ephemeral=True)
            return

        # collect the messages
        messages:list[tuple] = []
        async for message in channel.history(limit=30000):
            if not message.reactions:
                continue

            total_reactions = sum(reaction.count for reaction in message.reactions)
            if total_reactions > 10:
                messages.append((message,total_reactions))

        # sort the messages
        messages.sort(key=lambda x: x[1], reverse=True)
        top_posts = messages[:25]

        embed = discord.Embed(title = f'{channel.name} \nTop {len(top_posts)} Posts', url='' ,description = '', color = self.emb_color ) 

        for i, (mess,count) in enumerate(top_posts):
            embed.add_field(name = f'#{i+1}', value = f'{count} Reactions - [Jump to Post]({mess.jump_url})', inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))  
    @app_commands.command(name='top_10_date', description='Find the top 10 posts in this text channel before a given date.')
    @app_commands.describe(month="Month", day="Day", year="Year", limit="Total amount of messages to search. (max=20000)", minimum_reactions="Minimum reactions in a post.")
    async def find_top_posts(self, interaction:discord.Interaction, month:int, day:int, year:int, limit:int, minimum_reactions:int):
        await interaction.response.defer()

        if limit > 20000:
            limit = 20000
        elif limit < 0:
            limit = 10000

        if minimum_reactions < 3:
            minimum_reactions = 3

        try:
            before_date = date(year,month,day)
            before_time = time(0,0,0)
            before_datetime = datetime.combine(before_date, before_time)
        except Exception as e:
            await interaction.followup.send("Invalid date values provided.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.followup.send("This command must be used within a text channel.", ephemeral=True)
            return

        channel:discord.TextChannel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Text channel missing.", ephemeral=True)
            return

        # collect the messages
        messages:list[tuple] = []
        async for message in channel.history(limit=limit, before=before_datetime):
            if not message.reactions:
                continue

            total_reactions = sum(reaction.count for reaction in message.reactions)
            if total_reactions > minimum_reactions:
                messages.append((message,total_reactions))

        # sort the messages
        messages.sort(key=lambda x: x[1], reverse=True)
        top_posts = messages[:25]

        embed = discord.Embed(title = f'{channel.name} \nTop {len(top_posts)} Posts \nbefore {before_datetime.strftime("%A, %B %d, %Y")}', 
                              url='' ,
                              description = f'Limited to {limit} messages.', color = self.emb_color ) 

        for i, (mess,count) in enumerate(top_posts):
            embed.add_field(name = f'#{i+1}', value = f'{count} Reactions - [Jump to Post]({mess.jump_url})', inline=False)

        await interaction.followup.send(embed=embed)


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))  
    @app_commands.command(name='top_10_emoji', description='Find the top 10 posts in this text channel before a given date. Limited to emoji reactions.')
    @app_commands.describe(month="Month", day="Day", year="Year", limit="Total amount of messages to search. (max=20000)", minimum_reactions="Minimum reactions in a post.")
    async def find_top_posts(self, interaction:discord.Interaction, month:int, day:int, year:int, limit:int, minimum_reactions:int, emoji:str):
        await interaction.response.defer()

        if limit > 20000:
            limit = 20000
        elif limit < 0:
            limit = 10000

        if minimum_reactions < 3:
            minimum_reactions = 3

        try:
            before_date = date(year,month,day)
            before_time = time(0,0,0)
            before_datetime = datetime.combine(before_date, before_time)
        except Exception as e:
            await interaction.followup.send("Invalid date values provided.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.followup.send("This command must be used within a text channel.", ephemeral=True)
            return

        channel:discord.TextChannel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Text channel missing.", ephemeral=True)
            return

        # collect the messages
        messages:list[tuple] = []
        async for message in channel.history(limit=limit, before=before_datetime):
            if not message.reactions:
                continue

            emoji_reaction = get(message.reactions, emoji=emoji)
            if emoji_reaction:
                total_reactions = sum(reaction.count for reaction in message.reactions)
                emoji_reactions = emoji_reaction.count
                if total_reactions >= minimum_reactions:
                    messages.append((message, total_reactions, emoji_reactions))


        # sort the messages
        messages.sort(key=lambda x: x[1], reverse=True)
        top_posts = messages[:25]

        embed = discord.Embed(title = f'{channel.name} \nTop {len(top_posts)} Posts \nbefore {before_datetime.strftime("%A, %B %d, %Y")}', 
                              url='' ,
                              description = f'Limited to {limit} messages containing {emoji}.', color = self.emb_color ) 

        for i, (mess,count, emojis) in enumerate(top_posts):
            embed.add_field(name = f'#{i+1}', value = f'{count} Reactions - {emojis} {emoji} Reactions \n[Jump to Post]({mess.jump_url})', inline=False)

        await interaction.followup.send(embed=embed)


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

        logger.error(f"[Miscellaneous] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[Miscellaneous] - Failed to send error message: {e}")


    ###################################################
    # Handle Startup          
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
        self._ready = True
        logger.info('[Miscellaneous] - Initialized Miscellaneous')


    ####################################################
    # Handle Load
    ####################################################

    async def cog_load(self):
        logger.info('[Miscellaneous] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[Miscellaneous] - Cog Unload')


async def setup(bot):
    await bot.add_cog(Miscellaneous(bot))