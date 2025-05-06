import discord
from discord.ext import  commands

from pathlib import Path

import os
import json

import signal
import asyncio
import aiohttp 

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


class BotState:
    def __init__(self,guild_id:int = None, guild:discord.Object = None):
        # Shared resources and locks
        self.fantasy_query = None
        self.fantasy_query_lock = asyncio.Lock()
        self.session = None
        self.session_lock = asyncio.Lock()
        self.guild_id = guild_id
        self.guild = guild


bot.state = BotState(guild_id=guild_id, guild=guild)


async def setup_session():
    async with bot.state.session_lock:
        print('[Main_Setup] - aiohttp Session Started')
        bot.state.session = aiohttp.ClientSession()


async def close_session():
    async with bot.state.session_lock: 
        print('[Main_Setup] - aiohttp Session Closed')   
        await bot.state.session.close()
        bot.state.session = None


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
    print('[Main_Setup] - Cleared global commands.')

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def clear_guild_commands(ctx:commands.Context)->None:
    ctx.bot.tree.clear_commands(guild=ctx.guild)
    print('[Main_Setup] - Cleared guild commands.')

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx:commands.Context)->None:
    try:
        commands = await ctx.bot.tree.sync(guild=ctx.guild)
        print(f"[Main_Setup] - {len(commands)} Commands synced to guild: {ctx.guild.id}")
        await ctx.send(f"Synced the tree.")
    except discord.HTTPException as e:
        print(f"[Main_Setup] - HTTPException: Failed to sync commands for guild {ctx.guild.id} due to an HTTP error: {e}")
    except discord.CommandSyncFailure as e:
        print(f"[Main_Setup] - CommandSyncFailure: Command sync failed for guild {ctx.guild.id} - possibly invalid command data: {e}")
    except discord.Forbidden:
        print(f"[Main_Setup] - Forbidden: Bot lacks the 'applications.commands' scope for guild {ctx.guild.id}. Check permissions.")
    except discord.MissingApplicationID:
        print("[Main_Setup] - MissingApplicationID: Bot is missing an application ID. Ensure it's set properly.")
    except discord.TranslationError as e:
        print(f"[Main_Setup] - TranslationError: A translation issue occurred while syncing commands: {e}")
    


@bot.event
async def on_ready():
    try:
        await bot.tree.sync(guild=guild)
        print(f'[Main_Setup] - Synced commands to guild: {guild.id}')
    except discord.HTTPException as e:
        print(f"[Main_Setup] - HTTPException: Failed to sync commands for guild {guild.id} due to an HTTP error: {e}")
    except discord.CommandSyncFailure as e:
        print(f"[Main_Setup] - CommandSyncFailure: Command sync failed for guild {guild.id} - possibly invalid command data: {e}")
    except discord.Forbidden:
        print(f"[Main_Setup] - Forbidden: Bot lacks the 'applications.commands' scope for guild {guild.id}. Check permissions.")
    except discord.MissingApplicationID:                    
        print("[Main_Setup] - MissingApplicationID: Bot is missing an application ID. Ensure it's set properly.")
    except discord.TranslationError as e:
        print(f"[Main_Setup] - TranslationError: A translation issue occurred while syncing commands: {e}")

    print('[Main_Setup] - Bot is ready.')
    pass


###################################################
# Exit         
###################################################

async def shutdown():
    try:
        await bot.close()
    except Exception as e:
        print ('[Main_Setup] - Error during shutdown: {e}')

def handle_exit(signal_received, frame):
    print(f'\n[Main_Setup] - Signal {signal_received}.')
    print(f'[Main_Setup] - Current Function: {frame.f_code.co_name}')
    print(f'[Main_Setup] - Line number: {frame.f_lineno}\n')
    
    bot.loop.create_task(close_session())
    bot.loop.create_task(shutdown())

# Register exit definitions
signal.signal(signal.SIGINT,handle_exit)
signal.signal(signal.SIGTERM,handle_exit)

async def load_Test():
    for filename in os.listdir('./cogs'):
        if filename.startswith('MaintainFantasy') or filename.startswith('RSS'):
            print(f'[Main_Setup] - Loaded {filename}')
            await bot.load_extension(f'cogs.{filename[:-3]}')

async def load_extensions():
    # load all cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('py') and not filename.startswith('__'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            print(f'[Main_Setup] - Loaded {filename}')


async def setup_hook():
    print(f'[Main_Setup] - {bot.tree.get_commands(guild=guild)}')
    await setup_session()
    await load_extensions()

bot.setup_hook = setup_hook
bot.run(token)