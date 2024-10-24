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
import datetime


current_dir = Path(__file__).parent
emb_color = discord.Color.from_rgb(225, 198, 153)
emb_color_lock = asyncio.Lock()

# keep track of active view instances
active_views = []
active_views_lock = asyncio.Lock()

# number of teams
number_of_teams = utility.number_of_teams()

# RSS constants 
session = None
session_lock = asyncio.Lock()
rssURL = 'https://www.rotowire.com/rss/news.php?sport=NFL'
rssURL_lock = asyncio.Lock()
update_interval = 600.0
update_interval_lock = asyncio.Lock()

MAX_QUEUE = 30
RSS_QUEUE_FILE = 'rss_queue.json'
feed_queue = deque(maxlen=MAX_QUEUE)
feed_queue_lock = asyncio.Lock()

# Slap 
loser_role_name = 'King Chump'
denier_role_name = 'Pan'
dave_slap = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExOTZnZ2p6cnRxcHJucXZ4bGtpcThxd3VscWY0ZTFnMzZ3ZDQ0OXMwcSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/VeXiycRe0X4IewK6WY/giphy.gif'
charlie_slap = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExMWgyd3B4eHM0bms3bnloZXIyOWF4aHFqZ3ZsdzJ6cXhtN2Q4ZjZqdyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/V1xyrsMPCewzAoURLh/giphy.gif'
charlie_stare = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExNmlwcTQ4dzcxZWJhcHk5MHpoMXZxbDBpcWJ1bGdtam1xbGprbmZ4ZyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/GhySRlT2q4nj6SSbhC/giphy.gif'
tie_gif = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExbGs0MGJkaHc3YjN5b2p0eGp0NzY3OTkwa2ZpanpmOTVxbDFsOTN0NCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/1Q763R06W61dKBKZuM/giphy.gif'
left_winner = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExNWZ4bW96dmFxN20wbWE3cWRxZXlsbW5obGd2anJxOXRoOTR6Nm9ldCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/aB4piAqj3kbTcz4s08/giphy.gif'
right_winner = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExeGkybnhjZXp6bXhjdzZlZmdtbzJhdGI5OXd2b2x4dDVjZTN0M3cyeiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/G8IW5iQA4yeQ0ig0iJ/giphy.gif'
timeout_gif = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3d4NjExNmFqczAyOGltb2hveXl4OHNlcGdwc2d1eGxsaWRldnNrciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/XKPFjQAYe4l3nLxcr7/giphy.gif'

###################################################
# Setup discord bot          
###################################################

with open(current_dir / 'discordauth'/ 'private.json', 'r') as file:
    data = json.load(file)

token = data.get('discord_token')
channel_id = int(data.get('channel_id'))
channel_id_lock = asyncio.Lock()

news_channel_id = int(data.get('news_channel_id'))
news_id_lock = asyncio.Lock()

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
fantasy_query_lock = asyncio.Lock()

@tasks.loop(minutes=240)
async def refresh_fantasy():
    if not refresh_fantasy.current_loop:
        await asyncio.sleep(240)

    global fantasy_query
    async with fantasy_query_lock:
        # set directory location of private.json for authentication
        auth_dir = current_dir / 'yfpyauth' 

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

        fantasy_query = fantasyQuery(yahoo_query)

###################################################
# Exit         
###################################################

async def close_session():
    global session
    async with session_lock:
        if session:
            await session.close()

def handle_exit(signal_received, frame):
    bot.loop.create_task(close_session())
    bot.loop.create_task(save_queue())

    print(f'\nSignal {signal_received}.')
    print(f'Current Function: {frame.f_code.co_name}')
    print(f'Line number: {frame.f_lineno}\n')
    
    bot.loop.create_task(shutdown())

signal.signal(signal.SIGINT,handle_exit)
signal.signal(signal.SIGTERM,handle_exit)

async def shutdown():
    async with active_views_lock:
        for view in active_views:
            await view.cleanup()

    try:
        await bot.close()
    except Exception as e:
        print ('Error during shutdown: {e}')


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
        return deque(maxlen=MAX_QUEUE)
    else:
        with open(current_dir / 'persistent_data' / filename, 'r') as file:
            entries = json.load(file)
            return deque(entries, maxlen=MAX_QUEUE)

async def fetch_rss(session,url):
    async with session.get(url) as response:
        response_text = await response.text()
        return response_text

