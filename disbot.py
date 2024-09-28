import discord
from discord.ext import tasks, commands

import json
import os
from pathlib import Path

from yfpy.query import YahooFantasySportsQuery
from yfpy import Data

from fantasy import fantasyQuery
import utility

import signal
import aiohttp
import asyncio
import feedparser
from collections import deque



current_dir = Path(__file__).parent
emb_color = discord.Color.from_rgb(225, 198, 153)
emb_color_lock = asyncio.Lock()

# RSS constants 
session = None
session_lock = asyncio.Lock()
rssURL = 'https://www.rotowire.com/rss/news.php?sport=NFL'
rssURL_lock = asyncio.Lock()
update_interval = 600.0
update_interval_lock = asyncio.Lock()

MAX_QUEUE = 5
RSS_QUEUE_FILE = 'rss_queue.json'
feed_queue = deque(maxlen=MAX_QUEUE)
feed_queue_lock = asyncio.Lock()

###################################################
# Setup discord bot          
###################################################

with open(current_dir / 'discordauth'/ 'private.json', 'r') as file:
    data = json.load(file)

token = data.get('discord_token')
channel_id = int(data.get('channel_id'))
channel_id_lock = asyncio.Lock()

bot = commands.Bot(command_prefix= "$", intents = discord.Intents.all())


###################################################
# Setup yahoo api object           
###################################################

def init_fantasy():
    # set directory location of private.json for authentication
    auth_dir = current_dir / 'yfpyauth' 

    # set target directory for data output
    # data_dir = current_dir / "output"

    # create YFPY Data instance for saving/loading data
    #   data = Data(data_dir)

    with open(current_dir / 'yfpyauth' / 'config.json', 'r') as file:
        config_data = json.load(file)

    with open(current_dir / 'yfpyauth' / 'private.json') as file:
        private_data = json.load(file)

    yahoo_query = YahooFantasySportsQuery(
        auth_dir,
        config_data.get('league_id'),
        config_data.get('game_code'),
        game_id = config_data.get('game_id'),
        offline=False,
        all_output_as_json_str=False,
        consumer_key=private_data.get('consumer_key'),
        consumer_secret=private_data.get('consumer_secret')
    )

    return yahoo_query

# Create object to retreive data from yahoo api
fantasy_query = fantasyQuery(init_fantasy())

###################################################
# Exit         
###################################################

async def close_session():
    global session
    async with session_lock:
        if session:
            asyncio.run(session.close())

def handle_exit(signal_received, frame):
    bot.loop.create_task(close_session())


    bot.loop.create_task(save_queue())
    print(f'\nSignal {signal_received}.')
    print(f'Current Function: {frame.f_code.co_name}')
    print(f'Line number: {frame.f_lineno}\n')
    exit(0)

signal.signal(signal.SIGINT,handle_exit)
signal.signal(signal.SIGTERM,handle_exit)

###################################################
# RSS Helpers          
###################################################

async def save_queue(filename='rss_queue.json'):
    global feed_queue

    async with feed_queue_lock:
        with open(current_dir / 'persistent_data' / filename, 'w') as file:
            json.dump(list(feed_queue), file, indent = 4)

async def load_queue(filename='rss_queue.json'):
    if not os.path.exists(current_dir / 'persistent_data' / filename):
        return deque(maxlen=5)
    else:
        with open(current_dir / 'persistent_data' / filename, 'r') as file:
            entries = json.load(file)
            return deque(entries, maxlen=5)

async def fetch_rss(session,url):
    async with session.get(url) as response:
        response_text = await response.text()
        return response_text

async def send_rss(value):
    global channel_id
    async with channel_id_lock:
        local_id = channel_id
    
    channel = bot.get_channel(local_id)
    title = next(iter(value))
    print(title)
    detail=value[title][0]
    print(detail)
    page_url=value[title][1]
    print(page_url)

    async with emb_color_lock:
        async with rssURL_lock:
            embed = discord.Embed(title = title, url=page_url, description = '', color = emb_color)

    embed.add_field(name = '', value=detail)
    message = await channel.send(embed = embed)
    thread = await message.create_thread(name=title, auto_archive_duration=1440)

    

