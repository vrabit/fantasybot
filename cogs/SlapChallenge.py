import discord
from discord import app_commands
from discord.ext import tasks,commands

import json
import asyncio
import datetime
import os
from pathlib import Path
from collections import deque

from yfpy.models import GameWeek

import utility


class SlapChallenge(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent

        # keep track of active view instances
        self.active_views = []
        self.active_views_lock = asyncio.Lock()

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        # fantasy league (League)
        self.fantasy_league = None

        # Slap 
        self.loser_role_name = 'King Chump'
        self.dave_slap = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExOTZnZ2p6cnRxcHJucXZ4bGtpcThxd3VscWY0ZTFnMzZ3ZDQ0OXMwcSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/VeXiycRe0X4IewK6WY/giphy.gif'
        self.charlie_slap = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExMWgyd3B4eHM0bms3bnloZXIyOWF4aHFqZ3ZsdzJ6cXhtN2Q4ZjZqdyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/V1xyrsMPCewzAoURLh/giphy.gif'
        self.tie_gif = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExbGs0MGJkaHc3YjN5b2p0eGp0NzY3OTkwa2ZpanpmOTVxbDFsOTN0NCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/1Q763R06W61dKBKZuM/giphy.gif'
        self.left_winner = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExNWZ4bW96dmFxN20wbWE3cWRxZXlsbW5obGd2anJxOXRoOTR6Nm9ldCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/aB4piAqj3kbTcz4s08/giphy.gif'
        self.right_winner = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExeGkybnhjZXp6bXhjdzZlZmdtbzJhdGI5OXd2b2x4dDVjZTN0M3cyeiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/G8IW5iQA4yeQ0ig0iJ/giphy.gif'
        self.timeout_gif = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3d4NjExNmFqczAyOGltb2hveXl4OHNlcGdwc2d1eGxsaWRldnNrciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/XKPFjQAYe4l3nLxcr7/giphy.gif'

        self.setup_discord()
        self.poll_slap.start()


    ###################################################
    # Assign roles         
    ###################################################

    async def get_member_by_id(self,guild: discord.Guild, user_id: int):
        member = guild.get_member(user_id)

        if member is None:
            member = await guild.fetch_member(user_id)

        return member


    async def assign_role(self,member: discord.Member, role_name:str, channel: discord.TextChannel):
        guild = channel.guild
        roles = guild.roles
        role = discord.utils.get(roles,name = role_name)

        if role is None:
            print('[SlapChallenge] - Role doesn\'t exist.')
            return
        
        try:
            await member.add_roles(role)
            print(f'[SlapChallenge] - {member.display_name} assigned {role_name}')
        except discord.Forbidden:
            print(f'[SlapChallenge] - Do not have the necessary permissions to assign {role_name} role')
        except discord.HTTPException as e:
            print(f'[SlapChallenge] - Failed to assign {role_name} role. Error: {e}')


    async def remove_role_members(self,role_name:str):

        async with self.channel_id_lock:
            local_id = self.bot.state.slaps_channel_id
        
        channel = self.bot.get_channel(local_id)
        guild = channel.guild

        role = discord.utils.get(guild.roles, name = role_name)

        if role is not None:
            for member in role.members:
                await member.remove_roles(role)


    ###################################################
    # Slap Callout Challenge         
    ###################################################

    async def display_results(self,current_week:int, challenger_key:int, challengee_deque:deque, member_storage:list):
        """
            Display the results of the slap challenge.
            Args:
                current_week (int): The current week of the fantasy league.
                challenger_key (int): The team ID of the challenger.
                challengee_deque (deque): A deque containing the team IDs of the challengees.
                member_storage (list): List to store team stats for each member.
            Returns:
                None
        """
        # get guild role name
        chump_role = self.loser_role_name

        async with self.bot.state.slaps_channel_id_lock:
            local_id = self.bot.state.slap_channel_id

        if local_id is None:
            print('[SlapChallenge] - Channel not set.')
            return

        # gather challenger info
        challenger_name = await utility.teamid_to_name(challenger_key)
        challenger_discord_id = await utility.teamid_to_discord(challenger_key)
        formatted_challenger_discord_id = utility.id_to_mention(challenger_discord_id)

        # load challenger stats into array if not already loaded
        if member_storage[int(challenger_key) - 1] is None:
            async with self.bot.state.fantasy_query_lock:
                challenger_stats = self.bot.state.fantasy_query.get_team_stats(current_week,int(challenger_key))
            member_storage[int(challenger_key) - 1] = challenger_stats
        else:
            challenger_stats = member_storage[int(challenger_key) - 1]

        # get channel for message and guild.roles
        """
        channel = self.bot.get_channel(local_id)
        guild = channel.guild
        """
        channel = self.bot.get_channel(local_id)
        guild = self.bot.state.guild
        while challengee_deque:
            # gather current challenger info
            challengee_team_id = challengee_deque.pop()
            challengee_name = await utility.teamid_to_name(challengee_team_id)
            challengee_discord_id = await utility.teamid_to_discord(challengee_team_id)
            formatted_challengee_discord_id = utility.id_to_mention(challengee_discord_id)

            # add to array for the future
            if member_storage[int(challengee_team_id) - 1] is None:
                async with self.bot.state.fantasy_query_lock:
                    challengee_stats = self.bot.state.fantasy_query.get_team_stats(current_week, int(challengee_team_id))
                member_storage[int(challengee_team_id) - 1] = challengee_stats
            else:
                member_storage[int(challengee_team_id) - 1]

            embed = discord.Embed(title = '', url='', description = '', color = self.emb_color)
            if(challenger_stats['team_points'].total > challengee_stats['team_points'].total):
                embed.add_field(name = 'Winner', value='', inline = True)
                embed.add_field(name = '', value='', inline = True)
                embed.add_field(name = 'Loser', value='', inline = True)
                embed.set_image(url = self.left_winner)

                # assign role to loser
                challengee_member = await self.get_member_by_id(guild,int(challengee_discord_id))
                await self.assign_role(challengee_member, chump_role, channel)

            elif (challenger_stats['team_points'].total < challengee_stats['team_points'].total):
                embed.add_field(name = 'Loser', value='', inline = True)
                embed.add_field(name = '', value='', inline = True)
                embed.add_field(name = 'Winner', value='', inline = True)
                embed.set_image(url = self.right_winner)

                # assign role to loser
                challenger_member = await self.get_member_by_id(guild,int(challenger_discord_id))
                await self.assign_role(challenger_member, chump_role, channel)

            else:
                embed.add_field(name = 'Loser', value='', inline = True)
                embed.add_field(name = '', value='', inline = True)
                embed.add_field(name = 'Loser', value='', inline = True)
                embed.set_image(url=self.tie_gif)

                # assign role to losers
                challenger_member = await self.get_member_by_id(guild,int(challenger_discord_id))
                challengee_member = await self.get_member_by_id(guild,int(challengee_discord_id))
                await self.assign_role(challenger_member, chump_role, channel)
                await self.assign_role(challengee_member, chump_role, channel)

            embed.add_field(name = f'{challenger_name}', value=f"{challenger_stats['team_points'].total}\n{formatted_challenger_discord_id}", inline = True)
            embed.add_field(name = 'VS', value = '', inline = True)
            embed.add_field(name = f'{challengee_name}', value=f"{challengee_stats['team_points'].total}\n{formatted_challengee_discord_id}", inline = True)
            await channel.send(embed = embed)


    async def iterate_deque(self,current_week:int, challenges_deque:dict,member_storage:list):
        """
            Iterate through the deque and display results for each challenge.
            Args:
                current_week (int): The current week of the fantasy league.
                challenges_deque (dict): The deque containing challenges. {challenger_id: deque(challengee_ids)}
                member_storage (list): List to store team stats for each member.
            Returns:
                None
        """
        for key in challenges_deque:
            await self.display_results(current_week, key, challenges_deque[key], member_storage)


    @tasks.loop(minutes=1440)
    async def remove_slap_roles(self):
        # load dates list
        loaded_dates = await utility.load_dates()

        # current week
        async with self.bot.state.fantasy_query_lock:
            fantasy_league = self.bot.state.fantasy_query.get_league()['league']   
            
        current_week = fantasy_league.current_week

        # get current week end date
        end_date = loaded_dates.get(str(current_week))
        end_obj = datetime.datetime.strptime(end_date[1], '%Y-%m-%d').date() 
        today_obj = datetime.date.today()

        if end_obj == today_obj:
            await self.remove_role_members(self.loser_role_name)
            await self.remove_role_members(self.denier_role_name)


    async def construct_date_list(self,gameweek_list:list[GameWeek]) -> dict:
        """
        Constructs a dictionary of game week dates from the gameweek list.
            
            Args:
                gameweek_list (list): List of GameWeek.

            Returns:
                dict: Dictionary with game week numbers as keys and start/end dates as values.
        """
        print('[SlapChallenge] - Constructing date list')
        dates_dict = {}
        for gameweek in gameweek_list:
            current_entry = [gameweek.start,gameweek.end]
            dates_dict[gameweek.week] = current_entry

        print("[SlapChallenge] - Date list constructed")
        return dates_dict

    @tasks.loop(minutes=1440)
    async def poll_slap(self):
        # wait for fantasy object to be set up
        await asyncio.sleep(30)

        date_file = self.parent_dir / 'persistent_data' / 'week_dates.json'

        # if does not exist, create and store dates list
        exists = os.path.exists(date_file)
        if not exists:
            print('[SlapChallenge] - Dates file does not exist. Creating new one.')
            async with self.bot.state.fantasy_query_lock:
                dates_dict = await self.construct_date_list(self.bot.state.fantasy_query.get_game_weeks_by_game_id())
                await utility.store_dates(dates_dict)

        # load dates list
        loaded_dates = await utility.load_dates()

        if self.fantasy_league is None:
            async with self.bot.state.fantasy_query_lock:
                self.fantasy_league = self.bot.state.fantasy_query.get_league()['league']   

        # check if season is over
        today_obj = datetime.date.today()
        season_end_obj = datetime.datetime.strptime(self.fantasy_league.end_date, '%Y-%m-%d').date()
        if today_obj > season_end_obj:
            print('[SlapChallenge] - Season Ended')
            return

        # Check if we are in week 1 
        current_week = self.fantasy_league.current_week
        last_week = current_week - 1
        last_weeks_dates = loaded_dates.get(str(last_week))

        if last_weeks_dates is None:
            print('[SlapChallenge] - Still in week 1')
            return

        last_week_end_date_obj = datetime.datetime.strptime(last_weeks_dates[1], '%Y-%m-%d').date() 
        yesterday_date_obj = datetime.date.today() - datetime.timedelta(days = 1)


        # check if yesterday was the end of the week
        if yesterday_date_obj == last_week_end_date_obj:
            # pop all challenges from deque
            current_challenges = utility.load_challenges()

            if not current_challenges:
                print('[SlapChallenge] - No challenges to process')
                return
             
            # member storage to prevent repeated calls to get_team_stats
            members_storage = [None] * self.fantasy_league.num_teams
            await self.iterate_deque(current_week, current_challenges,members_storage)
            utility.clear_challenges()


    class AcceptDenyChallenge(discord.ui.View):
        def __init__(self, challenger:int,challengee:int,challengee_teamid:int, challenger_teamid:int):
            super().__init__(timeout = 1800)
            self.challenger = challenger
            self.challengee = challengee
            self.challenger_teamid = challenger_teamid
            self.challengee_teamid = challengee_teamid
            self.message = None

            # bot embed color
            self.emb_color = discord.Color.from_rgb(225, 198, 153)
            self.charlie_stare = 'https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExNmlwcTQ4dzcxZWJhcHk5MHpoMXZxbDBpcWJ1bGdtam1xbGprbmZ4ZyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/GhySRlT2q4nj6SSbhC/giphy.gif'
            self.denier_role_name = 'Pan'

        async def assign_role(self,member: discord.Member, role_name:str, channel: discord.TextChannel):
            guild = channel.guild
            roles = guild.roles
            role = discord.utils.get(roles,name = role_name)

            if role is None:
                print('[SlapChallenge] - Role doesn\'t exist.')
                return
            
            try:
                await member.add_roles(role)
                print(f'[SlapChallenge] - {member.display_name} assigned {role_name}')
            except discord.Forbidden:
                print(f'[SlapChallenge] - Do not have the necessary permissions to assign {role_name} role')
            except discord.HTTPException as e:
                print(f'[SlapChallenge] - Failed to assign {role_name} role. Error: {e}')


        async def on_timeout(self):
            for child in self.children:
                if isinstance(child,discord.ui.Button):
                    child.disabled = True

            if self.message:
                embed = discord.Embed(title = 'Slap', description = 'Challenge Expired',color = self.emb_color)
                await self.message.edit(embed = embed,view = self)

        async def cleanup(self):
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True

            if self.message:
                embed = discord.Embed(title = 'Slap', description = 'Challenge Expired',color = self.emb_color)
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
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            
            utility.add_challenges(self.challenger_teamid,self.challengee_teamid)

            embed = discord.Embed(title='Slap', description = f'{utility.id_to_mention(self.challengee)} has accepted {utility.id_to_mention(self.challenger)}\'s challenge.',color = self.emb_color)
            embed.set_image(url = self.charlie_slap)

            await interaction.response.edit_message(embed = embed, view=self)

        @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
        async def second_button_callback(self, interaction, button):
            # check if correct user responding
            if interaction.user.id != self.challengee:
                await interaction.response.send_message(f'You don\'t want no part of this {utility.id_to_mention(interaction.user.id)}')
                return
            
            button.disabled = True

            for child in self.children:
                if isinstance(child,discord.ui.Button):
                    child.disabled = True
            embed = discord.Embed(title='Slap', description = f'{utility.id_to_mention(self.challengee)} has denied {utility.id_to_mention(self.challenger)}\'s challenge.',color = self.emb_color)
            embed.set_image(url = self.charlie_stare)

            # give them the denier_role
            channel = interaction.channel
            member = interaction.user

            await self.assign_role(member,self.denier_role_name,channel)
            await interaction.response.edit_message(embed = embed, view=self)


    async def setup_slap_channel(self,channel_id:int) -> None:
        async with self.bot.state.slaps_channel_id_lock:
            if self.bot.state.slaps_channel_id is not None:
                return
            else:
                self.bot.state.slap_channel_id = channel_id

        # save channel id to persistent data
        data = await utility.get_private_discord_data_async()
        data.update({'channel_id': channel_id})
        await utility.set_private_discord_data_async(data)


    @app_commands.command(name="slap",description="Slap Somebody. Loser=Chump. Denier=Pan")
    @app_commands.describe(discord_user="Target's Discord Tag")
    async def slap(self,interaction:discord.Interaction,discord_user:discord.User):
        await interaction.response.defer()

        # make sure channel is set
        await self.setup_slap_channel(interaction.channel.id)
            
        # add challenges if not on the start date
        loaded_dates = await utility.load_dates()

        async with self.bot.state.fantasy_query_lock:
            fantasy_league = self.bot.state.fantasy_query.get_league()['league']

        current_week = fantasy_league.current_week

        start_date = loaded_dates.get(str(current_week))
        if start_date is None:
            print('[SlapChallenge] - Season Ended')
            return

        start_date = datetime.datetime.strptime(start_date[0], '%Y-%m-%d').date()
        today = datetime.date.today()

        if today == start_date:
            embed = discord.Embed(title='Slap someone tomorrow.', description = 'Challenges start Wednesday.',color = self.emb_color)
            embed.set_image(url = self.timeout_gif)

            await interaction.followup.send(embed = embed,ephemeral=False)
            return

        # create a challenge with buttons for accept and deny
        challengee_discord_id =discord_user.id
        challenger_discord_id = interaction.user.id

        challengee_teamid = await utility.discord_to_teamid(challengee_discord_id)
        challenger_teamid = await utility.discord_to_teamid(challenger_discord_id)

        description_text = f'{utility.id_to_mention(challenger_discord_id)} challenged {utility.id_to_mention(challengee_discord_id)} to a duel.'
        embed = discord.Embed(title = 'Slap', description = description_text,color = self.emb_color)
        embed.set_image(url = self.dave_slap)

        view = self.AcceptDenyChallenge(challenger_discord_id,challengee_discord_id,challengee_teamid,challenger_teamid)
        async with self.active_views_lock:
            self.active_views.append(view)

        message = await interaction.followup.send(embed = embed, view = view)
        view.message = message


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
            print(f"[SlapChallenge] - Error: {error}")


    def setup_discord(self):
        with open(self.parent_dir / 'discordauth'/ 'private.json', 'r') as file:
            data = json.load(file)

        channel_id = data.get('channel_id')
        if channel_id is not None:
            self.bot.state.slaps_channel_id = int(channel_id)
        else:
            self.bot.state.slaps_channel_id = None


    ###################################################
    # Handle Load           
    ###################################################

    async def cog_load(self):
        print('[SlapChallenge] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)

    @commands.Cog.listener()
    async def on_ready(self):
        print('[SlapChallenge] - Setup SlapChallenge')


    ###################################################
    # Handle Exit          
    ###################################################    

    def cog_unload(self):
        print('[SlapChallenge] - Cog Unload')


async def setup(bot):
    await bot.add_cog(SlapChallenge(bot))