async def send_rss(value):
    global news_channel_id
    async with news_id_lock:
        local_id = news_channel_id
    
    channel = bot.get_channel(local_id)
    title = next(iter(value))
    detail=value[title][0]
    page_url=value[title][1]

    async with rssURL_lock:
        embed = discord.Embed(title = title, url=page_url, description = '', color = emb_color)

    embed.add_field(name = '', value=detail)
    message = await channel.send(embed = embed)
    thread = await message.create_thread(name=title, auto_archive_duration=1440)
 

@tasks.loop(minutes=10)
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
    global fantasy_query
    async with fantasy_query_lock:
        utility.init_memlist(fantasy_query.get_teams())

    if not poll_rss.is_running():
        poll_rss.start()
        print('\nPolling Started')
        
    poll_slap.start()
    remove_slap_roles.start()

    refresh_fantasy.start()

    print('ready!')

@bot.event
async def on_close():
    global session
    async with session_lock:
        if session:
            await session.close()

###################################################
# Assign roles         
###################################################

async def get_member_by_id(guild: discord.Guild, user_id: int):
    member = guild.get_member(user_id)

    if member is None:
        member = await guild.fetch_member(user_id)

    return member

async def assign_role(member: discord.Member, role_name:str, channel: discord.TextChannel):
    guild = channel.guild
    roles = guild.roles
    role = discord.utils.get(roles,name = role_name)

    if role is None:
        print('Role doesn\'t exist.')
        return
    
    try:
        await member.add_roles(role)
        print(f'{member.display_name} assigned {role_name}')
    except discord.Forbidden:
        print(f'Do not have the necessary permissions to assign {role_name} role')
    except discord.HTTPException as e:
        print(f'Failed to assign {role_name} role')

async def remove_role_members(role_name:str):
    global channel_id
    async with channel_id_lock:
        local_id = channel_id

    channel = bot.get_channel(local_id)
    guild = channel.guild

    role = discord.utils.get(guild.roles, name = role_name)

    if role is not None:
        for member in role.members:
            await member.remove_roles(role)


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
async def all_commands(ctx):
    command_list = [{'info:':'Team Name / Team ID / Tag'},\
                    {'bind [teamid]:':'Binds current users Discord-tag to Yahoo-Id'},\
                    {'bind_other [discordTag] [teamid]:': 'Binds mentioned user to Yahoo-Id'}, \
                    {'set_channel:': 'Current channel becomes news channel'},\
                    {'chump [week]: ':'Lists lowest score user of the week\nDefaults to current week if not specified'},\
                    {'mvp [week]: ':'Lists highest score user of the week\nDefaults to current week if not specified'},\
                    {'matchups [week]: ':'Lists week matchups, points and projections\nDefaults to current week if not specified'},\
                    {'player [player name]:':'Lists player stats\nExpects complete name as represented in yahoo.'},\
                    {'leaderboard:':'Lists current fantasy standings'},\
                    {'most_points:':'Lists users from highest to lowest season points'},\
                    {'least_points:':'Lists users from lowest to highest season points'},\
                    {'slap':'Challenge a player. Loser gets assigned the chump tag.(FAAB gamble next year???)'}]
    
    embed = discord.Embed(title = 'All Commands', url='', description='',color = emb_color)
    for command in command_list:
        for key, value in command.items():
            embed.add_field(name=key, value=value, inline = False)

    await ctx.send(embed = embed)
    
@bot.command()
async def commands(ctx):
    command_list = [{'chump [week]: ':'Lists lowest score user of the week\nDefaults to current week if not specified'},\
                {'mvp [week]: ':'Lists highest score user of the week\nDefaults to current week if not specified'},\
                {'matchups [week]: ':'Lists week matchups, points and projections\nDefaults to current week if not specified'},\
                {'player [player name]:':'Lists player stats\nExpects complete name as represented in yahoo.'},\
                {'leaderboard:':'Lists current fantasy standings'},\
                {'most_points:':'Lists users from highest to lowest season points'},\
                {'least_points:':'Lists users from lowest to highest season points'}]
    
    embed = discord.Embed(title = 'All Commands', url='', description='',color = emb_color)
    for command in command_list:
        for key, value in command.items():
            embed.add_field(name=key, value=value, inline = False)

    await ctx.send(embed = embed)

