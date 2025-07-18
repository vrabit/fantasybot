import discord
from discord.ext import  commands
from discord.app_commands import CommandSyncFailure

from pathlib import Path
from yfpy.models import League

import os
from dotenv import load_dotenv
from bet_vault.vault import Vault

import signal
import asyncio
import aiohttp 

import file_manager

import logging
import logging.config
import json

import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)


current_dir = Path(__file__).parent

###################################################
# Setup logger     
###################################################

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

config_path = current_dir / "logging_config.json"
with open(config_path, "r") as f:
    config = json.load(f)

logging.config.dictConfig(config)
logger = logging.getLogger(__name__)


###################################################
# Load ENV Variables    
###################################################

# Load environment variables from .env files
load_dotenv(current_dir / 'yfpyauth' / '.env')
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


# Set up the bot with all intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix= "$", intents = intents, application_id = app_id)


class BotState:
    class BotFeatures:
        def __init__(self, settings_manager, 
                     vault_enabled:bool = False, 
                     slaps_enabled:bool = False, 
                     wagers_enabled:bool = False, 
                     news_enabled:bool = False,
                     transactions_enabled:bool = False,
                     log_season_enabled:bool = False
        ):
            
            self.vault_enabled:bool = vault_enabled
            self.slaps_enabled:bool = slaps_enabled
            self.wagers_enabled:bool = wagers_enabled
            self.news_enabled:bool = news_enabled
            self.transactions_enabled:bool = transactions_enabled
            self.log_season_enabled:bool = log_season_enabled

            self.settings_manager = settings_manager
            self.feature_settings_config_filename = "features_config.json"


        def __str__(self):
            return (
                f'BotFeatures\n'
                f'Vault Enabled: {self.vault_enabled}\n'
                f'Slaps Enabled: {self.slaps_enabled}\n'
                f'Wagers Enabled: {self.wagers_enabled}\n'
                f'News Enabled: {self.news_enabled}\n'
                f'Transactions Enabled: {self.transactions_enabled}\n'
                f'Season Log Enabled: {self.log_season_enabled}\n'
            )
        

        async def load_features(self):
            return await self.settings_manager.load_json(filename = self.feature_settings_config_filename)
        

        async def store_features(self, data:dict):
            await self.settings_manager.write_json(filename=self.feature_settings_config_filename, data=data)


        async def enable_wagers(self):
            # All of these features rely on an already configured Yahoo User - Discord User Memberlist 
            settings = await self.load_features()
            settings['vault_enabled'] = True
            settings['wagers_enabled'] = True
            await self.store_features(settings)
            logger.info('[Main][Features] - Vault and Wagers Enabled')


        async def set_vault(self, activate:bool):
            settings = await self.load_features()
            settings['vault_enabled'] = activate
            await self.store_features(settings)
            logger.info('[Main][Features] - Vault Enabled')


        async def set_slap(self, activate:bool):
            settings = await self.load_features()
            settings['slaps_enabled'] = activate
            await self.store_features(settings)
            logger.info('[Main][Features] - SlapChallenge Enabled')


        async def set_wagers(self, activate:bool):
            settings = await self.load_features()
            settings['wagers_enabled'] = activate
            await self.store_features(settings)
            logger.info('[Main][Features] - Wagers Enabled')


        async def set_news(self, activate:bool):
            settings = await self.load_features()
            settings['news_enabled'] = activate
            await self.store_features(settings)
            logger.info('[Main][Features] - News Enabled')


        async def set_transactions(self, activate:bool):
            settings = await self.load_features()
            settings['transactions_enabled'] = activate
            await self.store_features(settings)
            logger.info('[Main][Features] - Transactions Enabled')


        async def set_log(self, activate:bool):
            settings = await self.load_features()
            settings['season_log_enabled'] = activate
            await self.store_features(settings)
            logger.info('[Main][Features] - Season Log Enabled')


        async def setup_features(self):
            settings = await self.load_features()
            self.vault_enabled = settings.get('vault_enabled')
            self.slaps_enabled = settings.get('slaps_enabled')
            self.wagers_enabled = settings.get('wagers_enabled')
            self.news_enabled = settings.get('news_enabled')
            self.transactions_enabled = settings.get('transactions_enabled')
            self.log_season_enabled = settings.get('season_log_enabled')

            logger.info(f"[Main][setup_features] - {self}")


    def __init__(self,guild_id:int = None, guild:discord.Object = None):
        # ready check
        self.memlist_ready_lock = asyncio.Lock()
        self.memlist_ready = False

        # Shared resources and locks
        self.fantasy_query = None
        self.fantasy_query_lock = asyncio.Lock()
        self.session = None
        self.session_lock = asyncio.Lock()
        self.guild_id = guild_id
        self.guild = guild

        # Player Values
        self.trade_value_url = None
        self.trade_value_ready = False
        self.player_values_lock = asyncio.Lock()
        self.value_map_lock = asyncio.Lock()
        self.player_values = None
        self.value_map = None

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
        self.live_manager = file_manager.LiveManager()
        self.settings_manager = file_manager.SettingsManager()
        self.vault_manager = file_manager.VaultManager()

        # shared vault 
        self.vault:Vault = None

        # persistent_manager filenames
        self.player_ids_filename = 'player_ids.csv'
        self.members_filename = 'members.json'
        self.rss_queue_filename = 'rss_queue.json'
        self.player_data_filename = 'player_data.json'
        self.week_dates_filename = 'week_dates.json'
        self.transactions_filename = 'transactions.json'
        self.weekly_funds_filename = "weekly_funds.json"
        self.challenges_filename = 'challenges.json'
        self.trade_transactions_filename = 'trade_transactions.csv'

        # recap_manager filenames
        self.roster_csv = 'roster_value.csv'
        self.matchup_csv = 'matchup_data.csv'

        # recap_manager template filenames
        self.roster_json_template = 'week_{week}_roster.json'
        self.matchup_json_template = "week_{week}_matchup.json"
        self.matchup_standings_template = 'week_{week}_data.csv'

        # discord_auth_manager filenames
        self.private_filename = 'private.json'

        # live_manager filenames
        self.team_info_filename = 'espn_team_info.json'

        # settings_manager filenames
        self.challenge_config_filename = 'challenge_config.json'
        self.trade_value_config_filename = "trade_value_config.json"

        # vault_manager filenames
        self.vault_accounts_filename = 'vault_accounts.json'
        self.vault_slap_contracts_filename = 'vault_slap_contracts.json'
        self.vault_wager_contracts_filename = 'vault_wager_contracts.json'

        # Features
        self.bot_features = self.BotFeatures(settings_manager=self.settings_manager)


