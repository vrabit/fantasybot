import discord
from discord.ext import  commands

from pathlib import Path

from yfpy.models import League

import os
from dotenv import load_dotenv

import signal
import asyncio
import aiohttp 

import file_manager


current_dir = Path(__file__).parent


# Load environment variables from .env files
load_dotenv(current_dir / 'yfpyauth' / ".env.config")
load_dotenv(current_dir / 'yfpyauth' / '.env.private')
load_dotenv(current_dir / 'discordauth' / '.env.discord')


###################################################
# Setup discord bot          
###################################################

# Setup Bot
token = os.getenv('DISCORD_TOKEN')
guild_id = int(os.getenv('GUILD_ID'))
guild = discord.Object(id=guild_id)
app_id = int(os.getenv('APP_ID'))

print(type(guild))

# Set up the bot with all intents
intents = discord.Intents.default()
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

        # colors
        self.emb_color = discord.Color.from_rgb(225, 198, 153) # default
        self.winner_color = discord.Color.from_rgb(55, 255, 119) # green
        self.loser_color = discord.Color.from_rgb(154, 18, 26) # red
        
        # set channels
        self.news_channel_id = None
        self.news_channel_id_lock = asyncio.Lock()
        self.slaps_channel_id = None
        self.slaps_channel_id_lock = asyncio.Lock()
        self.transactions_channel_id = None
        self.transactions_channel_id_lock = asyncio.Lock()
        self.league: League = None
        self.league_lock = asyncio.Lock()
        
        # file managers
        self.persistent_manager = file_manager.PersistentManager()
        self.recap_manager = file_manager.RecapManager()
        self.discord_auth_manager = file_manager.DiscordAuthManager()


bot.state = BotState(guild_id=guild_id, guild=guild)


###################################################
# RSS Setup         
###################################################

async def setup_session():
    async with bot.state.session_lock:
        print('[Main_Setup] - aiohttp Session Started')
        bot.state.session = aiohttp.ClientSession()


async def close_session():
    async with bot.state.session_lock: 
        print('[Main_Setup] - aiohttp Session Closed')   
        await bot.state.session.close()
        bot.state.session = None


######################################################
# Manual Sync Commands
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
        await ctx.send("Synced the tree.")
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
    

###################################################
# Startup         
###################################################

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


###################################################
# Exit         
###################################################

async def shutdown():
    try:
        await bot.close()
    except Exception as e:
        print (f'[Main_Setup] - Error during shutdown: {e}')


def handle_exit(signal_received, frame):
    print(f'\n[Main_Setup] - Signal {signal_received}.')
    print(f'[Main_Setup] - Current Function: {frame.f_code.co_name}')
    print(f'[Main_Setup] - Line number: {frame.f_lineno}\n')
    
    bot.loop.create_task(close_session())
    bot.loop.create_task(shutdown())


# Register exit definitions
signal.signal(signal.SIGINT,handle_exit)
signal.signal(signal.SIGTERM,handle_exit)


###################################################
# Load Cogs and Extensions       
###################################################

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


#######################################################
# Setup Hook and Run Bot
#######################################################

async def setup_hook():
    await setup_session()
    await load_extensions()



bot.setup_hook = setup_hook
bot.run(token)