@bot.command()
async def fantasy_info(ctx):
    global fantasy_query
    async with fantasy_query_lock:
        fan_league = fantasy_query.get_league()

    async with emb_color_lock:
        embed = discord.Embed(title = fan_league['league'].name.decode('utf-8'), url=fan_league['league'].url,description = 'Fantasy participants and IDs', color = emb_color ) 
    embed.set_thumbnail(url = fan_league['league'].logo_url)
    
    async with fantasy_query_lock:
        teams = fantasy_query.get_teams()
    for team in teams:
        embed.add_field(name = team.name.decode("utf-8"), value = "Team ID: " + str(team.team_id))
    
    await ctx.send(embed=embed)

@bot.command()
async def info(ctx):
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    global fantasy_query
    async with fantasy_query_lock:
        fan_league = fantasy_query.get_league()

    embed = discord.Embed(title = fan_league['league'].name.decode('utf-8'), url=fan_league['league'].url,description = 'Current Yahoo and Discord Connections', color = emb_color ) 
    embed.set_thumbnail(url = fan_league['league'].logo_url)

    for i in range(len(members)):
        dis_id = members[i].get('discord_id')
        if dis_id is None:
            val = f"Team ID: {members[i].get('id')} \nTag: None"
        else:
            val = f"Team ID: {members[i].get('id')} \nTag: {utility.id_to_mention(members[i].get('discord_id'))}"
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

        if value != None and (value >= 1 or value <= 10):
            utility.bind_discord(value,discord_id)
            await ctx.send(f'Team ID: {value} bound to Discord ID: {utility.id_to_mention(discord_id)}')
        else:
            await ctx.send('Integer between 1 - 10')

@bot.command()
async def set_channel(ctx):
    global news_channel_id
    async with news_id_lock:
        news_channel_id = ctx.channel.id
    await ctx.send('Channel Set.')

@bot.command()
async def chump(ctx,*arg):
    global fantasy_query
    async with fantasy_query_lock:
        fantasy_league = fantasy_query.get_league()['league']

    if len(arg) != 1:
        week = fantasy_league.current_week
    else:
        week = utility.arg_to_int(arg[0])

    # search for lowerst points
    current_lowest = -1

    async with fantasy_query_lock:
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

    # check if user exists
    if discord_user is None:
        await ctx.send(utility.to_block(f'{lowest_name.decode('utf-8')} Total Pts: {current_lowest}'))
    else:
        member = ctx.guild.get_member(int(discord_user))
        if discord_user is not None:
            embed.set_author(name = member.display_name, url=lowest_url, icon_url = member.display_avatar.url)


        async with fantasy_query_lock:
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

        async with fantasy_query_lock:
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

@bot.command()
async def mvp(ctx,*arg):
    global fantasy_query
    async with fantasy_query_lock:
        fantasy_league = fantasy_query.get_league()['league']

    if len(arg) != 1:
        week = fantasy_league.current_week
    else:
        week = utility.arg_to_int(arg[0])

    # search for lowerst points
    current_highest = -1
        
    async with fantasy_query_lock:
        matchups_list = fantasy_query.get_scoreboard(week).matchups
    for i in range(len(matchups_list)):
        team_list = matchups_list[i].teams
        
        for team in team_list:
            if current_highest == -1:
                current_highest = team.team_points.total
                highest_id = team.team_id
                highest_url = team.url
                highest_name = team.name
                logo_url = team.team_logos[0].url
            
            elif team.team_points.total > current_highest:
                current_highest = team.team_points.total
                highest_id = team.team_id
                highest_url = team.url
                highest_name = team.name
                logo_url = team.team_logos[0].url
    
    
    embed = discord.Embed(title = f'Week {week} MVP', url = fantasy_league.url, description = f'Total Pts: {current_highest}', color = emb_color)
    embed.set_thumbnail(url = logo_url)

    # use highest_id to mention discord user 
    discord_user = utility.teamid_to_discord(highest_id)

    # check if user exists
    if discord_user is None:
        await ctx.send(utility.to_block(f'{highest_name.decode('utf-8')} Total Pts: {current_highest}'))
    else:
        member = ctx.guild.get_member(int(discord_user))


        if discord_user is not None:
            embed.set_author(name = member.display_name, url=highest_url, icon_url = member.display_avatar.url)

        async with fantasy_query_lock:
            # get and display loser's roster
            player_list = fantasy_query.get_team_roster(highest_id,week).players

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

        async with fantasy_query_lock:
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
        
        embed.set_footer(text = highest_name.decode('utf-8'))
        await ctx.send(embed = embed)


