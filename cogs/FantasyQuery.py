import discord
from discord import app_commands
from discord.ext import tasks, commands

from typing import Optional
import pandas as pd

from cogs_helpers import FantasyQueryHelper, FantasyHelper
import utility

import asyncio
from pathlib import Path
import requests

import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import numpy as np
import seaborn as sns
import pandas as pd
from io import BytesIO
import imageio

from difflib import get_close_matches
from yfpy.models import Scoreboard, League, Matchup, Team, Player, Roster, Name, TeamStandings

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

        # loaded files
        self.player_ids_filename = bot.state.player_ids_filename
        self.members_filename = bot.state.members_filename
        self._private_filename = bot.state.private_filename

        # generated files
        self._roster_csv = bot.state.roster_csv
        self._matchup_csv = bot.state.matchup_csv

        # bot embed color
        self.emb_color = self.bot.state.emb_color
        self.winner_color = self.bot.state.winner_color
        self.loser_color = self.bot.state.loser_color

        # Season Dates
        self._week_dates_filename = bot.state.week_dates_filename

        # File Name Templates
        self.roster_json_template = bot.state.roster_json_template
        self.matchup_json_template = bot.state.matchup_json_template
        self._matchup_standings_template = bot.state.matchup_standings_template

        # Settings
        self._settings_manager = bot.state.settings_manager
        self._settings_config_filename = bot.state.bot_features.feature_settings_config_filename


    ###################################################
    # Bind Commands USER         
    ###################################################

    class TeamSelectConfirmView(discord.ui.View):
        def __init__(self, outer: "FantasyQuery", selected_members:list, options:list):
            super().__init__()
            self.outer = outer
            self.bot = outer.bot
            self.members_filename = self.bot.state.members_filename
            self.selected_members = selected_members
            self.options = options

        async def disable_buttons(self):
            for child in self.children:
                if isinstance(child,discord.ui.Button):
                    child.disabled = True

        ##############################################################
        # Overloaded def -  Errors
        ##############################################################

        async def on_timeout(self):
            await self.disable_buttons()

            if self.message:
                embed = discord.Embed(title = 'Bind', description = 'Operation Expired',color = self.emb_color)
                await self.message.edit(embed = embed,view = self)


        async def on_error(self,interaction:discord.Interaction, error, item):
            if interaction.response.is_done():
                await interaction.followup.send(f'Error: {error}', ephemeral=True)
            else:
                await interaction.response.send_message(f'Error: {error}', ephemeral=True)


        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary)
        async def confirm(self, interaction:discord.Interaction, button:discord.Button):
            await interaction.response.defer()
            await self.disable_buttons()

            selected_member = self.selected_members[0]
            discord_id = interaction.user.id

            members = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)
            await self.outer.bind_discord(members, selected_member, discord_id)
            await self.bot.state.persistent_manager.write_json(filename=self.members_filename, data=members)
           
            label_list = [option.label for option in self.options if option.value == selected_member]

            await interaction.followup.send(f"Bound {utility.id_to_mention(discord_id)} to {label_list[0]}")


        @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
        async def second_button_callback(self, interaction:discord.Interaction, button:discord.Button):
            await self.disable_buttons()
            await interaction.response.send_message(f"Canceled operation.", ephemeral=True)


    class TeamSelect(discord.ui.Select):
        def __init__(self, outer: "FantasyQuery"):
            super().__init__(
                min_values=1,
                max_values=1
            )
            self.outer = outer
            self.bot = outer.bot
            self.members_filename = outer.bot.state.members_filename

        async def callback(self, interaction: discord.Interaction):
            view = FantasyQuery.TeamSelectConfirmView(self,self.values,self.options)
            await interaction.response.send_message("Are you sure?", view=view, ephemeral=True)


    async def construct_team_select(self):
        select = self.TeamSelect(self)

        members = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)
        for member in members:
            select.add_option(label=member.get('name'), value=member.get('id'), default=False)
        return select
    

    @app_commands.command(name="bind_team", description= "Select your Fantasy team.")
    async def bind_team(self,interaction:discord.Interaction):

        select = await self.construct_team_select()
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("Select your Yahoo Fantasy Team.", view=view, ephemeral=True)


    ###################################################
    # Bind Commands ADMIN        
    ###################################################

    async def bind_discord(self, members:dict, draft_id:int, discord_id:int) -> dict:
        for member in members:
            if member.get('id') == str(draft_id):
                member.update({'discord_id':str(discord_id)})
                break
        return members


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

        # Enable News Feature
        await self.bot.state.bot_features.set_news(activate = True)

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

        # Enable Slap Feature
        await self.bot.state.bot_features.set_slap(activate=True)

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

        # Enable Transactions Feature
        await self.bot.state.bot_features.set_transactions(activate=True)

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

        #sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_for), reverse = True)
        sorted_standings = sorted(standings, key = lambda tup: int(tup[1].points_for), reverse = True)

        # load names 
        players_dict_list = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)

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
        if await FantasyHelper.season_over(fantasy_league):
            last_week = week
        else:
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
    # Log Season - Save JSON DATA
    ###################################################

    async def get_player_values(self, player_name:str) -> Optional[str]:
        async with self.bot.state.value_map_lock:
            closest_key = get_close_matches(player_name,self.bot.state.value_map,n=1,cutoff=0.6)
        if len(closest_key) == 0:
            return None
        else:
            return self.bot.state.value_map.get(closest_key[0])

    async def format_player_data(self, player_dict:dict, player_specific:dict):
        player_dict['age'] = player_specific.get('maybeAge')
        player_dict['yoe'] = player_specific.get('maybeYoe')
        player_dict['weight'] = player_specific.get('maybeWeight')
        player_dict['height'] = player_specific.get('maybeHeight')


    async def format_values(self, player_dict:dict, player_name:str) -> None:
        values = await self.get_player_values(player_name)
        if values is None:
            return
        
        player_dict['rank'] = values.get('overallRank')
        player_dict['positional_rank'] = values.get('positionRank')
        player_dict['trend30day'] = values.get('trend30Day')
        player_dict['redraft_value'] = values.get('redraftValue')
        player_dict['dynasty_value'] = values.get('value')

        player_specific = values.get('player') 
        if player_specific:
            await self.format_player_data(player_dict, player_specific)



    async def serialize_player(self, player:Player, owner_id:str, owner_name:str, week:int):
        player_dict = {}

        name_obj:Name = player.name
        player_dict['owner_id'] = owner_id
        player_dict['owner_name'] = owner_name
        player_dict['week'] = week
        player_dict['name'] = name_obj.full
        player_dict["primary_position"] = player.primary_position
        player_dict['team_name'] = player.editorial_team_full_name
        player_dict['number'] = player.uniform_number
        player_dict['player_key'] = player.player_key

        await self.format_values(player_dict, name_obj.full)
        return player_dict


    async def serialize_roster(self, roster_list:list, roster:Roster, owner_id:str, owner_name:str, week:int):
        players_list: list[Player] = roster.players

        for player in players_list:
            serialized_player = await self.serialize_player(player,owner_id, owner_name, week)
            roster_list.append(serialized_player)


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


    async def store_scoreboard(self, week:int):
        filename = self.matchup_json_template.format(week = week)
        if await self.bot.state.recap_manager.path_exists(filename):
            return
        
        async with self.bot.state.fantasy_query_lock:  
            current_week_obj = self.bot.state.fantasy_query.get_scoreboard(week)

        serialized_data = await self.serialize_matchups(current_week_obj)
        logger.info(f"creating {filename}")
        await self.bot.state.recap_manager.write_json(filename=filename, data = serialized_data)


    async def store_roster(self, week:int):
        filename = self.roster_json_template.format(week=week)
        
        if await self.bot.state.recap_manager.path_exists(filename):
            return
        
        async with self.bot.state.league_lock:
            fantasy_league = self.bot.state.league
        number_of_teams = int(fantasy_league.num_teams)
        
        roster_list = []
        for i in range(number_of_teams):
            owner_id = i + 1
            members = await self.bot.state.persistent_manager.load_json(filename=self.members_filename)
            for member in members: 
                if str(owner_id) == member.get('id'):
                    team_name = member.get('name')
        
            async with self.bot.state.fantasy_query_lock:  
                current_week_roster = self.bot.state.fantasy_query.get_roster(str(owner_id), week)
            await self.serialize_roster(roster_list, current_week_roster, str(owner_id), team_name, week)
            await asyncio.sleep(1)

        logger.info(f"creating {filename}")
        await self.bot.state.recap_manager.write_json(filename=filename, data=roster_list)


    ###################################################
    # Log season - Create Roster CSV 
    ###################################################

    async def construct_roster_DataFrame(self, start_week:int, end_week:int):
        data = []
        for i in range(start_week,end_week + 1):
            filename = self.roster_json_template.format(week=i)
            loaded_data = await self.bot.state.recap_manager.load_json(filename)
            data += loaded_data
        
        df_player_stats = pd.DataFrame(data)

        # fix empty values
        value_columns = ['trend30day', 'redraft_value', 'dynasty_value']
        df_player_stats[value_columns]=df_player_stats[value_columns].apply(pd.to_numeric, errors='coerce')
        df_player_stats[value_columns] = df_player_stats[value_columns].fillna(0).astype(int)
    
        stats_columns = ['number', 'rank', 'positional_rank', 'age', 'yoe', 'weight', 'height']
        df_player_stats[stats_columns] = df_player_stats[stats_columns].apply(pd.to_numeric, errors='coerce')
        df_player_stats[stats_columns] = df_player_stats[stats_columns][stats_columns].fillna(-1).astype(int)
        
        await self.bot.state.recap_manager.write_csv_formatted(self._roster_csv, df_player_stats)


    ###################################################
    # Log season - Create Matchup CSV 
    ###################################################

    async def modify_data_frame_winlosstie(self, df_raw:pd.DataFrame):
        df = df_raw.sort_values(by=['id', 'week']).copy()

        team_group = ['id', 'week', 'points']
        opponent_lookup = df[team_group].copy()
        opponent_lookup.rename(
            columns={
                'id' : 'opponent_id',
                'points' : 'opponent_points'
            },
            inplace=True
        )

        left_categories=['opponent_id', 'week']
        right_categories=['opponent_id', 'week']
        df_all_points = pd.merge(
            df,
            opponent_lookup,
            left_on=left_categories,
            right_on=right_categories,
            how='left'    
        )

        df_all_points['win'] = np.nan
        df_all_points['loss'] = np.nan
        df_all_points['tie'] = np.nan


        # Calculate 'win' for all matchups
        # np.where(condition, value_if_true, value_if_false)
        df_all_points['win'] = np.where(df_all_points['points'] > df_all_points['opponent_points'], 1, 0 )
        df_all_points['loss'] = np.where(df_all_points['points'] < df_all_points['opponent_points'], 1, 0)
        df_all_points['tie'] = np.where(df_all_points['points'] == df_all_points['opponent_points'], 1, 0)

        # week 15 tiebreakers, and playoffs should be ignored
        weeks_to_ignore_for_sum = (df_all_points['week'] == 15) | (df_all_points['week'] > 16)

        df_all_points['win_for_cumsum'] = np.where(weeks_to_ignore_for_sum, 0, df_all_points['win'])
        df_all_points['loss_for_cumsum'] = np.where(weeks_to_ignore_for_sum, 0, df_all_points['loss'])
        df_all_points['tie_for_cumsum'] = np.where(weeks_to_ignore_for_sum, 0, df_all_points['tie'])

        # Sort the DataFrame
        df_sorted = df_all_points.sort_values(by=['id', 'week']).copy()

        # Calculate RAW cumulative totals
        # These sums will use the 'for_cumsum' columns, so Week 15 and >16 contribute 0
        df_sorted['total_wins_raw'] = df_sorted.groupby('id')['win_for_cumsum'].transform(lambda x: x.cumsum().shift(1)).fillna(0)
        df_sorted['total_losses_raw'] = df_sorted.groupby('id')['loss_for_cumsum'].transform(lambda x: x.cumsum().shift(1)).fillna(0)
        df_sorted['total_ties_raw'] = df_sorted.groupby('id')['tie_for_cumsum'].transform(lambda x: x.cumsum().shift(1)).fillna(0)


        # For weeks that don't count towards the total (Week 15, and >16),
        # set their 'total_wins_raw' to NaN so ffill can propagate the previous valid total.
        df_sorted.loc[weeks_to_ignore_for_sum, ['total_wins_raw', 'total_losses_raw', 'total_ties_raw']] = np.nan

        # Now, forward-fill within each group
        df_sorted['total_wins'] = df_sorted.groupby('id')['total_wins_raw'].ffill().astype(int)
        df_sorted['total_losses'] = df_sorted.groupby('id')['total_losses_raw'].ffill().astype(int)
        df_sorted['total_ties'] = df_sorted.groupby('id')['total_ties_raw'].ffill().astype(int)

        # Clean up temporary columns 
        df_final = df_sorted.drop(columns=[
            'win_for_cumsum', 'loss_for_cumsum', 'tie_for_cumsum',
            'total_wins_raw', 'total_losses_raw', 'total_ties_raw'
        ])

        return df_final

    async def construct_matchups_DataFrame(self, start_week:int, end_week:int):
        def add_to_compiled(entry:dict, compiled_dict:list):
            for _, details in entry.items():
                compiled_dict.append(details)

        compiled_list = []
        for i in range(start_week,end_week + 1):
            filename=self.matchup_json_template.format(week=i)
            entry = await self.bot.state.recap_manager.load_json(filename)
            add_to_compiled(entry,compiled_list)

        df_matchups_raw = pd.DataFrame(compiled_list)

        int_values_names = ['id', 'week', 'faab', 'opponent_id']
        numeric_values_names = ['id', 'week', 'faab', 'opponent_id', 'points']
        df_matchups_raw[numeric_values_names] = df_matchups_raw[numeric_values_names].apply(pd.to_numeric, errors='coerce')
        df_matchups_raw[int_values_names] = df_matchups_raw[int_values_names].fillna(-1).astype(int)
        df_matchups_raw['points'] = df_matchups_raw['points'].fillna(0.0).astype(float)

        df_final = await self.modify_data_frame_winlosstie(df_matchups_raw)

        await self.bot.state.recap_manager.write_csv_formatted(self._matchup_csv, df_final)


    ###################################################
    # Log season - Standings    
    ###################################################

    async def add_team_urls(self, entry:dict):
        async with self.bot.state.fantasy_query_lock:
            team_list:list[Team] = self.bot.state.fantasy_query.get_league_teams()

        id = entry.get('id')
        for team in team_list:
            if id == team.team_id:
                entry['logo_url'] = team.team_logos[0].url
                entry['url'] = team.url
                break

    async def construct_standings_DataFrame(self):
        async with self.bot.state.league_lock:
            league = self.bot.state.league
        current_week = league.current_week
        filename = self._matchup_standings_template.format(week = current_week)

        if await self.bot.state.recap_manager.path_exists(filename):
            logger.info(f"[FantasyQuery][log_season] - {filename} already exists.")
            return

        async with self.bot.state.fantasy_query_lock:
            standings = self.bot.state.fantasy_query.get_all_standings(self.bot.state.league.num_teams)

        sorted_standings:list[tuple[int,TeamStandings]] = sorted(standings, key = lambda tup: int(tup[1].rank))

        standings_list = []
        for owner_id, standing in sorted_standings:
            team_name = await utility.teamid_to_name(owner_id, self.bot.state.persistent_manager)
            entry = {
                'id':owner_id,
                'team_name':team_name,
                'rank':standing.rank,
                'streak':standing.streak.value,
                'playoff_seed': standing.playoff_seed,
                'wins':standing.outcome_totals.wins,
                'losses':standing.outcome_totals.losses,
                'ties':standing.outcome_totals.ties,
                'win_percentage': standing.outcome_totals.percentage,
            }
            await self.add_team_urls(entry)
            standings_list.append(entry)

        df = pd.DataFrame(standings_list)
        await self.bot.state.recap_manager.write_csv_formatted(filename, df)


    ###################################################
    # Log season - Startup    
    ###################################################

    async def log_season(self,fantasy_league_info):
        _, end_date = await FantasyHelper.get_current_week_dates(self.bot, fantasy_league_info.current_week, self._week_dates_filename)

        today_date = datetime.date.today()
        if today_date < end_date.date():    # middle of the week, dont include
            end_week = fantasy_league_info.current_week
        else:                               # end of the season
            end_week = fantasy_league_info.current_week + 1

        logger.info("[log_season] - Season log started.")
        for i in range(fantasy_league_info.start_week, end_week):
            await self.store_scoreboard(i)
            await self.store_roster(i)

        # Store Data CSV for Graphs
        await self.construct_matchups_DataFrame(fantasy_league_info.start_week, end_week)
        await self.construct_roster_DataFrame(fantasy_league_info.start_week, end_week)
        await self.construct_standings_DataFrame()
        logger.info("[log_season] - Season log completed.")


    @tasks.loop(minutes=1440)
    async def store_data(self):
        if self.bot.state.bot_features.log_season_enabled == False:
            logger.info("[FantasyQuery][store_data] - Season Log disabled.\n To resolve, run the 'enable_log' Command." )
            return

        logger.info('[FantasyQuery][store_data] - Starting!')
        async with self.bot.state.league_lock:
            fantasy_league_info = self.bot.state.league

        current_week = fantasy_league_info.current_week
        if current_week <= 1:
            logger.info('[FantasyQuery][store_data] - Week 1 not concluded.')
            return

        await self.log_season(fantasy_league_info)


    ###################################################
    # Season Recap - Rankings Visualization
    ###################################################

    async def create_bump_chart_plot(self, df):
        def calculate_rank(group):
            group_sorted = group.sort_values(by=['total_wins', 'points'], ascending = [False, False])
            group_sorted['rank'] = range(1, len(group_sorted) + 1)
            return group_sorted

        # Narrow data to necessary columns
        necessary = ['id', 'name', 'week', 'total_wins', 'win', 'loss', 'tie', 'points']
        df_narrow = df[necessary].copy()
        df_narrow = df_narrow[df_narrow['week'] < 15]

        # Calculate Rank for plottable DataFrame
        df_plot = df_narrow.groupby('week').apply(calculate_rank, include_groups=False).reset_index(level='week')
        return df_plot


    async def plot_rank_bumpchart(self, df):
        # Gather all necessary data
        df_plot = await self.create_bump_chart_plot(df)

        # Draw
        fig, ax = plt.subplots(figsize = (18,10), facecolor="#F0F0F0")

        # Pallette
        hue_order_for_coloring = sorted(df_plot['name'].unique())
        palette = sns.husl_palette(n_colors=len(hue_order_for_coloring), h=0.01, s=0.9, l=0.4)
        name_to_color_map = dict(zip(hue_order_for_coloring, palette))

        sns.lineplot(
            data=df_plot, 
            x='week',
            y='rank',
            hue='name', 
            units='id', 
            marker='o',         
            palette=palette,    
            lw=2,               
            markersize=8,
            ax=ax,
            hue_order=hue_order_for_coloring,
            legend=False   
        )

        # rank 1 at top
        ax.invert_yaxis() # Invert y-axis

        # labels
        max_rank_display = df_plot['rank'].max()
        ax.set_facecolor("#DDEEEE")
        ax.set_yticks(range(1, max_rank_display + 1)) 
        ax.set_xticks(range(df_plot['week'].min(), df_plot['week'].max() + 1)) 
        ax.set_title('Regular Season - Team Ranks', fontsize=16) 
        ax.set_xlabel('Week', fontsize=12) 
        ax.set_yticklabels([]) 
        ax.set_ylabel('Rank', fontsize=12) 
        ax.grid(True, linestyle='--', alpha=0.7) 

        # annotations
        unique_ids:list = df_plot['id'].unique()
        id_to_name_map = df_plot[['id', 'name']].drop_duplicates(subset=['id'], keep='last').set_index('id')['name'].to_dict()

        players_for_annotation = []
        for player_id in unique_ids:
            player_name = id_to_name_map.get(player_id)
            players_for_annotation.append({'id': player_id, 'name': player_name})
        
        for player_data in players_for_annotation:
            player_id = player_data['id']
            player_name_for_label = player_data['name'] 

            # Determine the color based on the player's name used in the label
            line_color = name_to_color_map.get(player_name_for_label, 'black') 

            # Annotate start rank
            start_data = df_plot[(df_plot['id'] == player_id) & (df_plot['week'] == df_plot['week'].min())]
            if not start_data.empty:
                ax.text(
                        start_data['week'].iloc[0] - 0.75, start_data['rank'].iloc[0], player_name_for_label, 
                        ha='right', va='center', fontsize=12, color=line_color
                    )

            # Annotate end rank
            end_data = df_plot[(df_plot['id'] == player_id) & (df_plot['week'] == df_plot['week'].max())]
            if not end_data.empty:
                ax.text(
                        end_data['week'].iloc[0] + 0.75, end_data['rank'].iloc[0], player_name_for_label, 
                        ha='left', va='center', fontsize=12, color=line_color
                    )

        fig.tight_layout() 
        
        # Save the figure to the globally defined output directory
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        return buf


    ###################################################
    # Season Recap - Radial Cumulative
    ###################################################

    async def create_points_DataFrame(self, df):
        df['week'] = pd.to_numeric(df['week'], errors='coerce').fillna(-1).astype(int)
        weeks = sorted(df['week'].unique())
        weeks = [w for w in weeks if w != -1] # Remove the fillna value if it was used

        all_ids = df['id'].unique() # Get all unique IDs
        all_weeks = sorted(df['week'].unique())
        all_weeks = [w for w in all_weeks if w != -1]

        # Create a base DataFrame with all ID-Week combinations for rows
        index = pd.MultiIndex.from_product([all_ids, all_weeks], names=['id', 'week'])
        full_index_df = pd.DataFrame(index=index)

        # Merge the original data with the full index.
        filled_df = pd.merge(
            df[['id', 'week', 'points', 'name']],   # left data frame
            full_index_df.reset_index(),            # right dataframe. convert index into columns.
            on=['id', 'week'],                      # columns to join
            how='right'                             # join type
        )                           

        # Fill any NaN with 0
        filled_df['points'] = pd.to_numeric(filled_df['points'], errors='coerce').fillna(0)

        # Sort by ID and Week to ensure correct cumulative sum and name propagation
        filled_df = filled_df.sort_values(by=['id', 'week'])

        # Calculate cumulative points based on 'id'
        filled_df['cumulative_points'] = filled_df.groupby('id')['points'].cumsum()

        # Forward-fill 'name' within each 'id' group.
        filled_df['name'] = filled_df.groupby('id')['name'].ffill()

        # If any IDs appear in 'all_ids' but never had an entry with a 'name'
        filled_df['name']=filled_df['name'].fillna(value="Unknown Player")

        return filled_df, all_ids, weeks, 


    async def generate_points_frame(self, filled_df, week, color_map) -> BytesIO:
        # Select data for the current week.
        data_to_plot = filled_df[filled_df['week'] == week][['id', 'name', 'cumulative_points']].copy()
        data_to_plot = data_to_plot.sort_values(by='cumulative_points', ascending=False)

        fig = plt.figure(figsize=(12, 6), facecolor="#FDF5E2")
        colors_for_frame = [color_map[player_id] for player_id in data_to_plot['id']]

        ax = sns.barplot(
            data=data_to_plot,
            x='cumulative_points',
            y='name', # Display 'name'
            hue='name',
            orient='h',
            legend=False,
            order=data_to_plot['name'], # Order by sorted names
            palette=colors_for_frame,
            ax=fig.gca()
        )

        ax.set_facecolor("#E6F2EB")
        plt.title(f"Cumulative Points – Week {week}")
        plt.xlabel("Total Points")
        plt.ylabel("Player")
        plt.tight_layout()

        # Add labels to the bars
        for i, row in enumerate(data_to_plot.itertuples()):

            player_id = row.id
            cumulative = row.cumulative_points

            this_week_points = filled_df[(filled_df['week'] == week) & (filled_df['id'] == player_id)]['points']

            if not this_week_points.empty:
                label = f"+{float(this_week_points.iloc[0]):.1f}"
            else:
                label = "+0"

            text_x_pos = cumulative - 1 if cumulative > 0 else 0.5
            text_color = 'white' if cumulative > ax.get_xlim()[1] * 0.2 else 'black'

            ax.text(
                text_x_pos,
                i,
                label,
                va='center',
                ha='right',
                fontsize=8,
                color=text_color,
                weight='bold'
            )

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        return buf


    async def generate_cumulative_frames(self, df_original: pd.DataFrame) -> list[BytesIO]:
        df = df_original.copy()
        filled_df, all_ids, weeks = await self.create_points_DataFrame(df)

        num_players = len(all_ids)
        player_colors = sns.color_palette("husl", num_players)
        color_map = {player_id: player_colors[i] for i, player_id in enumerate(all_ids)}

        frames_list = []
        for week in weeks:
            frame = await self.generate_points_frame(filled_df, week, color_map)
            frames_list.append(frame)

        return frames_list


    async def convert_buffers_list_to_gif_buffer(self,buffers:list[BytesIO], fps=0.5) -> BytesIO:
        frames = []
        for buf in buffers:
            frames.append(imageio.v3.imread(buf))

        gif_buffer = BytesIO()
        imageio.v3.imwrite(gif_buffer, frames, format='GIF', extension='.gif', fps=fps, loop=0)
        gif_buffer.seek(0)
        return gif_buffer


    ###################################################
    # Season Recap - Podium
    ###################################################

    async def load_image_from_url(self, url, placeholder_url="https://placehold.co/80x80/cccccc/000000?text=IMG+Error"):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status() # Raise an exception for bad status codes
            img_array = imageio.v3.imread(BytesIO(response.content))
            return img_array
        except (requests.exceptions.RequestException, IOError) as e: # Removed Image.UnidentifiedImageError as it's PIL-specific
            logger.error(f"Warning: Could not load image from {url}. Error: {e}. Using placeholder.")
            # Load placeholder image if primary fails
            placeholder_response = requests.get(placeholder_url, timeout=5)
            placeholder_response.raise_for_status()
            placeholder_img_array = imageio.v3.imread(BytesIO(placeholder_response.content))
            return placeholder_img_array


    async def prepare_ranks_dataframe(self, df_raw):
        df = df_raw.copy()

        # generate plot dataframe 
        df = df.sort_values(by=['rank'])
        number_of_teams = len(df)

        max_y = 100 
        min_y = 10 
        log_spaced_values = np.linspace(max_y, min_y, number_of_teams)
        df['y_level'] = log_spaced_values

        return df


    async def plot_images_podium(self, df_raw):
        df = await self.prepare_ranks_dataframe(df_raw)

        fig, ax = plt.subplots(figsize=(18, 10),facecolor="#DDEEEE") # Adjust figure size for better aspect ratio

        # Colors for podium
        podium_colors = {
            1: '#FFD700', # Gold for 1st
            2: '#B0C4DE', # Silver for 2nd
            3: '#B8860B'  # Bronze for 3rd
        }
        other_rank_color = 'rosybrown' 
        bar_colors = [podium_colors.get(rank, other_rank_color) for rank in df['rank']]

        # define bars
        bar_width = .9
        bars = ax.bar(df['rank'], df['y_level'], color=bar_colors, width=bar_width )

        ax.set_facecolor("#DDEEEE")
        ax.set_title('Team Rankings', fontsize=16, pad=10) # Add a title
        ax.set_xlabel('', fontsize=12) # Label the x-axis as Rank
        ax.set_xticks(df['rank'])
        ax.set_xticklabels([])

        # padding
        x_padding_factor = 0.8 # Adjust this (e.g., 0.5 to 1.0) for more/less padding
        ax.set_xlim(df['rank'].min() - x_padding_factor, df['rank'].max() + x_padding_factor)
        max_image_display_height_in_data_units = df['y_level'].max() * 0.2
        # Modify this line in your code:
        ax.set_ylim(0, df['y_level'].max() + max_image_display_height_in_data_units * 1.5)

        ax.set_ylabel('')
        ax.set_yticklabels([])
        ax.tick_params(axis='y', length=0)
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)

        ax.set_axisbelow(True)

        vertical_space_for_image_and_text = df['y_level'].max() * 0.25 # e.g., 25% of tallest bar's height

        # Add Team Logo images
        for i, bar in enumerate(bars):
            player_data = df.iloc[i]
            image_url = player_data['logo_url']

            img_array = await self.load_image_from_url(image_url) 
            
            # Calculate image position (extent for ax.imshow)
            x_center = bar.get_x() + bar.get_width() / 2
            y_bottom = bar.get_height() + (df['y_level'].max() * 0.02) # Small offset above bar
        
            ax.autoscale(False)
            target_display_width = 80 # Match or slightly less than bar width
            img_actual_width = img_array.shape[1]  # pixel width
            zoom = target_display_width / img_actual_width
            imagebox = OffsetImage(img_array, zoom=zoom, interpolation='bilinear')
            y_bottom_of_image = bar.get_height() + (df['y_level'].max() * 0.02) 
            ab = AnnotationBbox(
                imagebox, 
                (x_center, y_bottom), 
                frameon=False, 
                box_alignment=(0.5, 0)
            )
            ax.add_artist(ab)

            text_y_pos = y_bottom_of_image + (vertical_space_for_image_and_text * 0.8) # Place text above image
            
            ax.text(x_center, text_y_pos,
                    f"{player_data['team_name']}",
                    ha='center', va='bottom', fontsize=12, color='black',
                )

        fig.tight_layout()

        # Save the figure to the globally defined output directory
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        return buf


    @app_commands.command(name="season_recap",description="Season Recap.")
    async def season_recap(self,interaction:discord.Interaction):
        await interaction.response.defer()
        async with self.bot.state.league_lock:
            league = self.bot.state.league
        current_week = league.current_week

        embed_list = []

        # Generate podium embed
        podium_filename=self._matchup_standings_template.format(week=current_week)
        df_podium = await self.bot.state.recap_manager.load_csv_formatted(podium_filename)
        podium_buff = await self.plot_images_podium(df_podium)

        podium_filename = 'podium.png'
        podium_file = discord.File(podium_buff, filename=podium_filename)
        podium_embed = discord.Embed(title = "Season Recap", description = "Post Season Rankings", color = self.emb_color)
        podium_embed.set_image(url=f'attachment://{podium_filename}')
        embed_list.append((podium_embed, podium_file))


        # Generate rankings visualization for non-playoff weeks
        df_raw = await self.bot.state.recap_manager.load_csv_formatted(self._matchup_csv)
        df_matchups_raw = df_raw.copy()
        bump_buff = await self.plot_rank_bumpchart(df_matchups_raw)

        bump_filename = 'season_bump_chart.png'
        bump_file = discord.File(bump_buff, filename=bump_filename)
        bump_embed = discord.Embed(title = "Season Recap", description = "Regular Post Rankings", color = self.emb_color)
        bump_embed.set_image(url=f'attachment://{bump_filename}')
        embed_list.append((bump_embed, bump_file))


        # Generate cumulative points chart
        df = df_raw.copy()
        buffer_list:list[BytesIO] = await self.generate_cumulative_frames(df)
        if buffer_list:
            cumul_filename = 'cumulative_points.gif'
            gif_buffer = await self.convert_buffers_list_to_gif_buffer(buffer_list)
            cumul_file = discord.File(gif_buffer, filename=cumul_filename)
            embed_radial = discord.Embed(title = "Season Recap", description = "Total Cumulative Points Earned", color = self.emb_color)
            embed_radial.set_image(url=f'attachment://{cumul_filename}')
            embed_list.append((embed_radial, cumul_file))
            
        else:
            await interaction.followup.send("Failed to generate cumulative radial gif.",ephemeral=False)

        for file_embed, file in embed_list:
             await interaction.followup.send(embed=file_embed, file=file)


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


    async def wait_for_trade_value(self):
        while not self.bot.state.trade_value_ready:
            await asyncio.sleep(1)


    @commands.Cog.listener()
    async def on_ready(self):
        await self.wait_for_fantasy()
        await self.wait_for_trade_value()
        self.store_data.start()
        logger.info('[FantasyQuery] - Ready')


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[FantasyQuery] - Cog Unload')


async def setup(bot):
    await bot.add_cog(FantasyQuery(bot))