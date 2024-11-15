import discord
from discord import app_commands
from discord.ext import commands

import utility
import json
import asyncio
from pathlib import Path

from difflib import get_close_matches

data = utility.get_private_data()

# Decorator guild_id
guild_id = int(data.get('guild_id'))




class FantasyQuery(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent

        self.channel_id = None
        self.channel_id_lock = asyncio.Lock()
        self.news_channel_id = None
        self.news_id_lock = asyncio.Lock()

        # bot embed color
        self.emb_color = discord.Color.from_rgb(225, 198, 153)

    ###################################################
    # Discord Commands          
    ###################################################

    @commands.command()
    async def discord_info(self,ctx, *arg):
        await ctx.send(f' guild: {ctx.guild} \n message: {ctx.message.channel.name} \n author: @{ctx.author}')

    def check_user_exists(self,user):
        with open(self.parent_dir / 'persistent_data'/ 'members.json', 'r') as file:
            members = json.load(file)

        for i in range(len(members)):
            if 'discord_id' in members[i] and members[i]['discord_id'] == user:
                return True
        return False


    @app_commands.command(name="reload_commands", description="Reloads slash commands.")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def reload_commands(self, interaction: discord.Interaction):
        # load all cogs
        directory = self.parent_dir / 'cogs'
        for filename in directory:
            if filename.is_file() and filename.endswith('py') and not filename.startswith('__'):
                print(f'Reload {filename}')
                await self.bot.load_extension(f'cogs.{filename[:-3]}')
            await interaction.response.send_message(f'Reload Done')


    @app_commands.command(name="all_commands", description="List of all available commands.")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def all_commands(self, interaction: discord.Interaction):
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
        
        embed = discord.Embed(title = 'All Commands', url='', description='',color = self.emb_color)
        for command in command_list:
            for key, value in command.items():
                embed.add_field(name=key, value=value, inline = False)

        await interaction.response.send_message(embed = embed,ephemeral=False)
        

    @app_commands.command(name = "user_commands", description = "List of user-level commands.")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def user_commands(self, interaction: discord.Interaction):
        command_list = [{'chump [week]: ':'Lists lowest score user of the week\nDefaults to current week if not specified'},\
                    {'mvp [week]: ':'Lists highest score user of the week\nDefaults to current week if not specified'},\
                    {'matchups [week]: ':'Lists week matchups, points and projections\nDefaults to current week if not specified'},\
                    {'player [player name]:':'Lists player stats\nExpects complete name as represented in yahoo.'},\
                    {'leaderboard:':'Lists current fantasy standings'},\
                    {'most_points:':'Lists users from highest to lowest season points'},\
                    {'least_points:':'Lists users from lowest to highest season points'},\
                    {'slap':'Challenge a player. Loser gets assigned the chump tag.(FAAB gamble next year???)'}]
        
        embed = discord.Embed(title = 'All Commands', url='', description='',color = self.emb_color)
        for command in command_list:
            for key, value in command.items():
                embed.add_field(name=key, value=value, inline = False)

        await interaction.response.send_message(embed = embed,ephemeral=False)


    @app_commands.command(name="fantasy_info", description = "Lists Team IDs")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def fantasy_info(self,interaction: discord.Interaction):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            fan_league = self.bot.fantasy_query.get_league()


        embed = discord.Embed(title = fan_league['league'].name.decode('utf-8'), url=fan_league['league'].url,description = 'Fantasy participants and IDs', color = self.emb_color ) 
        embed.set_thumbnail(url = fan_league['league'].logo_url)
        
        async with self.bot.fantasy_query_lock:
            teams = self.bot.fantasy_query.get_teams()

        for team in teams:
            embed.add_field(name = team.name.decode("utf-8"), value = "Team ID: " + str(team.team_id))
        
        await interaction.followup.send(embed=embed,ephemeral=False)


    @app_commands.command(name="info", description = "Lists Team IDs and Discord Tags")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def info(self,interaction: discord.Interaction):
        with open(self.parent_dir / 'persistent_data'/ 'members.json', 'r') as file:
            members = json.load(file)

        async with self.bot.fantasy_query_lock:
            fan_league = self.bot.fantasy_query.get_league()

        embed = discord.Embed(title = fan_league['league'].name.decode('utf-8'), url=fan_league['league'].url,description = 'Current Yahoo and Discord Connections', color = self.emb_color ) 
        embed.set_thumbnail(url = fan_league['league'].logo_url)

        for i in range(len(members)):
            dis_id = members[i].get('discord_id')
            if dis_id is None:
                val = f"Team ID: {members[i].get('id')} \nTag: None"
            else:
                val = f"Team ID: {members[i].get('id')} \nTag: {utility.id_to_mention(members[i].get('discord_id'))}"
            embed.add_field(name = members[i].get('name'), value = val, inline=False)

        await interaction.response.send_message(embed = embed,ephemeral=False)


    @app_commands.command(name="bind", description= "Bind Team ID to current Discord ID")
    @app_commands.describe(id="Yahoo team ID")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def bind(self,interaction:discord.Interaction, id: int):
        discord_id = interaction.user.id

        value = utility.arg_to_int(id)

        if value != None and (value >= 1 or value <= 10):
            utility.bind_discord(value,discord_id)
            await interaction.response.send_message(f'Team ID: {value} bound to Discord ID: {utility.id_to_mention(discord_id)}',ephemeral=True)
        else:
            await interaction.response.send_message('Integer between 1 - 10',ephemeral=True)


    @app_commands.command(name='bind_other', description= "Bind Team ID to specified Discord ID")
    @app_commands.describe(discord_user="Tagged Discord User",id="Yahoo team ID")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def bind_other(self, interaction:discord.Interaction, discord_user:discord.User, id:int):

        if id != None and (id >= 1 or id <= 10):
            utility.bind_discord(id,discord_user.id)
            await interaction.response.send_message(f'Team ID: {id} bound to Discord ID: {utility.id_to_mention(discord_user.id)}',ephemeral=True)
        else:
            await interaction.response.send_message('Integer between 1 - 10',ephemeral=True)


    @app_commands.command(name="set_news",description="Set current channel to news channel")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def set_channel(self,interaction:discord.Interaction):
        async with self.news_id_lock:
            self.news_channel_id = interaction.channel_id
        await interaction.response.send_message('Channel Set.')


    @app_commands.command(name="week_chump",description="Loser of the specified week")
    @app_commands.describe(week="week")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def week_chump(self,interaction:discord.Interaction,week:int):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            fantasy_league = self.bot.fantasy_query.get_league()['league']

        # search for lowerst points
        current_lowest = -1

        async with self.bot.fantasy_query_lock:
            matchups_list = self.bot.fantasy_query.get_scoreboard(week).matchups
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
        
        
        embed = discord.Embed(title = f'Week {week} Chump', url = fantasy_league.url, description = f'Total Pts: {current_lowest}', color = self.emb_color)
        embed.set_thumbnail(url = logo_url)

        # use lowest_id to mention discord user 
        discord_user = utility.teamid_to_discord(lowest_id)

        # check if user exists
        if discord_user is None:
            await interaction.followup.send(utility.to_block(f"{lowest_name.decode('utf-8')} Total Pts: {current_lowest}"),ephemeral=False)
        else:
            member = interaction.guild.get_member(int(discord_user))
            if discord_user is not None:
                embed.set_author(name = member.display_name, url=lowest_url, icon_url = member.display_avatar.url)

            async with self.bot.fantasy_query_lock:
                # get and display loser's roster
                player_list = self.bot.fantasy_query.get_team_roster(lowest_id,week).players

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

            async with self.bot.fantasy_query_lock:
            # populate the fields
                for player in starting_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
                
                for player in defense_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'{team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
                
                embed.add_field(name = '\u200b', value = '\u200b')  
                for player in bench_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)   
            
            embed.set_footer(text = lowest_name.decode('utf-8'))
            await interaction.followup.send(embed = embed,ephemeral=False)


    @app_commands.command(name="chump",description="Loser of the current week")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def chump(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            fantasy_league = self.bot.fantasy_query.get_league()['league']

        week = fantasy_league.current_week

        # search for lowerst points
        current_lowest = -1

        async with self.bot.fantasy_query_lock:
            matchups_list = self.bot.fantasy_query.get_scoreboard(week).matchups
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
        
        
        embed = discord.Embed(title = f'Week {week} Chump', url = fantasy_league.url, description = f'Total Pts: {current_lowest}', color = self.emb_color)
        embed.set_thumbnail(url = logo_url)

        # use lowest_id to mention discord user 
        discord_user = utility.teamid_to_discord(lowest_id)

        # check if user exists
        if discord_user is None:
            await interaction.followup.send(utility.to_block(f"{lowest_name.decode('utf-8')} Total Pts: {current_lowest}"),ephemeral=False)
        else:
            member = interaction.guild.get_member(int(discord_user))
            if discord_user is not None:
                embed.set_author(name = member.display_name, url=lowest_url, icon_url = member.display_avatar.url)

            async with self.bot.fantasy_query_lock:
                # get and display loser's roster
                player_list = self.bot.fantasy_query.get_team_roster(lowest_id,week).players

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

            async with self.bot.fantasy_query_lock:
            # populate the fields
                for player in starting_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
                
                for player in defense_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'{team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
                
                embed.add_field(name = '\u200b', value = '\u200b')  
                for player in bench_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)   
            
            embed.set_footer(text = lowest_name.decode('utf-8'))
            await interaction.followup.send(embed = embed,ephemeral=False)

    @app_commands.command(name="week_mvp",description="MVP of the specified week")
    @app_commands.describe(week="week")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def week_mvp(self,interaction:discord.Interaction,week:int):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            fantasy_league = self.bot.fantasy_query.get_league()['league']

        # search for lowerst points
        current_highest = -1
            
        async with self.bot.fantasy_query_lock:
            matchups_list = self.bot.fantasy_query.get_scoreboard(week).matchups
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
        
        
        embed = discord.Embed(title = f'Week {week} MVP', url = fantasy_league.url, description = f'Total Pts: {current_highest}', color = self.emb_color)
        embed.set_thumbnail(url = logo_url)

        # use highest_id to mention discord user 
        discord_user = utility.teamid_to_discord(highest_id)

        # check if user exists
        if discord_user is None:
            await interaction.followup.send(utility.to_block(f"{highest_name.decode('utf-8')} Total Pts: {current_highest}"),ephemeral=False)
        else:
            member = interaction.guild.get_member(int(discord_user))


            if discord_user is not None:
                embed.set_author(name = member.display_name, url=highest_url, icon_url = member.display_avatar.url)

            async with self.bot.fantasy_query_lock:
                # get and display loser's roster
                player_list = self.bot.fantasy_query.get_team_roster(highest_id,week).players

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

            async with self.bot.fantasy_query_lock:
            # populate the fields
                for player in starting_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
                
                for player in defense_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'{team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
                
                embed.add_field(name = '\u200b', value = '\u200b')  
                for player in bench_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)   
            
            embed.set_footer(text = highest_name.decode('utf-8'))
            await interaction.followup.send(embed = embed,ephemeral=False)

    @app_commands.command(name="mvp",description="MVP of the current week")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def mvp(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            fantasy_league = self.bot.fantasy_query.get_league()['league']

        week = fantasy_league.current_week

        # search for lowerst points
        current_highest = -1
            
        async with self.bot.fantasy_query_lock:
            matchups_list = self.bot.fantasy_query.get_scoreboard(week).matchups
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
        
        
        embed = discord.Embed(title = f'Week {week} MVP', url = fantasy_league.url, description = f'Total Pts: {current_highest}', color = self.emb_color)
        embed.set_thumbnail(url = logo_url)

        # use highest_id to mention discord user 
        discord_user = utility.teamid_to_discord(highest_id)

        # check if user exists
        if discord_user is None:
            await interaction.followup.send(utility.to_block(f"{highest_name.decode('utf-8')} Total Pts: {current_highest}"),ephemeral=False)
        else:
            member = interaction.guild.get_member(int(discord_user))


            if discord_user is not None:
                embed.set_author(name = member.display_name, url=highest_url, icon_url = member.display_avatar.url)

            async with self.bot.fantasy_query_lock:
                # get and display loser's roster
                player_list = self.bot.fantasy_query.get_team_roster(highest_id,week).players

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

            async with self.bot.fantasy_query_lock:
            # populate the fields
                for player in starting_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
                
                for player in defense_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'{team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)        
                
                embed.add_field(name = '\u200b', value = '\u200b')  
                for player in bench_list:
                    team_stats = self.bot.fantasy_query.team_stats(player,week)
                    embed.add_field(name = f'{team_stats.name.full}', value = f'#{team_stats.uniform_number}, {team_stats.primary_position}, {team_stats.editorial_team_full_name} \nTotal Pts: [{team_stats.player_points.total:4.2f}]({team_stats.url})', inline = False)   
            
            embed.set_footer(text = highest_name.decode('utf-8'))
            await interaction.followup.send(embed = embed,ephemeral=False)


    @app_commands.command(name="week_matchups",description="Matchups of the specified week")
    @app_commands.describe(week="week")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def week_matchups(self,interaction:discord.Interaction,week:int):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            fan_league = self.bot.fantasy_query.get_league()

        embed = discord.Embed(title = f'Week {week} Matchups', url=fan_league['league'].url, description = '', color = self.emb_color)

        if week is not None:
            async with self.bot.fantasy_query_lock:
                matchups_list = self.bot.fantasy_query.get_scoreboard(week).matchups
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
            await interaction.followup.send(embed = embed,ephemeral=False)


    @app_commands.command(name="matchups",description="Matchups of the current week")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def matchups(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            week = self.bot.fantasy_query.get_league()['league'].current_week
            fan_league = self.bot.fantasy_query.get_league()

        embed = discord.Embed(title = f'Week {week} Matchups', url=fan_league['league'].url, description = '', color = self.emb_color)

        if week is not None:

            async with self.bot.fantasy_query_lock:
                matchups_list = self.bot.fantasy_query.get_scoreboard(week).matchups
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
            await interaction.followup.send(embed = embed,ephemeral=False)


    @app_commands.command(name="player_stats",description="NFL player details")
    @app_commands.describe(player_name="name")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def player_stats(self,interaction:discord.Interaction,player_name:str):
        await interaction.response.defer()
        player_list = utility.load_players()
        closest_keys = get_close_matches(player_name,player_list,n=1,cutoff=0.6)
        
        if len(closest_keys) == 0:
             await interaction.followup.send("Doesn't exit or you need to spell better.")
             return

        if closest_keys[0] == player_name:
            name = player_name
        else:
            name = closest_keys[0]

        async with self.bot.fantasy_query_lock:
            player_id = self.bot.fantasy_query.get_player_id(name)

            # weekly stats
            player = self.bot.fantasy_query.get_player_stats(player_id)
            week = self.bot.fantasy_query.get_league()['league'].current_week
            team_stats = self.bot.fantasy_query.team_stats(player_id,week)

        embed = discord.Embed(title = f'{name}', url=player.url, description = f'#{player.uniform_number}, {player.display_position}, {player.editorial_team_full_name}', color = self.emb_color)
        embed.set_thumbnail(url = player.image_url)

        if player.has_player_notes:
            embed.add_field(name = 'Status',value =utility.to_red_text(f'{player.status_full} {player.injury_note}'),inline=True)

        embed.add_field(name = 'Points', value = utility.to_block(team_stats.player_points.total), inline=True)

        # season points
        async with self.bot.fantasy_query_lock:
            season_league = self.bot.fantasy_query.get_league_stats(player_id)['league']

        season_stats = season_league.players[0]
        embed.add_field(name = 'Season Pts', value = utility.to_block(season_stats.player_points.total))
        embed.add_field(name = '\u200b', value = '\u200b', inline= False) 

        # footer
        async with self.bot.fantasy_query_lock:
            ownership_result = self.bot.fantasy_query.get_ownership(player_id)['league']  
        if len(ownership_result.players[0].ownership.teams) != 0:
            embed.set_footer(text = 'Manager: ' + ownership_result.players[0].ownership.teams[0].name.decode('utf-8'))
        
        # List Stats
        stats_list = team_stats.player_stats.stats
        for i in range(len(stats_list)):
            async with self.bot.fantasy_query_lock:
                embed.add_field(name = self.bot.fantasy_query.stat_dict.get(str(stats_list[i].stat_id)), value = utility.to_block(f'{stats_list[i].value:3.1f}'), inline = True)

        await interaction.followup.send(embed=embed,ephemeral=False)


    @app_commands.command(name="leaderboard",description="Fantasy Leaderboard")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def leaderboard(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            standings = self.bot.fantasy_query.get_all_standings(10)

        sorted_standings = sorted(standings, key = lambda tup: int(tup[1].rank))

        # load names 
        players_dict_list = utility.load_members()
        embed = discord.Embed(title = f'Current Rankings', url='', description = '', color = self.emb_color)
        for players in sorted_standings:
            current_player = players_dict_list[players[0]-1]

            record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
            rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
            points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
            points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
            streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

            formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
            embed.add_field(name = f"{current_player['name']} {record}",value = utility.to_block(formated),inline = False)

        await interaction.followup.send(embed = embed,ephemeral=False)


    @app_commands.command(name="most_points",description="Standings by most points")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def most_points(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            standings = self.bot.fantasy_query.get_all_standings(10)

        sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_for), reverse = True)

        # load names 
        players_dict_list = utility.load_members()
        embed = discord.Embed(title = f'Current Rankings', url='', description = '', color = self.emb_color)
        for players in sorted_standings:
            current_player = players_dict_list[players[0]-1]

            record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
            rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
            points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
            points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
            streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

            formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
            embed.add_field(name = f"{current_player['name']} {record}",value = utility.to_block(formated),inline = False)

        await interaction.followup.send(embed = embed,ephemeral=False)


    @app_commands.command(name="points_against",description="Standings by points against")
    @app_commands.guilds(discord.Object(id=guild_id))
    async def points_against(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.fantasy_query_lock:
            standings = self.bot.fantasy_query.get_all_standings(10)

        sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_against), reverse = True)

        # load names 
        players_dict_list = utility.load_members()
        embed = discord.Embed(title = f'Current Rankings', url='', description = '', color = self.emb_color)
        for players in sorted_standings:
            current_player = players_dict_list[players[0]-1]

            record = f'({players[1].outcome_totals.wins}-{players[1].outcome_totals.losses}-{players[1].outcome_totals.ties})'
            rank = format('Rank: ', '<15') + format(players[1].rank, '<1')
            points = format('Pts for: ', '<15') + format(str(players[1].points_for), '<1')
            points_against = format('Pts against: ','<15') + format(str(players[1].points_against), '<1') 
            streak = format('Streak: ' , '<15') + format(f'{players[1].streak.type} - {players[1].streak.value}','<1')

            formated = f'{rank}\n{points}\n{points_against}\n{streak} \n' 
            embed.add_field(name = f"{current_player['name']} {record}",value = utility.to_block(formated),inline = False)

        await interaction.followup.send(embed = embed,ephemeral=False)

    ###################################################
    # Error Handling         
    ###################################################

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandNotFound):
            await interaction.response.send_message("This command does not exist.", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        else:
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            # Log the error or print details for debugging
            print(f"Error: {error}")


    ###################################################
    # Handle Startup          
    ###################################################

    def setup_discord(self):
        with open(self.parent_dir / 'discordauth'/ 'private.json', 'r') as file:
            data = json.load(file)

        self.channel_id = int(data.get('channel_id'))
        self.news_channel_id = int(data.get('news_channel_id'))

    @commands.Cog.listener()
    async def on_ready(self):
        self.setup_discord()
        print('Channels Set Up!')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        print('FantasyQuery - Cog Unload')

async def setup(bot):
    await bot.add_cog(FantasyQuery(bot))