# expects week as arg, defaults to current week
@bot.command()
async def matchups(ctx,*arg):
    global fantasy_query
    async with fantasy_query_lock:
        if len(arg) != 1:
            week = fantasy_query.get_league()['league'].current_week
        else:
            week = utility.arg_to_int(arg[0])

        #print(fantasy_query.get_scoreboard(week))
        fan_league = fantasy_query.get_league()

    async with emb_color_lock:
        embed = discord.Embed(title = f'Week {week} Matchups', url=fan_league['league'].url, description = '', color = emb_color)
    if week is not None:

        async with fantasy_query_lock:
            matchups_list = fantasy_query.get_scoreboard(week).matchups
        for i in range(len(matchups_list)):
            team_list = matchups_list[i].teams
            
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
    global fantasy_query
    async with fantasy_query_lock:
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
    async with fantasy_query_lock:
        season_league = fantasy_query.get_league_stats(player_id)['league']

    season_stats = season_league.players[0]
    embed.add_field(name = 'Season Pts', value = utility.to_block(season_stats.player_points.total))
    embed.add_field(name = '\u200b', value = '\u200b', inline= False) 

    # footer
    async with fantasy_query_lock:
        ownership_result = fantasy_query.get_ownership(player_id)['league']  
    if len(ownership_result.players[0].ownership.teams) != 0:
        embed.set_footer(text = 'Manager: ' + ownership_result.players[0].ownership.teams[0].name.decode('utf-8'))
    
    # List Stats
    stats_list = team_stats.player_stats.stats
    for i in range(len(stats_list)):
        async with fantasy_query_lock:
            embed.add_field(name = fantasy_query.stat_dict.get(str(stats_list[i].stat_id)), value = utility.to_block(f'{stats_list[i].value:3.1f}'), inline = True)

    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx):
    global fantasy_query
    async with fantasy_query_lock:
        standings = fantasy_query.get_all_standings(10)

    sorted_standings = sorted(standings, key = lambda tup: int(tup[1].rank))

    # load names 
    players_dict_list = utility.load_members()
    embed = discord.Embed(title = f'Current Rankings', url='', description = '', color = emb_color)
    for players in sorted_standings:
        current_player = players_dict_list[players[0]-1]

        record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
        rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
        points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
        points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
        streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

        formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
        embed.add_field(name = f"{current_player['name']} {record}",value = utility.to_block(formated),inline = False)

    await ctx.send(embed = embed)

@bot.command()
async def most_points(ctx):
    global fantasy_query
    async with fantasy_query_lock:
        standings = fantasy_query.get_all_standings(10)

    sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_for), reverse = True)

    # load names 
    players_dict_list = utility.load_members()
    embed = discord.Embed(title = f'Current Rankings', url='', description = '', color = emb_color)
    for players in sorted_standings:
        current_player = players_dict_list[players[0]-1]

        record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
        rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
        points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
        points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
        streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

        formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
        embed.add_field(name = f"{current_player['name']} {record}",value = utility.to_block(formated),inline = False)

    await ctx.send(embed = embed)

@bot.command()
async def least_points(ctx):
    global fantasy_query
    async with fantasy_query_lock:
        standings = fantasy_query.get_all_standings(10)

    sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_against), reverse = True)

    # load names 
    players_dict_list = utility.load_members()
    embed = discord.Embed(title = f'Current Rankings', url='', description = '', color = emb_color)
    for players in sorted_standings:
        current_player = players_dict_list[players[0]-1]

        record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
        rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
        points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
        points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
        streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

        formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
        embed.add_field(name = f"{current_player['name']} {record}",value = utility.to_block(formated),inline = False)

    await ctx.send(embed = embed)

###################################################
# Slap Callout Challenge         
###################################################

