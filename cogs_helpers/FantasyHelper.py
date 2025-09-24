import discord

from datetime import datetime, date
from yfpy.models import GameWeek

import logging
logger = logging.getLogger(__name__)

_week_dates_filename = 'week_dates.json'


###################################################
# load week dates
###################################################

async def construct_date_list(gameweek_list:list[GameWeek]) -> dict:
    """
    Constructs a dictionary of game week dates from the gameweek list.
        
        Args:
            gameweek_list (list): List of GameWeek.

        Returns:
            dict: Dictionary with game week numbers as keys and start/end dates as values.
    """
    dates_dict = {}
    for gameweek in gameweek_list:
        current_entry = [gameweek.start,gameweek.end]
        dates_dict[gameweek.week] = current_entry

    return dates_dict


async def load_week_dates(bot, week_dates_filename:str = _week_dates_filename) -> dict:
    exists = await bot.state.persistent_manager.path_exists(filename=week_dates_filename)
    if not exists:
        async with bot.state.fantasy_query_lock:
            dates_dict = await construct_date_list(bot.state.fantasy_query.get_game_weeks_by_game_id())
        await bot.state.persistent_manager.write_json(filename=week_dates_filename, data=dates_dict)
        logger.info("[FantasyHelper] - Week Dates File Created.")

    loaded_dates = await bot.state.persistent_manager.load_json(filename=week_dates_filename)
    logger.info("[FantasyHelper] - Week Dates File Loaded.")
    return loaded_dates


async def get_current_week_dates(bot, week:int, week_dates_filename:str = _week_dates_filename) -> tuple[datetime,datetime]:
    all_dates = await load_week_dates(bot=bot, week_dates_filename=week_dates_filename)
    current_week_dates = all_dates.get(str(week))
    
    if current_week_dates is None:
        raise ValueError('Current week dates not found.')

    start_date:datetime = datetime.strptime(current_week_dates[0], '%Y-%m-%d')
    end_date:datetime = datetime.strptime(current_week_dates[1], '%Y-%m-%d')
    return start_date, end_date


###################################################################
# season checks
###################################################################

async def season_over(fantasy_league) -> bool:
    today_obj = date.today()
    season_end_obj = datetime.strptime(fantasy_league.end_date, '%Y-%m-%d').date()
    if today_obj > season_end_obj:
        return True
    return False


async def season_started(fantasy_league) -> bool:
    today_obj = date.today()
    season_start_obj = datetime.strptime(fantasy_league.start_date, '%Y-%m-%d').date()
    if today_obj < season_start_obj:
        return False
    return True


###################################################################
# Roles
###################################################################

async def create_role(guild:discord.Guild, role_name:str, color:discord.Color):
    role = await guild.create_role(
        name=role_name,
        colour=color,
        hoist=True,
        mentionable=True,
        reason=f'Created {role_name} within {guild.name} role for FantasyBot',
    )

    bot_member = guild.me
    bot_top_role = max(bot_member.roles, key=lambda r: r.position)
    new_position = bot_top_role.position - 1

    await guild.edit_role_positions(positions={role: new_position})


async def get_member_by_id(guild:discord.Guild, user_id:int):
    member:discord.Member = guild.get_member(user_id)

    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except Exception as e:
            logger.error(f'[FantasyHelper][get_member_by_id] - Error:{e}')
            return None
    return member


async def remove_role_members_by_guild(guild:discord.Guild, role_name:str):
    role = discord.utils.get(guild.roles, name = role_name)
    logger.info(f'[FantasyHelper][remove_role_members_by_guild] - Removing {role_name} role from members.')
    if role is None:
        logger.warning('[FantasyHelper][remove_role_members] - Role doesn\'t exist.')
        return
    
    async for member in guild.fetch_members():
        if role in member.roles:
            logger.info(f'[FantasyHelper][remove_role_members_by_guild] - Removing {role_name} from {member.id}')
            await member.remove_roles(role)


async def remove_role_members_by_channel(channel:discord.TextChannel, role_name:str):
    guild:discord.Guild = channel.guild
    role = discord.utils.get(guild.roles, name = role_name)
    if role is None:
        logger.warning('[FantasyHelper][remove_role_members] - Role doesn\'t exist.')
        return

    if role is not None:
        for member in role.members:
            await member.remove_roles(role)
        

async def assign_role_by_guild(guild:discord.Guild, discord_member_id:int, role_name:str, role_color:discord.Color):
    roles = guild.roles
    role:discord.Role = discord.utils.get(roles, name = role_name)
    if role is None:
        await create_role(guild, role_name, role_color)
    
    member:discord.Member = await get_member_by_id(guild, int(discord_member_id))
    logger.info(f"[FantasyHelper][assign_role_by_guild] - Using {guild.name} to assign {role_name} to {member.name}.")
    if member is None:
        logger.warning('[FantasyHelper][assign_role_by_guild] - Failed to fetch discord member from discord_id.')
        return

    try:
        await member.add_roles(role)
        logger.info(f'[FantasyHelper][assign_role_by_guild] - {member.display_name} assigned {role_name}')
    except discord.Forbidden:
        logger.error(f'[FantasyHelper][assign_role_by_guild] - Do not have the necessary permissions to assign {role_name} role')
    except discord.HTTPException as e:
        logger.error(f'[FantasyHelper][assign_role_by_guild] - Failed to assign {role_name} role. Error: {e}')


async def assign_role_by_channel(channel:discord.TextChannel, discord_member_id:int, role_name:str, role_color:discord.Color):
    guild:discord.Guild = channel.guild
    roles = guild.roles
    role:discord.Role = discord.utils.get(roles, name = role_name)
    if role is None:
        await create_role(guild, role_name, role_color)
    
    member:discord.Member = await get_member_by_id(guild, int(discord_member_id))
    logger.info(f"[FantasyHelper][assign_role_by_channel] - Using {channel.name} to assign {role_name} to {member.name}.")
    if member is None:
        logger.warning('[FantasyHelper][assign_role_by_channel] - Failed to fetch discord member from discord_id.')
        return

    try:
        await member.add_roles(role)
        logger.info(f'[FantasyHelper][assign_role_by_channel] - {member.display_name} assigned {role_name}')
    except discord.Forbidden:
        logger.error(f'[FantasyHelper][assign_role_by_channel] - Do not have the necessary permissions to assign {role_name} role')
    except discord.HTTPException as e:
        logger.error(f'[FantasyHelper][assign_role_by_channel] - Failed to assign {role_name} role. Error: {e}')