bot.state = BotState(guild_id=guild_id, guild=guild)


###################################################
# RSS Setup         
###################################################

async def setup_session():
    async with bot.state.session_lock:
        logger.info('[Main_Setup] - aiohttp Session Started')
        bot.state.session = aiohttp.ClientSession()


async def close_session():
    async with bot.state.session_lock: 
        logger.info('[Main_Setup] - aiohttp Session Closed')   
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
    logger.info('[Main_Setup] - Cleared global commands.')


@bot.command()
@commands.guild_only()
@commands.is_owner()
async def clear_guild_commands(ctx:commands.Context)->None:
    ctx.bot.tree.clear_commands(guild=ctx.guild)
    logger.info('[Main_Setup] - Cleared guild commands.')


@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx:commands.Context)->None:
    try:
        commands = await ctx.bot.tree.sync(guild=ctx.guild)
        logger.info(f"[Main_Setup] - {len(commands)} Commands synced to guild: {ctx.guild.id}")
        await ctx.send("Synced the tree.")
    except discord.HTTPException as e:
        logger.error(f"[Main_Setup] - HTTPException: Failed to sync commands for guild {ctx.guild.id} due to an HTTP error: {e}")
    except discord.Forbidden:   
        logger.error(f"[Main_Setup] - Forbidden: Bot lacks the 'applications.commands' scope for guild {guild.id}. Check permissions.")
    except CommandSyncFailure:
        logger.error("Command sync failed.")
    except discord.DiscordException as e:
        logger.error(f"[Main_Setup] - DiscordException: An error occurred while syncing commands: {e}")
    except Exception as e:
        logger.error(f'Caught error: {e}')


###################################################
# Startup         
###################################################

@bot.event
async def on_ready():
    try:
        await bot.tree.sync(guild=guild)
        logger.info(f'[Main_Setup] - Synced commands to guild: {guild.id}')
    except discord.HTTPException as e:
        logger.error(f"[Main_Setup] - HTTPException: Failed to sync commands for guild {guild.id} due to an HTTP error: {e}")
    except discord.Forbidden:
        logger.error(f"[Main_Setup] - Forbidden: Bot lacks the 'applications.commands' scope for guild {guild.id}. Check permissions.")
    except CommandSyncFailure:
        logger.error("Command sync failed.")
    except discord.DiscordException as e:
        logger.error(f"[Main_Setup] - DiscordException: An error occurred while syncing commands: {e}")
    except Exception as e:
        logger.error(f'Caught error: {e}')
    logger.info('[Main_Setup] - Bot is ready.')


###################################################
# Exit         
###################################################

async def shutdown():
    try:
        await bot.close()
    except Exception as e:
        logger.info(f'[Main_Setup] - Error during shutdown: {e}')


def handle_exit(signal_received, frame):
    logger.info(f'[Main_Setup] - Signal {signal_received}.')
    logger.info(f'[Main_Setup] - Current Function: {frame.f_code.co_name}')
    logger.info(f'[Main_Setup] - Line number: {frame.f_lineno}\n')
    
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
            logger.info(f'[Main_Setup] - Loaded {filename}')
            await bot.load_extension(f'cogs.{filename[:-3]}')


async def load_extensions():
    # load all cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('py') and not filename.startswith('__'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            logger.info(f'[Main_Setup] - Loaded {filename}')


#######################################################
# Setup Hook and Run Bot
#######################################################

async def setup_hook():
    await setup_session()
    await load_extensions()


def main():
    bot.setup_hook = setup_hook
    bot.run(token)

if __name__ == '__main__':
    main()