async def display_results(current_week, challenger_key, challengee_deque, member_storage):
    chump_role = loser_role_name

    global channel_id
    async with channel_id_lock:
        local_id = channel_id

    global fantasy_query
    
    # gather challenger info
    challenger_name = utility.teamid_to_name(challenger_key)
    challenger_discord_id = utility.teamid_to_discord(challenger_key)
    formatted_challenger_discord_id = utility.id_to_mention(challenger_discord_id)

    # add to array for the future
    if member_storage[int(challenger_key) - 1] is None:
        async with fantasy_query_lock:
            challenger_stats = fantasy_query.get_team_stats(current_week,int(challenger_key))
        member_storage[int(challenger_key) - 1] = challenger_stats
    else:
        challenger_stats = member_storage[int(challenger_key) - 1]

    # get channel for message and guild.roles
    channel = bot.get_channel(local_id)
    guild = channel.guild
    while challengee_deque:
        # gather current challenger info
        challengee_team_id = challengee_deque.pop()
        challengee_name = utility.teamid_to_name(challengee_team_id)
        challengee_discord_id = utility.teamid_to_discord(challengee_team_id)
        formatted_challengee_discord_id = utility.id_to_mention(challengee_discord_id)

        # add to array for the future
        if member_storage[int(challengee_team_id) - 1] is None:
            async with fantasy_query_lock:
                challengee_stats = fantasy_query.get_team_stats(current_week, int(challengee_team_id))
            member_storage[int(challengee_team_id) - 1] = challengee_stats
        else:
            member_storage[int(challengee_team_id) - 1]

        embed = discord.Embed(title = '', url='', description = '', color = emb_color)
        if(challenger_stats['team_points'].total > challengee_stats['team_points'].total):
            embed.add_field(name = f'Winner', value=f'', inline = True)
            embed.add_field(name = f'', value=f'', inline = True)
            embed.add_field(name = f'Loser', value=f'', inline = True)
            embed.set_image(url = left_winner)

            # assign role to loser
            challengee_member = await get_member_by_id(guild,int(challengee_discord_id))
            await assign_role(challengee_member, chump_role, channel)

        elif (challenger_stats['team_points'].total < challengee_stats['team_points'].total):
            embed.add_field(name = f'Loser', value=f'', inline = True)
            embed.add_field(name = f'', value=f'', inline = True)
            embed.add_field(name = f'Winner', value=f'', inline = True)
            embed.set_image(url = right_winner)

            # assign role to loser
            challenger_member = await get_member_by_id(guild,int(challenger_discord_id))
            await assign_role(challenger_member, chump_role, channel)

        else:
            embed.add_field(name = f'Loser', value=f'', inline = True)
            embed.add_field(name = f'', value=f'', inline = True)
            embed.add_field(name = f'Loser', value=f'', inline = True)
            embed.set_image(url=tie_gif)

            # assign role to losers
            challenger_member = await get_member_by_id(guild,int(challenger_discord_id))
            challengee_member = await get_member_by_id(guild,int(challengee_discord_id))
            await assign_role(challenger_member, chump_role, channel)
            await assign_role(challengee_member, chump_role, channel)

        embed.add_field(name = f'{challenger_name}', value=f'{challenger_stats['team_points'].total}\n{formatted_challenger_discord_id}', inline = True)
        embed.add_field(name = 'VS', value = '', inline = True)
        embed.add_field(name = f'{challengee_name}', value=f'{challengee_stats['team_points'].total}\n{formatted_challengee_discord_id}', inline = True)
        await channel.send(embed = embed)


async def iterate_deque(current_week, challenges_deque,member_storage):
    for key in challenges_deque:
        await display_results(current_week, key, challenges_deque[key], member_storage)

@tasks.loop(minutes=1440)
async def remove_slap_roles():
    # load dates list
    loaded_dates = utility.load_dates()

    # current week
    async with fantasy_query_lock:
        fantasy_league = fantasy_query.get_league()['league']   
        
    current_week = fantasy_league.current_week

    # get current week end date
    end_date = loaded_dates.get(str(current_week))
    end_obj = datetime.datetime.strptime(end_date[1], '%Y-%m-%d').date() 
    today_obj = datetime.date.today()

    if end_obj == today_obj:
        await remove_role_members(loser_role_name)
        await remove_role_members(denier_role_name)

@tasks.loop(minutes=1440)
async def poll_slap():
    global fantasy_query
    date_file = current_dir / 'persistent_data' / 'week_dates.json'

    # storage to minimize api calls
    members_storage = [None] * number_of_teams

    # if does not exist, create and store dates list
    exists = os.path.exists(date_file)
    if not exists:
        async with fantasy_query_lock:
            dates_list = utility.construct_date_list(fantasy_query.get_game_weeks()['game_weeks'])
        utility.store_dates(dates_list)

    # load dates list
    loaded_dates = utility.load_dates()

    async with fantasy_query_lock:
        # current week
        fantasy_league = fantasy_query.get_league()['league']   
    current_week = fantasy_league.current_week
    last_week = current_week - 1

    # check if season is over
    start_date = loaded_dates.get(str(current_week))
    if start_date is None:
        print('Season Ended')
        return

    # get last weeks end date and compare to today-1 
    end_date = loaded_dates.get(str(last_week))
    end_obj = datetime.datetime.strptime(end_date[1], '%Y-%m-%d').date() 
    yesterday_obj = datetime.date.today() - datetime.timedelta(days = 1)

    if yesterday_obj == end_obj:
        # pop all challenges from deque
        current_challenges = utility.load_challenges()
        await iterate_deque(current_week, current_challenges,members_storage)
        utility.clear_challenges()

