import discord

from collections import deque
from yfpy.models import Team, Matchup, Player
from difflib import get_close_matches

import utility

################################################################
# Chump Helper - find lowest
################################################################

async def check_if_lower_pts(team:Team, lowest:Team) -> Team:
    if lowest == None:
        lowest = team
    elif team.team_points.total < lowest.team_points.total:
        lowest = team
    return lowest


async def lowest_points_team_list(team_list:list[Team], lowest:Team) -> Team:
    for team in team_list:
        lowest = await check_if_lower_pts(team, lowest)
    return lowest


async def lowest_points_matchup_list(matchups:list[Matchup]) -> Team:
    lowest:Team = None
    for matchup in matchups:
        lowest = await lowest_points_team_list(matchup.teams, lowest)
    return lowest


################################################################
# Champ Helper - find lowest
################################################################

async def check_if_higher_pts(team:Team, highest:Team) -> Team:
    if highest == None:
        highest = team
    elif team.team_points.total > highest.team_points.total:
        highest = team
    return highest


async def highest_points_team_list(team_list:list[Team], highest:Team) -> Team:
    for team in team_list:
        highest = await check_if_higher_pts(team, highest)
    return highest


async def highest_points_matchup_list(matchups:list[Matchup]) -> Team:
    highest:Team = None
    for matchup in matchups:
        highest = await highest_points_team_list(matchup.teams, highest)
    return highest


################################################################
# Chump/Champ Helper - construct starting, bench and defense lists
################################################################

async def init_embed(chimp:str,extra:str, week:int, url, total_points, color, logo_url):
    embed = discord.Embed(
        title = f'Week {week} {chimp}{extra}', 
            url = url, 
            description = f'Total Pts: {total_points}', 
            color = color
        )
    embed.set_thumbnail(url = logo_url)
    return embed


async def add_player_fields(embed:discord.Embed, queue:deque[int], week, state) -> None:
    async with state.fantasy_query_lock:
        while queue:
            id = queue.popleft()
            player_stats:Player = state.fantasy_query.team_stats(id,week)
            embed.add_field(name = f'{player_stats.name.full}',
                            value = (
                                f'#{player_stats.uniform_number}, {player_stats.primary_position}, {player_stats.editorial_team_full_name}\n'
                                f'Total Pts: [{player_stats.player_points.total:4.2f}]({player_stats.url})'
                            ), 
                            inline = False)   


async def add_defense_fields(embed:discord.Embed, queue:deque[int], week, state) -> None:
    async with state.fantasy_query_lock:
        while queue:
            id = queue.popleft()
            player_stats:Player = state.fantasy_query.team_stats(id,week)
            embed.add_field(name = f'{player_stats.name.full}', 
                            value = (
                                f'{player_stats.primary_position}, {player_stats.editorial_team_full_name}\n'
                                f'Total Pts: [{player_stats.player_points.total:4.2f}]({player_stats.url})'),
                            inline = False) 


async def construct_roster_lists(player_list:list[Player]) -> tuple[deque[int], deque[int], deque[int]]:
    # create lists for formatting
    starting_list:deque = deque()
    bench_list:deque = deque()
    defense_list:deque = deque()

    for player in player_list:
        if player.selected_position.position == 'BN':
            bench_list.append(player.player_id)
        elif player.selected_position.position == 'DEF':
            defense_list.append(player.player_id)

        else:
            starting_list.append(player.player_id)
    return starting_list, bench_list, defense_list


################################################################
# matchups helper
################################################################

async def add_matchup_fields_team(team:Team, embed) -> None:
    embed.add_field(
        name = f"{team.name.decode('utf-8')} - Id: {team.team_id}",
        value = (
            f'{utility.to_blue_text(f'{team.points:.2f}{team.team_projected_points.total:>11.2f}')}'  
            f'WP:  {(team.win_probability*100):3.0f}%'
        ),
        inline = True
    )


async def add_matchup_fields_team_list(team_list:list[Team], embed) -> None:
    for team in team_list:
        await add_matchup_fields_team(team, embed)
    embed.add_field(name = '\u200b', value = '\u200b')


async def add_matchup_fields(matchup_list:list[Matchup], embed:discord.Embed) -> None:
    for matchup in matchup_list:
        team_list:list[Team] = matchup.teams
        await add_matchup_fields_team_list(team_list,embed)     
    embed.set_footer(text='Current Points - Projected Points')


################################################################
# player_stats helper
################################################################

async def find_closest_name(player_name, persistent_manager, filename):
    # compare name to playerlist and use closest match for query
    player_list = await persistent_manager.load_simple_csv(filename=filename)

    closest_keys = get_close_matches(player_name,player_list,n=1,cutoff=0.6)
    if len(closest_keys) == 0:
        return None
    
    return closest_keys[0], player_list.get(closest_keys[0])
