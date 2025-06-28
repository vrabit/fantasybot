import discord
from discord import app_commands
from discord.ext import tasks, commands

from cogs_helpers import FantasyQueryHelper
import utility

import asyncio
from pathlib import Path

from yfpy.models import Scoreboard, League, Matchup, Team, Player

import os
import datetime

import logging
logger = logging.getLogger(__name__)


class FantasyQuery(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready = False

        self.player_ids_filename = 'player_ids.csv'
        self.members_filename = 'members.json'
        self._private_filename = 'private.json'

        # bot embed color
        self.emb_color = self.bot.state.emb_color
        self.winner_color = self.bot.state.winner_color
        self.loser_color = self.bot.state.loser_color


    ###################################################
    # Discord Commands          
    ###################################################

    @commands.command()
    async def discord_info(self,ctx, *arg):
        await ctx.send(f' guild: {ctx.guild} \n message: {ctx.message.channel.name} \n author: @{ctx.author}')


    async def check_user_exists(self,user):
        members = await self.bot.state.persistent_manager.load_json(filename = self.members_filename)

        for member in members:
            if 'discord_id' in member and member.get('discord_id') == user:
                return True
        return False


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))   
    @app_commands.command(name="reload_commands", description="Reloads slash commands.")
    async def reload_commands(self, interaction: discord.Interaction):
        # load all cogs
        directory = self.parent_dir / 'cogs'
        for filename in directory:
            if filename.is_file() and filename.endswith('py') and not filename.startswith('__'):
                logger.info(f'[FantasyQuery] - Reload {filename}')
                await self.bot.load_extension(f'cogs.{filename[:-3]}')
            await interaction.response.send_message('Reload Done')


    @app_commands.command(name="fantasy_info", description = "Lists Team IDs")
    async def fantasy_info(self,interaction: discord.Interaction):
        await interaction.response.defer()
        async with self.bot.state.league_lock:
            fan_league = self.bot.state.league
            embed = discord.Embed(title = fan_league.name.decode('utf-8'), url=fan_league.url,description = 'Fantasy participants and IDs', color = self.emb_color ) 
            embed.set_thumbnail(url = fan_league.logo_url)
        
        async with self.bot.state.fantasy_query_lock:
            teams = self.bot.state.fantasy_query.get_teams()

        for team in teams:
            embed.add_field(name = team.name.decode("utf-8"), value = "Team ID: " + str(team.team_id),inline=False)
        
        await interaction.followup.send(embed=embed,ephemeral=False)


    @app_commands.command(name="info", description = "Lists Team IDs and Discord Tags")
    async def info(self,interaction: discord.Interaction):
        members = await self.bot.state.persistent_manager.load_json(filename = self.members_filename)

        async with self.bot.state.league_lock:
            fan_league = self.bot.state.league
            embed = discord.Embed(title = fan_league.name.decode('utf-8'), url=fan_league.url,description = 'Current Yahoo and Discord Connections', color = self.emb_color ) 
            embed.set_thumbnail(url = fan_league.logo_url)

        for i in range(len(members)):
            dis_id = members[i].get('discord_id')
            if dis_id is None:
                val = f"Team ID: {members[i].get('id')} \nTag: None"
            else:
                val = f"Team ID: {members[i].get('id')} \nTag: {utility.id_to_mention(members[i].get('discord_id'))}"
            embed.add_field(name = members[i].get('name'), value = val, inline=False)

        await interaction.response.send_message(embed = embed,ephemeral=False)


    async def bind_discord(self, members:dict, draft_id:int, discord_id:int) -> dict:
        for member in members:
            if member.get('id') == str(draft_id):
                member.update({'discord_id':str(discord_id)})
                break
        return members


    @app_commands.command(name="bind", description= "Bind Team ID to current Discord ID")
    @app_commands.describe(id="Yahoo team ID")
    async def bind(self,interaction:discord.Interaction, id: int):
        discord_id = interaction.user.id

        value = utility.arg_to_int(id)

        async with self.bot.state.league_lock:
            num_teams = utility.arg_to_int(self.bot.state.league.num_teams) 

        if value >= 1 and value <= num_teams:
            members = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)
            updated_members = await self.bind_discord(members, value, discord_id)
            await self.bot.state.persistent_manager.write_json(filename=self.members_filename, data=updated_members)

            await interaction.response.send_message(f'Team ID: {value} bound to Discord ID: {utility.id_to_mention(discord_id)}',ephemeral=True)
        else:
            await interaction.response.send_message(f'Integer between 1 - {num_teams}',ephemeral=True)


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='bind_other', description= "Bind Team ID to specified Discord ID")
    @app_commands.describe(discord_user="Tagged Discord User", id="Yahoo team ID")
    async def bind_other(self, interaction:discord.Interaction, discord_user:discord.User, id:int):

        async with self.bot.state.league_lock:
            num_teams = utility.arg_to_int(self.bot.state.league.num_teams) 

        if id >= 1 and id <= num_teams:
            members = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)
            updated_members = await self.bind_discord(members, id, discord_user.id)
            await self.bot.state.persistent_manager.write_json(filename=self.members_filename, data=updated_members)

            await interaction.response.send_message(f'Team ID: {id} bound to Discord ID: {utility.id_to_mention(discord_user.id)}',ephemeral=True)
        else:
            await interaction.response.send_message(f'Integer between 1 - {num_teams}',ephemeral=True)


    @app_commands.command(name="set_news",description="Set current channel to News channel")
    async def set_channel(self,interaction:discord.Interaction):
        async with self.bot.state.news_channel_id_lock:
            self.bot.state.news_channel_id = interaction.channel_id

        # load persistent data
        exists = await self.bot.state.discord_auth_manager.path_exists(self._private_filename)
        if exists:
            data = await self.bot.state.discord_auth_manager.load_json(self._private_filename)
        else:
            data = {'news_channel_id': None,'channel_id': None, 'transactions_channel_id': None}

        # update persistent data
        data.update({'news_channel_id': str(interaction.channel_id)})
        await self.bot.state.discord_auth_manager.write_json(filename = self._private_filename, data = data)

        await interaction.response.send_message('News Channel Set.')


    @app_commands.command(name="set_slap_channel",description="Set current channel to Slap channel")
    async def set_slap_channel(self,interaction:discord.Interaction):
        async with self.bot.state.slaps_channel_id_lock:
            self.bot.state.slap_channel_id = interaction.channel_id

        # load persistent data
        exists = await self.bot.state.discord_auth_manager.path_exists(self._private_filename)
        if exists:
            data = await self.bot.state.discord_auth_manager.load_json(self._private_filename)
        else:
            data = {'news_channel_id': None,'channel_id': None, 'transactions_channel_id': None}

        # update persistent data
        data.update({'channel_id': str(interaction.channel_id)})
        await self.bot.state.discord_auth_manager.write_json(filename = self._private_filename, data = data)

        await interaction.response.send_message('Slap Channel Set.')


    @app_commands.command(name="set_transactions_channel",description="Set current channel to Transactions channel")
    async def set_transactions_channel(self,interaction:discord.Interaction):
        async with self.bot.state.transactions_channel_id_lock:
            self.bot.state.transactions_channel_id = interaction.channel_id

        # load persistent data
        exists = await self.bot.state.discord_auth_manager.path_exists(self._private_filename)
        if exists:
            data = await self.bot.state.discord_auth_manager.load_json(self._private_filename)
        else:
            data = {'news_channel_id': None,'channel_id': None, 'transactions_channel_id': None}

        # update persistent data
        data.update({'transactions_channel_id': str(interaction.channel_id)})
        await self.bot.state.discord_auth_manager.write_json(filename = self._private_filename, data = data)

        await interaction.response.send_message('Transactions Channel Set.')


    async def construct_chump_champ(self,chimp:str, fantasy_league, lowest_team, interaction, week, color):
        # use lowest_id to mention discord user 
        discord_user = await utility.teamid_to_discord(lowest_team.team_id,self.bot.state.persistent_manager)

        embed_starting = await FantasyQueryHelper.init_embed(chimp, ' - STARTING', week,fantasy_league.url, lowest_team.team_points.total, color, lowest_team.team_logos[0].url)
        embed_bench = await FantasyQueryHelper.init_embed(chimp, ' - BENCH', week,fantasy_league.url, lowest_team.team_points.total, color, lowest_team.team_logos[0].url)
        embed_defense = await FantasyQueryHelper.init_embed(chimp, ' - DEFENSE', week,fantasy_league.url, lowest_team.team_points.total, color, lowest_team.team_logos[0].url)
        
        # check if user exists
        if discord_user is None:
            await interaction.followup.send(utility.to_block(f"{lowest_team.name.decode('utf-8')} Total Pts: {lowest_team.team_points.total}"),ephemeral=False)
        else:
            member = interaction.guild.get_member(int(discord_user))
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(int(discord_user))
                except Exception as e:
                    logger.error(f'[FantasyQuery][construct_chump_champ] - Error: {e}')
                    await interaction.followup.send('Failed to Construct Player Profile.')
                    return

            if discord_user is not None:
                embed_starting.set_author(name = member.display_name, url=lowest_team.url, icon_url = member.display_avatar.url)
                embed_bench.set_author(name = member.display_name, url=lowest_team.url, icon_url = member.display_avatar.url)
                embed_defense.set_author(name = member.display_name, url=lowest_team.url, icon_url = member.display_avatar.url)

            async with self.bot.state.fantasy_query_lock:
                # get and display loser's roster
                player_list:list[Player] = self.bot.state.fantasy_query.get_team_roster(lowest_team.team_id,week).players

        
            # sort players by position into deque
            starting_deque, bench_deque, defense_deque = await FantasyQueryHelper.construct_roster_lists(player_list)
            
            # add fields and send
            if starting_deque:
                await FantasyQueryHelper.add_player_fields(embed_starting, starting_deque, week, self.bot.state)
                embed_starting.set_footer(text = lowest_team.name.decode('utf-8'))
                await interaction.followup.send(embed = embed_starting,ephemeral=False)

            if defense_deque:
                await FantasyQueryHelper.add_defense_fields(embed_defense, defense_deque, week, self.bot.state)
                embed_defense.set_footer(text = lowest_team.name.decode('utf-8'))
                await interaction.followup.send(embed = embed_defense,ephemeral=False)

            if bench_deque:
                await FantasyQueryHelper.add_player_fields(embed_bench, bench_deque, week, self.bot.state)
                embed_bench.set_footer(text = lowest_team.name.decode('utf-8'))
                await interaction.followup.send(embed = embed_bench,ephemeral=False)


    @app_commands.command(name="week_chump",description="Loser of the specified week")
    @app_commands.describe(week="week")
    async def week_chump(self,interaction:discord.Interaction,week:int):
        await interaction.response.defer()

        async with self.bot.state.league_lock:
            league:League = self.bot.state.league
            start_week = league.start_week
            end_week = league.end_week

        if week > end_week or week < start_week:
            await interaction.followup.send(f'Invalid Input: start_week={start_week} - end_week={end_week}',ephemeral=True)
            return
        
        if week > league.current_week:
            await interaction.followup.send(f'Invalid Input: current_week={league.current_week}',ephemeral=True)
            return

        # lowest team
        async with self.bot.state.fantasy_query_lock:
            matchups_list:list[Matchup] = self.bot.state.fantasy_query.get_scoreboard(week).matchups
        lowest_team:Team = await FantasyQueryHelper.lowest_points_matchup_list(matchups_list)

        await self.construct_chump_champ('Chump', league,lowest_team,interaction, week, self.loser_color)


    @app_commands.command(name="chump",description="Loser of the current week")
    async def chump(self,interaction:discord.Interaction):
        await interaction.response.defer()

        async with self.bot.state.league_lock:
            fantasy_league:League = self.bot.state.league

        week = fantasy_league.current_week
        async with self.bot.state.fantasy_query_lock:
            matchups_list = self.bot.state.fantasy_query.get_scoreboard(week).matchups
        lowest_team:Team = await FantasyQueryHelper.lowest_points_matchup_list(matchups_list)

        await self.construct_chump_champ('Chump', fantasy_league, lowest_team, interaction, week, self.loser_color)


    @app_commands.command(name="week_mvp",description="MVP of the specified week")
    @app_commands.describe(week="week")
    async def week_mvp(self,interaction:discord.Interaction,week:int):
        await interaction.response.defer()

        async with self.bot.state.league_lock:
            league:League = self.bot.state.league
            start_week = league.start_week
            end_week = league.end_week

        if week > end_week or week < start_week:
            await interaction.followup.send(f'Invalid Input: start_week={start_week} - end_week={end_week}',ephemeral=True)
            return

        if week > league.current_week:
            await interaction.followup.send(f'Invalid Input: current_week={league.current_week}', ephemeral=True)
            return

        async with self.bot.state.fantasy_query_lock:
            matchups_list:list[Matchup] = self.bot.state.fantasy_query.get_scoreboard(week).matchups
        highest_team:Team = await FantasyQueryHelper.highest_points_matchup_list(matchups_list)

        await self.construct_chump_champ('Champ',league, highest_team, interaction, week, self.winner_color)


    @app_commands.command(name="mvp",description="MVP of the current week")
    async def mvp(self,interaction:discord.Interaction):
        await interaction.response.defer()

        async with self.bot.state.league_lock:
            league:League = self.bot.state.league

        week = league.current_week

        async with self.bot.state.fantasy_query_lock:
            matchups_list:list[Matchup] = self.bot.state.fantasy_query.get_scoreboard(week).matchups
        highest_team:Team = await FantasyQueryHelper.highest_points_matchup_list(matchups_list)

        await self.construct_chump_champ('Champ',league, highest_team, interaction, week, self.winner_color)


    @app_commands.command(name="week_matchups",description="Matchups of the specified week")
    @app_commands.describe(week="week")
    async def week_matchups(self,interaction:discord.Interaction,week:int):
        await interaction.response.defer()
        async with self.bot.state.league_lock:
            fan_league:League = self.bot.state.league

        embed = discord.Embed(title = f'Week {week} Matchups', url=fan_league.url, description = '', color = self.emb_color)
        async with self.bot.state.fantasy_query_lock:
            matchups_list = self.bot.state.fantasy_query.get_scoreboard(week).matchups

        await FantasyQueryHelper.add_matchup_fields(matchups_list, embed)
        await interaction.followup.send(embed = embed,ephemeral=False)


    @app_commands.command(name="matchups",description="Matchups of the current week")
    async def matchups(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.state.league_lock:
            fan_league:League = self.bot.state.league
        week = fan_league.current_week

        embed = discord.Embed(title = f'Week {week} Matchups', url=fan_league.url, description = '', color = self.emb_color)

        async with self.bot.state.fantasy_query_lock:
            matchups_list = self.bot.state.fantasy_query.get_scoreboard(week).matchups

        await FantasyQueryHelper.add_matchup_fields(matchups_list, embed)
        await interaction.followup.send(embed = embed,ephemeral=False)


    @app_commands.command(name="player_stats",description="NFL player details")
    @app_commands.describe(player_name="name")
    async def player_stats(self,interaction:discord.Interaction,player_name:str):
        await interaction.response.defer()

        async with self.bot.state.league_lock:
            league:League = self.bot.state.league
        week = league.current_week

        name, player_id = await FantasyQueryHelper.find_closest_name(player_name, self.bot.state.persistent_manager, self.player_ids_filename)
        if player_id is None:
            await interaction.followup.send("Doesn't exist or you need to spell better.")
            return


        async with self.bot.state.fantasy_query_lock:
            # weekly stats
            player = self.bot.state.fantasy_query.get_player_stats(player_id)
            team_stats = self.bot.state.fantasy_query.team_stats(player_id,week)

        # create embed
        embed = discord.Embed(title = f'{name}', url=player.url, description = f'#{player.uniform_number}, {player.display_position}, {player.editorial_team_full_name}', color = self.emb_color)
        embed.set_thumbnail(url = player.image_url)

        if player.has_player_notes:
            embed.add_field(name = 'Status',value =utility.to_red_text(f'{player.status_full} {player.injury_note}'),inline=True)
        embed.add_field(name = 'Points', value = utility.to_block(team_stats.player_points.total), inline=True)

        # season points
        async with self.bot.state.fantasy_query_lock:
            season_league = self.bot.state.fantasy_query.get_league_stats(player_id)['league']

        season_stats = season_league.players[0]
        embed.add_field(name = 'Season Pts', value = utility.to_block(season_stats.player_points.total))
        embed.add_field(name = '\u200b', value = '\u200b', inline= False) 

        # footer
        async with self.bot.state.fantasy_query_lock:
            ownership_result:League = self.bot.state.fantasy_query.get_ownership(player_id)['league']  

        # ownership result always list of size 1
        if len(ownership_result.players[0].ownership.teams) != 0:
            embed.set_footer(text = 'Manager: ' + ownership_result.players[0].ownership.teams[0].name.decode('utf-8'))
        
        # List Stats
        stats_list = team_stats.player_stats.stats
        for i in range(len(stats_list)):
            async with self.bot.state.fantasy_query_lock:
                embed.add_field(name = self.bot.state.fantasy_query.stat_dict.get(str(stats_list[i].stat_id)), value = utility.to_block(f'{stats_list[i].value:3.1f}'), inline = True)

        await interaction.followup.send(embed=embed,ephemeral=False)


    @app_commands.command(name="leaderboard",description="Fantasy Leaderboard")
    async def leaderboard(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.state.fantasy_query_lock:
            standings = self.bot.state.fantasy_query.get_all_standings(self.bot.state.league.num_teams)

        sorted_standings = sorted(standings, key = lambda tup: int(tup[1].rank))

        # load names 
        players_dict_list = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)
        #utility.load_members()
        embed = discord.Embed(title = 'Current Rankings', url='', description = '', color = self.emb_color)
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
    async def most_points(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.state.fantasy_query_lock:
            standings = self.bot.state.fantasy_query.get_all_standings(self.bot.state.league.num_teams)

        sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_for), reverse = True)

        # load names 
        players_dict_list = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)
        #utility.load_members()
        embed = discord.Embed(title = 'Current Rankings', url='', description = '', color = self.emb_color)
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
    async def points_against(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.state.fantasy_query_lock:
            standings = self.bot.state.fantasy_query.get_all_standings(self.bot.state.league.num_teams)

        sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_against), reverse = True)

        # load names 
        players_dict_list = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)
        #utility.load_members()
        embed = discord.Embed(title = 'Current Rankings', url='', description = '', color = self.emb_color)
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


    async def highest_scoring(self, matchups_list):
        highest_scoring_team_pts = -1

        for i in range(len(matchups_list)):
            team_list = matchups_list[i].teams
            
            for team in team_list:
                if highest_scoring_team_pts == -1:
                    highest_scoring_team_pts = team.team_points.total
                    highest_url = team.url
                    highest_name = team.name
                
                elif team.team_points.total > highest_scoring_team_pts:
                    highest_scoring_team_pts = team.team_points.total
                    highest_url = team.url
                    highest_name = team.name

        return (highest_scoring_team_pts, highest_name, highest_url)


    async def lowest_scoring(self, matchups_list):
        lowest_scoring_team_pts = 10000

        for i in range(len(matchups_list)):
            team_list = matchups_list[i].teams
            
            for team in team_list:
                if lowest_scoring_team_pts == 10000:
                    lowest_scoring_team_pts = team.team_points.total
                    lowest_url = team.url
                    lowest_name = team.name
                
                elif team.team_points.total < lowest_scoring_team_pts:
                    lowest_scoring_team_pts = team.team_points.total
                    lowest_url = team.url
                    lowest_name = team.name

        return (lowest_scoring_team_pts, lowest_name, lowest_url)


    async def highest_margin_win(self, matchups_list):
        highest_margin_team_pts = 0
        winning_name = ""
        winning_pts = 0
        losing_name = ""
        losing_pts = 0

        for i in range(len(matchups_list)):
            team_list = matchups_list[i].teams

            if len(team_list) == 2:
                current_margin_pts = abs(team_list[0].team_points.total - team_list[1].team_points.total)

                if current_margin_pts > highest_margin_team_pts:
                    highest_margin_team_pts = current_margin_pts

                    if team_list[0].team_points.total > team_list[1].team_points.total:
                        winning_name = team_list[0].name
                        winning_pts = team_list[0].team_points.total
                        losing_name = team_list[1].name
                        losing_pts = team_list[1].team_points.total
                    else:
                        winning_name = team_list[1].name
                        winning_pts = team_list[1].team_points.total
                        losing_name = team_list[0].name
                        losing_pts = team_list[0].team_points.total

        return (highest_margin_team_pts, winning_pts, losing_pts,winning_name,losing_name)


    async def lowest_margin_win(self, matchups_list):
        lowest_margin_team_pts = 10000
        winning_name = ""
        winning_pts = 0
        losing_name = ""
        losing_pts = 0
    
        for i in range(len(matchups_list)):
            team_list = matchups_list[i].teams

            if len(team_list) == 2:
                current_margin_pts = abs(team_list[0].team_points.total - team_list[1].team_points.total)

                if current_margin_pts < lowest_margin_team_pts:
                    lowest_margin_team_pts = current_margin_pts

                    if team_list[0].team_points.total > team_list[1].team_points.total:
                        winning_name = team_list[0].name
                        winning_pts = team_list[0].team_points.total
                        losing_name = team_list[1].name
                        losing_pts = team_list[1].team_points.total
                    else:
                        winning_name = team_list[1].name
                        winning_pts = team_list[1].team_points.total
                        losing_name = team_list[0].name
                        losing_pts = team_list[0].team_points.total

        return (lowest_margin_team_pts, winning_pts, losing_pts,winning_name,losing_name)


    @app_commands.command(name="recap",description="Last week's recap.")
    async def recap(self,interaction:discord.Interaction):
        await interaction.response.defer()
        newln = '\n'

        async with self.bot.state.fantasy_query_lock:
            fantasy_league = self.bot.state.fantasy_query.get_league()['league']

        week = fantasy_league.current_week
        last_week = week - 1

        if last_week <= 0:
            await interaction.followup.send("Error: Week 1 hasn't ended.",ephemeral=False)

        async with self.bot.state.fantasy_query_lock:
            matchups_list = self.bot.state.fantasy_query.get_scoreboard(last_week).matchups

        # search for lowest points and highest
        highest_scoring_team_pts, highest_scoring_team, highest_scoring_url = await self.highest_scoring(matchups_list)
        highest_margin_pts, highest_margin_winner_pts, highest_margin_loser_pts,highest_margin_winning_name, highest_margin_losing_name = await self.highest_margin_win(matchups_list)

        lowest_scoring_team_pts, lowest_scoring_team, lowest_scoring_url = await self.lowest_scoring(matchups_list)
        lowest_margin_pts, lowest_margin_winner_pts, lowest_margin_loser_pts, lowest_margin_winning_name, lowest_margin_losing_name = await self.lowest_margin_win(matchups_list)

        # embed for each stat
        embed = discord.Embed(title = f'Week {last_week} Recap', url="", description = '', color = self.emb_color) 

        # highest scoring team
        highest_scoring_team_decode = f"{highest_scoring_team.decode('utf-8')}"
        highest_formated = f"{highest_scoring_team_decode:<30} {highest_scoring_team_pts:>5.2f}"
        embed.add_field(name = "Highest Scoring Team", value = utility.to_block(highest_formated), inline = False)  
        embed.add_field(name = '\u200b', value = '\u200b', inline= False)   

        # lowest scoring team
        lowest_scoring_team_decode = lowest_scoring_team.decode('utf-8')
        lowest_formated = f"{lowest_scoring_team_decode:<30} {lowest_scoring_team_pts:>5.2f}"
        embed.add_field(name = "Lowest Scoring Team", value = utility.to_block(lowest_formated), inline = False)
        embed.add_field(name = '\u200b', value = '\u200b', inline= False)

        # largest margin victory
        highest_margin_winning_name_decode = f"{highest_margin_winning_name.decode('utf-8')}: "
        highest_margin_winning_formated = f"{highest_margin_winning_name_decode:<30} {highest_margin_winner_pts:>5.2f}"
        highest_margin_losing_name_decode = f"{highest_margin_losing_name.decode('utf-8')}: "
        highest_margin_losing_formated = f"{highest_margin_losing_name_decode:<30} {highest_margin_loser_pts:>5.2f}"
        embed.add_field(name = "Largest Margin of Victory", 
                        value = utility.to_block(f"{highest_margin_winning_formated}{newln}{highest_margin_losing_formated} "), 
                        inline = True)
        embed.add_field(name = '\u200b', value = utility.to_green_text(f"{highest_margin_pts:.2f}"), inline= True)
        embed.add_field(name = '\u200b', value = '\u200b', inline= False)

        # smallest margin victory
        lowest_margin_winning_name_decode = f"{lowest_margin_winning_name.decode('utf-8')}:"
        lowest_margin_winning_formated = f"{lowest_margin_winning_name_decode:<30} {lowest_margin_winner_pts:>5.2f}"
        lowest_margin_losing_name_decode = f"{lowest_margin_losing_name.decode('utf-8')}:"
        lowest_margin_losing_formated = f"{lowest_margin_losing_name_decode:<30} {lowest_margin_loser_pts:>5.2f}"
        embed.add_field(name = "Smallest Margin of Victory", 
                        value = utility.to_block(f"{lowest_margin_winning_formated}{newln}{lowest_margin_losing_formated}"), 
                        inline = True)
        embed.add_field(name = '\u200b', value = utility.to_green_text(f"{lowest_margin_pts:.2f}"), inline= True)

        await interaction.followup.send(embed = embed,ephemeral=False)


    ###################################################
    # Recap
    ###################################################

    async def serialize_matchups(self,scoreboard:Scoreboard):
        """
        Serialize matchups data to a dictionary.
            Args:
                scoreboard (object): YFPY Scoreboard object
            Returns:    
                dict: Serialized matchups data
        """
  
        def to_serializable(value):
            if isinstance(value, bytes):
                return value.decode('utf-8')
            return value

        matchups_dict = {}
        matchups_list = scoreboard.matchups

        for i in range(len(matchups_list)):
            team_list = matchups_list[i].teams

            individual_dict_1 = {}
            individual_dict_2 = {}
            if len(team_list) == 2:
                individual_dict_1['name'] = to_serializable(team_list[0].name)
                individual_dict_1['id'] = to_serializable(team_list[0].team_id)
                individual_dict_1['points'] = team_list[0].team_points.total
                individual_dict_1['week'] = team_list[0].team_points.week
                individual_dict_1['team_key'] = to_serializable(team_list[0].team_key)
                individual_dict_1['faab'] = team_list[0].faab_balance
                individual_dict_1['opponent_id'] = to_serializable(team_list[1].team_id)
                individual_dict_1['opponent_name'] = to_serializable(team_list[1].name)

                individual_dict_2['name'] = to_serializable(team_list[1].name)
                individual_dict_2['id'] = to_serializable(team_list[1].team_id)
                individual_dict_2['points'] = team_list[1].team_points.total
                individual_dict_2['week'] = team_list[1].team_points.week
                individual_dict_2['team_key'] = to_serializable(team_list[1].team_key)
                individual_dict_2['faab'] = team_list[1].faab_balance
                individual_dict_2['opponent_id'] = to_serializable(team_list[0].team_id)
                individual_dict_2['opponent_name'] = to_serializable(team_list[0].name)

                matchups_dict[individual_dict_1['id']] = individual_dict_1
                matchups_dict[individual_dict_2['id']] = individual_dict_2
            else:
                individual_dict_1['name'] = to_serializable(team_list[0].name)
                individual_dict_1['id'] = to_serializable(team_list[0].team_id)
                individual_dict_1['points'] = team_list[0].team_points.total
                individual_dict_1['week'] = team_list[0].team_points.week
                individual_dict_1['team_key'] = to_serializable(team_list[0].team_key)
                individual_dict_1['faab'] = team_list[0].faab_balance
                individual_dict_1['opponent_id'] = 'NONE'
                individual_dict_1['opponent_name'] = 'NONE'

        return matchups_dict


    async def log_season(self,fantasy_league_info):
        #for every week log the matchup results
        for i in range(fantasy_league_info.start_week, fantasy_league_info.end_week + 1):

            async with self.bot.state.fantasy_query_lock:  
                current_week_obj = self.bot.state.fantasy_query.get_scoreboard(i)

            filename = f"week_{i}_matchup.json"
            serialized_data = await self.serialize_matchups(current_week_obj)
            await self.bot.state.recap_manager.write_json(filename=filename, data = serialized_data)


    @tasks.loop(minutes=1440)
    async def store_data(self):

        async with self.bot.state.league_lock:
            fantasy_league_info = self.bot.state.league

        end_date = fantasy_league_info.end_date
        end_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date() 
        today_obj = datetime.date.today()

        if end_obj < today_obj:
            await self.log_season(fantasy_league_info)
        else:
            logger.info('[FantasyQuery] - Fantasy season has not ended.')


    @app_commands.command(name="season_recap",description="Season Recap.")
    async def season_recap(self,interaction:discord.Interaction):
        await interaction.response.defer()


        await interaction.followup.send("Filler",ephemeral=False)


    ###################################################
    # Error Handling         
    ###################################################

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):

        message = ""
        if isinstance(error, app_commands.CommandNotFound):
            message = "This command does not exist."
        elif isinstance(error, app_commands.CheckFailure):
            message = "You do not have permission to use this command."
        else:
            message = "An error occurred. Please try again."

        logger.error(f"[FantasyQuery] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[FantasyQuery] - Failed to send error message: {e}")

    ###################################################
    # Loop Error Handling          
    ###################################################

    @store_data.error
    async def store_data_error(self,error):
        logger.error(f'[FantasyQuery][store_data] - Error: {error}')


    ###################################################
    # Handle Load          
    ###################################################

    async def cog_load(self):
        logger.info('[FantasyQuery] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)
        

    ###################################################
    # Handle Startup          
    ###################################################

    async def wait_for_fantasy(self):
        while not self._ready:
            async with self.bot.state.fantasy_query_lock:
                fantasy_query = self.bot.state.fantasy_query
            if fantasy_query is not None:
                self._ready = True
            else:
                await asyncio.sleep(1)


    @commands.Cog.listener()
    async def on_ready(self):
        await self.wait_for_fantasy()
        logger.info('[FantasyQuery][store_data] - Starting!')
        self.store_data.start()
        logger.info('[FantasyQuery] - Ready')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[FantasyQuery] - Cog Unload')


async def setup(bot):
    await bot.add_cog(FantasyQuery(bot))