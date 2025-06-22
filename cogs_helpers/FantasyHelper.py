import asyncio
from datetime import datetime, date, timedelta

import file_manager
from datetime import datetime, timedelta
from yfpy.models import GameWeek


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


async def load_week_dates(bot, persistent_manager:file_manager.BaseFileManager, week_dates_filename:str = _week_dates_filename) -> dict:
    exists = await persistent_manager.path_exists(filename=week_dates_filename)
    if not exists:
        async with bot.state.fantasy_query_lock:
            dates_dict = await construct_date_list(bot.state.fantasy_query.get_game_weeks_by_game_id())
        await persistent_manager.write_json(filename=week_dates_filename, data=dates_dict)

    loaded_dates = await persistent_manager.load_json(filename=week_dates_filename)
    return loaded_dates


###################################################
# 
###################################################