@tasks.loop(minutes=15)
async def poll_rss(url='https://www.rotowire.com/rss/news.php?sport=NFL'):
    global feed_queue
    global session

    loaded_queue = await load_queue('rss_queue.json')
    async with feed_queue_lock:
        feed_queue = loaded_queue
    async with session_lock:
        if not session:
            session = aiohttp.ClientSession()

    response = await fetch_rss(session,url)
    content = feedparser.parse(response)
    async with feed_queue_lock:
        for entry in content.entries:    
            if len(feed_queue) == 0:
                await send_rss({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                feed_queue.append({entry.get('title'):(entry.get('summary'),entry.get('link'))})
            else:
                found = False
                for dict_entry in feed_queue:
                    if entry.get('title') in dict_entry:
                        found = True
                        break
                if not found:
                    await send_rss({entry.get('title'):(entry.get('summary'),entry.get('link'))})
                    feed_queue.append({entry.get('title'):(entry.get('summary'),entry.get('link'))})

    await save_queue('rss_queue.json')

###################################################
# Discord Events          
###################################################

@bot.event
async def on_ready():
    utility.init_memlist(fantasy_query.get_teams())
    if not poll_rss.is_running():
        poll_rss.start()
        print('\nPolling Started')
    print('ready!')

@bot.event
async def on_close():
    global session
    async with session_lock:
        if session:
            await session.close()


###################################################
# Discord Commands          
###################################################

@bot.command()
async def discord_info(ctx, *arg):
    await ctx.send(f' guild: {ctx.guild} \n message: {ctx.message.channel.name} \n author: @{ctx.author}')

def check_user_exists(user):
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    for i in range(len(members)):
        if 'discord_id' in members[i] and members[i]['discord_id'] == user:
            return True
    return False

@bot.command()
async def exists(ctx, arg1 , arg2):
    mentions_list = ctx.message.raw_mentions
    response = 'Members: '
    if len(mentions_list) != 0:
        existing_list = []
        for user in mentions_list:
            exists = check_user_exists(user)
            if exists:
                existing_list.append(user)
        if len(existing_list) != 0:
            response += utility.list_to_mention(mentions_list)
            await ctx.send(response)
        else:
            await ctx.send('Cant find record of users.')

    else:
        await ctx.send('Try mentioning a user.')

@bot.command()
async def fantasy_info(ctx):
    fan_league = fantasy_query.get_league()

    async with emb_color_lock:
        embed = discord.Embed(title = fan_league['league'].name.decode('utf-8'), url=fan_league['league'].url,description = 'Fantasy participants and IDs', color = emb_color ) 
    embed.set_thumbnail(url = fan_league['league'].logo_url)
    
    teams = fantasy_query.get_teams()
    for team in teams:
        embed.add_field(name = team.name.decode("utf-8"), value = "Team ID: " + str(team.team_id))
    
    await ctx.send(embed=embed)

@bot.command()
async def info(ctx):
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    fan_league = fantasy_query.get_league()
    embed = discord.Embed(title = fan_league['league'].name.decode('utf-8'), url=fan_league['league'].url,description = 'Current Yahoo and Discord Connections', color = emb_color ) 
    embed.set_thumbnail(url = fan_league['league'].logo_url)

    for i in range(len(members)):
        dis_id = members[i].get('discord_id')
        if dis_id is None:
            val = f'Team ID: {members[i].get('id')} \nTag: None'
        else:
            val = f'Team ID: {members[i].get('id')} \nTag: {utility.id_to_mention(members[i].get('discord_id'))}'
        embed.add_field(name = members[i].get('name'), value = val, inline=False)

    await ctx.send(embed = embed)

@bot.command()
async def bind(ctx, arg):
    discord_id = ctx.author.id

    value = utility.arg_to_int(arg)

    if value != None and (value >= 1 or value <= 10):
        utility.bind_discord(value,discord_id)
        await ctx.send(f'Team ID: {value} bound to Discord ID: {utility.id_to_mention(discord_id)}')
    else:
        await ctx.send('Integer between 1 - 10')

@bot.command()
async def bind_other(ctx,*args):
    mention = ctx.message.raw_mentions
    if len(args) != 2 or len(mention) != 1:
        await ctx.send('Expected: Tag, ID')
    else:
        discord_id = utility.arg_to_int(mention[0])
        value = utility.arg_to_int(args[1])

        #member = ctx.guild.get_member(int(discord_id))
        #print(member.id)
        if value != None and (value >= 1 or value <= 10):
            utility.bind_discord(value,discord_id)
            await ctx.send(f'Team ID: {value} bound to Discord ID: {utility.id_to_mention(discord_id)}')
        else:
            await ctx.send('Integer between 1 - 10')

@bot.command()
async def set_channel(ctx):
    global channel_id
    async with channel_id_lock:
        channel_id = ctx.channel.id
    await ctx.send('Channel Set.')

@bot.command()
async def chump(ctx,*arg):
    fantasy_league = fantasy_query.get_league()['league']

    if len(arg) != 1:
        week = fantasy_league.current_week
    else:
        week = utility.arg_to_int(arg[0])

    # search for lowerst points
    current_lowest = -1
    matchups_list = fantasy_query.get_scoreboard(week).matchups
    for i in range(len(matchups_list)):
        team_list = matchups_list[i].teams
        
        for team in team_list:
            if current_lowest == -1:
                current_lowest = team.team_points.total
                lowest_id = team.team_id
                lowest_url = team.url
                lowest_name = team.name
                logo_url = team.team_logos[0].url
            
            elif team.team_points.total < current_lowest:
                current_lowest = team.team_points.total
                lowest_id = team.team_id
                lowest_url = team.url
                logo_url = team.team_logos[0].url
    
    
    embed = discord.Embed(title = f'Week {week} Chump', url = fantasy_league.url, description = f'Total Pts: {current_lowest}', color = emb_color)
    embed.set_thumbnail(url = logo_url)

    # use lowest_id to mention discord user 
    discord_user = utility.teamid_to_discord(lowest_id)
    member = ctx.guild.get_member(int(discord_user))
    if discord_user is not None:
        embed.set_author(name = member.display_name, url=lowest_url, icon_url = member.display_avatar.url)

    # get and display loser's roster
    player_list = fantasy_query.get_team_roster(lowest_id,week).players

    # create lists for formatting
    starting_list = []
    bench_list = []
    defense_list = []
    for i in range(len(player_list)):
        if player_list[i].selected_position.position == 'BN':
            bench_list.append(player_list[i].player_id)
        elif player_list[i].selected_position.position == 'DEF':
            defense_list.append(player_list[i].player_id)
        else:
            starting_list.append(player_list[i].player_id)

    # populate the fields
    for player in starting_list:
        team_stats = fantasy_query.team_stats(player,week)
        embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
    
    for player in defense_list:
        team_stats = fantasy_query.team_stats(player,week)
        embed.add_field(name = f'{team_stats.name.full}', value = f'{team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
    
    embed.add_field(name = '\u200b', value = '\u200b')  
    for player in bench_list:
        team_stats = fantasy_query.team_stats(player,week)
        embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)   
    
    embed.set_footer(text = lowest_name.decode('utf-8'))
    await ctx.send(embed = embed)

# expects week as arg, defaults to current week
@bot.command()
async def matchups(ctx,*arg):
    
    if len(arg) != 1:
        week = fantasy_query.get_league()['league'].current_week
    else:
        week = utility.arg_to_int(arg[0])

    #print(fantasy_query.get_scoreboard(week))
    fan_league = fantasy_query.get_league()

    async with emb_color_lock:
        embed = discord.Embed(title = f'Week {week} Matchups', url=fan_league['league'].url, description = '', color = emb_color)
    if week is not None:
        matchups_list = fantasy_query.get_scoreboard(week).matchups
        for i in range(len(matchups_list)):
            team_list = matchups_list[i].teams
            print(matchups_list)
            
            team1 = team_list[0]
            team2 = team_list[1]
            embed.add_field(name = team1.name.decode('utf-8') ,\
                            value = utility.to_blue_text(f'{team1.points:5.2f}          {team1.team_projected_points.total:5.2f}') + f'WP:  {(team1.win_probability*100):3.0f}%', inline = True)
            embed.add_field(name = team2.name.decode('utf-8') ,\
                            value = utility.to_blue_text(f'{team2.points:5.2f}          {team2.team_projected_points.total:5.2f}') + f'WP:  {(team2.win_probability*100):3.0f}%', inline = True)
            embed.add_field(name = '\u200b', value = '\u200b')        
        embed.set_footer(text='Current Points - Projected Points')
        await ctx.send(embed = embed)

@bot.command()
async def player(ctx,*args):
    name = utility.list_to_str(args)
    player_id = fantasy_query.get_player_id(name)

    # weekly stats
    player = fantasy_query.get_player_stats(player_id)
    week = fantasy_query.get_league()['league'].current_week
    team_stats = fantasy_query.team_stats(player_id,week)

    async with emb_color_lock:
        embed = discord.Embed(title = f'{name}', url=player.url, description = f'#{player.uniform_number}, {player.display_position}, {player.editorial_team_full_name}', color = emb_color)
    embed.set_thumbnail(url = player.image_url)

    if player.has_player_notes:
        embed.add_field(name = 'Status',value =utility.to_red_text(f'{player.status_full} {player.injury_note}'),inline=True)

    embed.add_field(name = 'Points', value = utility.to_block(team_stats.player_points.total), inline=True)

    # season points
    season_league = fantasy_query.get_league_stats(player_id)['league']
    season_stats = season_league.players[0]
    embed.add_field(name = 'Season Pts', value = utility.to_block(season_stats.player_points.total))
    embed.add_field(name = '\u200b', value = '\u200b', inline= False) 

    # footer
    ownership_result = fantasy_query.get_ownership(player_id)['league']  
    if len(ownership_result.players[0].ownership.teams) != 0:
        embed.set_footer(text = 'Manager: ' + ownership_result.players[0].ownership.teams[0].name.decode('utf-8'))
    
    # List Stats
    stats_list = team_stats.player_stats.stats
    for i in range(len(stats_list)):
        embed.add_field(name = fantasy_query.stat_dict.get(str(stats_list[i].stat_id)), value = utility.to_block(f'{stats_list[i].value:3.1f}'), inline = True)

    await ctx.send(embed=embed)

@bot.command()
async def recent_reports(ctx):
    embed = discord.Embed(title = f'Recent Reports', url = rssURL, description = '')

    count = 1
    for entry in feed_queue:
        embed.add_field(name = f'{entry}', value = '', inline = False)
        count += 1

@bot.command()
async def leaderboard(ctx):
    standings = fantasy_query.get_all_standings(10)
    sorted_standings = sorted(standings, key = lambda tup: int(tup[1].rank))

    # load names 
    players_dict_list = utility.load_members()
    embed = discord.Embed(title = f'Current Rankings', url='', description = '')
    for players in sorted_standings:
        current_player = players_dict_list[players[0]-1]

        record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
        rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
        points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
        points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
        streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

        formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
        embed.add_field(name = f'{current_player['name']} {record}',value = utility.to_block(formated),inline = False)

    await ctx.send(embed = embed)

@bot.command()
async def points(ctx):
    standings = fantasy_query.get_all_standings(10)
    sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_for), reverse = True)

    # load names 
    players_dict_list = utility.load_members()
    embed = discord.Embed(title = f'Current Rankings', url='', description = '')
    for players in sorted_standings:
        current_player = players_dict_list[players[0]-1]

        record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
        rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
        points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
        points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
        streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

        formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
        embed.add_field(name = f'{current_player['name']} {record}',value = utility.to_block(formated),inline = False)

    await ctx.send(embed = embed)

