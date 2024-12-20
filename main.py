import discord
from discord.ext import tasks, commands

import json
from pathlib import Path

from yfpy.query import YahooFantasySportsQuery
from yfpy import Data

from fantasy import fantasyQuery
import os

import signal
import asyncio
import aiohttp 

from collections import deque

import utility

current_dir = Path(__file__).parent


# bot embed color
emb_color = discord.Color.from_rgb(225, 198, 153)


###################################################
# Setup discord bot          
###################################################

data = utility.get_private_data()

# Setup Bot
token = data.get('discord_token')
guild_id = int(data.get('guild_id'))
guild = discord.Object(id=guild_id)
app_id = int(data.get('app_id'))

intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix= "$", intents = intents, application_id = app_id)


# Shared resources and locks
bot.fantasy_query = None
bot.fantasy_query_lock = asyncio.Lock()
bot.session = None
bot.session_lock = asyncio.Lock()
bot.guild_id = guild_id
bot.guild = guild

async def setup_session():
    async with bot.session_lock:
        print('aiohttp Session Started')
        bot.session = aiohttp.ClientSession()

async def close_session():
    async with bot.session_lock: 
        print('aiohttp Session Closed')   
        await bot.session.close()
        bot.session = None

async def reload_extensions():
    # load all cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('py') and not filename.startswith('__'):
            print(f'Loaded {filename}')
            await bot.reload_extension(f'cogs.{filename[:-3]}')


######################################################
# Reload
######################################################

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def clear_global_commands(ctx:commands.Context)->None:
    ctx.bot.tree.clear_commands(guild=guild)
    print('Cleared global commands.')

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def clear_guild_commands(ctx:commands.Context)->None:
    ctx.bot.tree.clear_commands(guild=ctx.guild)
    print('Cleared guild commands.')

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx:commands.Context)->None:
    try:
        commands = await ctx.bot.tree.sync(guild=ctx.guild)
        print(f"{len(commands)} Commands synced to guild: {ctx.guild.id}")
        await ctx.send(f"Synced the tree.")
    except discord.HTTPException as e:
        print(f"HTTPException: Failed to sync commands for guild {ctx.guild.id} due to an HTTP error: {e}")
    except discord.CommandSyncFailure as e:
        print(f"CommandSyncFailure: Command sync failed for guild {ctx.guild.id} - possibly invalid command data: {e}")
    except discord.Forbidden:
        print(f"Forbidden: Bot lacks the 'applications.commands' scope for guild {ctx.guild.id}. Check permissions.")
    except discord.MissingApplicationID:
        print("MissingApplicationID: Bot is missing an application ID. Ensure it's set properly.")
    except discord.TranslationError as e:
        print(f"TranslationError: A translation issue occurred while syncing commands: {e}")
    


@bot.event
async def on_ready():
    #print('Sync bot tree.')
    #bot.tree.clear_commands(guild=guild)


    print(guild)
    pass


###################################################
# Exit         
###################################################

async def shutdown():
    try:
        await bot.close()
    except Exception as e:
        print ('Error during shutdown: {e}')

def handle_exit(signal_received, frame):
    print(f'\nSignal {signal_received}.')
    print(f'Current Function: {frame.f_code.co_name}')
    print(f'Line number: {frame.f_lineno}\n')
    
    bot.loop.create_task(close_session())
    bot.loop.create_task(shutdown())

# Register exit definitions
signal.signal(signal.SIGINT,handle_exit)
signal.signal(signal.SIGTERM,handle_exit)

async def load_Test():
    for filename in os.listdir('./cogs'):
        if filename.startswith('MaintainFantasy') or filename.startswith('RSS'):
            print(f'Loaded {filename}')
            await bot.load_extension(f'cogs.{filename[:-3]}')

async def load_extensions():
    # load all cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('py') and not filename.startswith('__'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            print(f'Loaded {filename}')


async def setup_hook():
    print(bot.tree.get_commands(guild=guild))
    await setup_session()
    await load_extensions()

bot.setup_hook = setup_hook
bot.run(token)