class AcceptDenyChallenge(discord.ui.View):
    def __init__(self, challenger,challengee,challengee_teamid, challenger_teamid):
        super().__init__(timeout = 1800)
        self.challenger = challenger
        self.challengee = challengee
        self.challenger_teamid = challenger_teamid
        self.challengee_teamid = challengee_teamid
        self.message = None

    async def on_timeout(self):
        for child in self.children:
            if type(child) == discord.ui.Button:
                child.disabled = True

        if self.message:
            embed = discord.Embed(title = 'Slap', description = f'Challenge Expired',color = emb_color)
            await self.message.edit(embed = embed,view = self)

    async def cleanup(self):
        for child in self.children:
            if type(child) == discord.ui.Button:
                child.disabled = True

        if self.message:
            embed = discord.Embed(title = 'Slap', description = f'Challenge Expired',color = emb_color)
            await self.message.edit(embed = embed,view = self)

    async def shutdown(self):
        await self.cleanup()

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.primary)
    async def button_callback(self, interaction, button):
        # check if correct user responding
        if interaction.user.id != self.challengee:
            await interaction.response.send_message(f'You don\'t want no part of this {utility.id_to_mention(interaction.user.id)}')
            return

        # disable current button
        button.disabled = True

        # disable all other buttons
        for child in self.children:
            if type(child) == discord.ui.Button:
                child.disabled = True
        
        utility.add_challenges(self.challenger_teamid,self.challengee_teamid)

        embed = discord.Embed(title='Slap', description = f'{utility.id_to_mention(self.challengee)} has accepted {utility.id_to_mention(self.challenger)}\'s challenge.',color = emb_color)
        embed.set_image(url = charlie_slap)

        await interaction.response.edit_message(embed = embed, view=self)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def second_button_callback(self, interaction, button):
        # check if correct user responding
        if interaction.user.id != self.challengee:
            await interaction.response.send_message(f'You don\'t want no part of this {utility.id_to_mention(interaction.user.id)}')
            return
        
        button.disabled = True

        for child in self.children:
            if type(child) == discord.ui.Button:
                child.disabled = True
        embed = discord.Embed(title='Slap', description = f'{utility.id_to_mention(self.challengee)} has denied {utility.id_to_mention(self.challenger)}\'s challenge.',color = emb_color)
        embed.set_image(url = charlie_stare)

        # give them the denier_role
        channel = interaction.channel
        member = interaction.user

        await assign_role(member,denier_role_name,channel)
        await interaction.response.edit_message(embed = embed, view=self)

@bot.command()
async def slap(ctx,arg):
    
    # add challenges if not on the start date
    loaded_dates = utility.load_dates()

    global fantasy_query
    async with fantasy_query_lock:
        fantasy_league = fantasy_query.get_league()['league']

    current_week = fantasy_league.current_week

    start_date = loaded_dates.get(str(current_week))
    if start_date is None:
        print('Season Ended')
        return

    start_date = datetime.datetime.strptime(start_date[0], '%Y-%m-%d').date()
    today = datetime.date.today()

    if today == start_date:
        embed = discord.Embed(title='Slap someone tomorrow.', description = f'Challenges start Wednesday.',color = emb_color)
        embed.set_image(url = timeout_gif)

        await ctx.send(embed = embed)
        return

    # create a challenge with buttons for accept and deny
    mention = ctx.message.raw_mentions
    challengee_discord_id = utility.arg_to_int(mention[0])
    challenger_discord_id = ctx.author.id

    challengee_teamid = utility.discord_to_teamid(challengee_discord_id)
    challenger_teamid = utility.discord_to_teamid(challenger_discord_id)

    description_text = f'{utility.id_to_mention(challenger_discord_id)} challenged {utility.id_to_mention(challengee_discord_id)} to a duel.'
    embed = discord.Embed(title = 'Slap', description = description_text,color = emb_color)
    embed.set_image(url = dave_slap)

    view = AcceptDenyChallenge(challenger_discord_id,challengee_discord_id,challengee_teamid,challenger_teamid)
    async with active_views_lock:
        active_views.append(view)

    message = await ctx.send(embed = embed, view = view)
    view.message = message

@bot.command()
async def test(ctx):
    await ctx.send("Press the button!", view=AcceptDenyChallenge())

@bot.command()
async def game_test(ctx):
    await poll_slap()


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