@bot.command()
async def wrecked(ctx):
    standings = fantasy_query.get_all_standings(10)
    sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_against), reverse = True)

    # load names 
    players_dict_list = utility.load_members()
    embed = discord.Embed(title = f'Current Rankings', url='', description = '')
    for players in sorted_standings:
        current_player = players_dict_list[players[0]-1]

        record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
        rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
        points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
        points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
        streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

        formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
        embed.add_field(name = f'{current_player['name']} {record}',value = utility.to_block(formated),inline = False)

    await ctx.send(embed = embed)

@bot.command()
async def cream_of_the_crop(ctx):
    pass

@bot.command()
async def test(ctx, *args):
    name = utility.list_to_str(args)
    player_id = fantasy_query.get_league_transactions()
    print(player_id)


@bot.command()
async def game_test(ctx):
    print(len(fantasy_query.get_game()['game'].players))


###################################################
# Error Handling          
###################################################
@matchups.error
async def matchups_error(ctx,error):
    print('$matchups called with invalid arguments - '+ str(error))


@player.error
async def player_error(ctx,error):
    await ctx.send(utility.to_block("You should learn how to spell."))

'''
@chump.error
async def chump_error(ctx,error):
    await ctx.send(utility.to_block('Select a valid week.'))
'''
bot.run(token)