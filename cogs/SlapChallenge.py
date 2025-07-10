import discord
from discord import app_commands
from discord.ext import commands

import asyncio
from datetime import datetime, date, timedelta
from pathlib import Path

from yfpy.models import GameWeek

from bet_vault.vault import Vault
import utility
from cogs_helpers import FantasyHelper

import logging
logger = logging.getLogger(__name__)

class SlapChallenge(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

        self._ready = False
        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent

        # keep track of active view instances
        self.active_views:list[SlapChallenge.AcceptDenyChallenge] = []
        self.active_views_lock = asyncio.Lock()

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        self._private_filename = bot.state.private_filename
        self._week_dates_filename = bot.state.week_dates_filename
        self._challenges_filename = bot.state.challenges_filename
        
        # vault
        self.vault:Vault = self.bot.state.vault

        # Slap 
        self._challenge_filename = self.bot.state.challenge_config_filename
        self.loser_role_name = None
        self.denier_role_name = None
        self._challenge_send_link = None
        self._challenge_accept_link = None
        self._challenge_deny_link = None
        self._timeout_link = None
      

    #########################################################
    # Setup Button interactions for challenges 
    #########################################################

    class AcceptDenyChallenge(discord.ui.View):

        def __init__(self, challenges_filename, challenger:int, challengee:int, amount:int, week:int, expiration_date:datetime, vault:Vault, challenge_accept_link:str, challenge_deny_link:str, denier_role_name:str):
            super().__init__(timeout = 28800) # 8 hrs
            self.challenger = challenger
            self.challengee = challengee
            self.amount = amount
            self.week = week
            self.expiration:datetime = expiration_date
            self.vault:Vault = vault
            self._challenge_accept_link = challenge_accept_link
            self._challenge_deny_link = challenge_deny_link
            self.message = None #should be initialized with interaction.followup.send()

            # bot embed color
            self.emb_color = discord.Color.from_rgb(225, 198, 153)
            self.denier_role_name = denier_role_name
            self._challenges_filename = challenges_filename


        ##############################################################
        # Overloaded def
        ##############################################################

        async def interaction_check(self, interaction:discord.Interaction) -> bool:
            if interaction.user.id != self.challengee:
                await interaction.response.send_message(f"You don't want no part of this {utility.id_to_mention(interaction.user.id)}", ephemeral=True)
                return False
            return True


        async def on_timeout(self):
            for child in self.children:
                if isinstance(child,discord.ui.Button):
                    child.disabled = True

            if self.message:
                embed = discord.Embed(title = 'Slap', description = 'Challenge Expired',color = self.emb_color)
                await self.message.edit(embed = embed,view = self)


        async def on_error(interaction:discord.Interaction, error, item):
            await interaction.response.send_message(f'Error: {error}', ephemeral=True)


        ##############################################################
        # helpers
        ############################################################## 

        async def assign_role(self,member: discord.Member, role_name:str, channel: discord.TextChannel):
            guild = channel.guild
            roles = guild.roles
            role = discord.utils.get(roles,name = role_name)

            if role is None:
                logger.warning("[SlapChallenge] - Role doesn't exist.")
                return

            try:
                await member.add_roles(role)
                logger.info(f'[SlapChallenge] - {member.display_name} assigned {role_name}')
            except discord.Forbidden:
                logger.info(f'[SlapChallenge] - Do not have the necessary permissions to assign {role_name} role')
            except discord.HTTPException as e:
                logger.info(f'[SlapChallenge] - Failed to assign {role_name} role. Error: {e}')


        async def create_vault_contract(self):
            await Vault.create_contract(
                challenger_fantasy_id=str(self.challenger),
                challengee_fantasy_id=str(self.challengee),
                amount=self.amount,
                expiration_date=self.expiration,
                week=self.week,
                contract_type=Vault.SlapContract.__name__
            )


        @discord.ui.button(label="Accept", style=discord.ButtonStyle.primary)
        async def button_callback(self, interaction:discord.Interaction, button:discord.Button):
            # disable current button
            button.disabled = True

            # disable all other buttons
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            
            # create vault contract
            try:
                await self.create_vault_contract(self.challenger, self.challenger, self.amount, self.expiration)
            except Exception as e:
                embed = discord.Embed(title='Slap', 
                    description = 'Failed to create contract for challenge.',
                    color = self.emb_color)
                await interaction.response.edit_message(embed = embed, view=self)
                logger.error(f'[SlapChallenge][AcceptDenyChallenge] - {e}')
                return

            embed = discord.Embed(title='Slap', description = f'{utility.id_to_mention(self.challengee)} has accepted {utility.id_to_mention(self.challenger)}\'s challenge.',color = self.emb_color)
            embed.set_image(url = self._challenge_accept_link)
            await interaction.response.edit_message(embed = embed, view=self)


        @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
        async def second_button_callback(self, interaction:discord.Interaction, button:discord.Button):
            button.disabled = True

            for child in self.children:
                if isinstance(child,discord.ui.Button):
                    child.disabled = True
            embed = discord.Embed(title='Slap', description = f'{utility.id_to_mention(self.challengee)} has denied {utility.id_to_mention(self.challenger)}\'s challenge.',color = self.emb_color)
            embed.set_image(url = self._challenge_deny_link)

            # give them the denier_role
            channel = interaction.channel
            member = interaction.user

            await self.assign_role(member,self.denier_role_name,channel)
            await interaction.response.edit_message(embed = embed, view=self)


    ###################################################################
    # Slap Command
    ###################################################################

    async def setup_slap_channel(self,channel_id:int) -> None:
        async with self.bot.state.slaps_channel_id_lock:
            if self.bot.state.slaps_channel_id is not None:
                return
            else:
                self.bot.state.slap_channel_id = channel_id

        # save channel id to persistent data
        data = await self.bot.state.discord_auth_manager.load_json(filename = self._private_filename)
        data.update({'channel_id': channel_id})
        await self.bot.state.discord_auth_manager.write_json(filename = self._private_filename, data = data)


    @app_commands.command(name="slap",description="Slap Somebody. Loser=Chump. Denier=Pan")
    @app_commands.describe(discord_user="Target's Discord Tag", amount='Tokens to wager.')
    async def slap(self,interaction:discord.Interaction, discord_user:discord.User, amount:int):
        await interaction.response.defer()

        async with self.bot.state.league_lock:
            fantasy_league = self.bot.state.league

        # make sure channel is set
        await self.setup_slap_channel(interaction.channel.id)
            
        if not await FantasyHelper.season_started(fantasy_league=fantasy_league):
            return

        if await FantasyHelper.season_over(fantasy_league=fantasy_league):
            return
        
        # cant challenge someone on first day of the week
        current_week = fantasy_league.current_week
        start_datetime, end_date = await FantasyHelper.get_current_week_dates(self.bot, current_week, self._week_dates_filename)
        expiration_date = end_date + timedelta(days = 1)
        today_date = date.today()

        if today_date == start_datetime.date():
            embed = discord.Embed(title='Slap someone tomorrow.', description = f'Challenges start {start_datetime.date() + timedelta(days=1)}.',color = self.emb_color)
            embed.set_image(url = self._timeout_link)
            await interaction.followup.send(embed = embed,ephemeral=False)
            return

        # create a challenge with buttons for accept and deny
        challengee_discord_id = discord_user.id
        challenger_discord_id = interaction.user.id

        description_text = f'{utility.id_to_mention(challenger_discord_id)} challenged {utility.id_to_mention(challengee_discord_id)} to a duel.'
        embed = discord.Embed(title = 'Slap', description = description_text,color = self.emb_color)
        embed.set_image(url = self._challenge_send_link)

        # create view and store it for the future
        view = self.AcceptDenyChallenge(
            self._challenge_filename,
            challenger=challenger_discord_id,
            challengee=challengee_discord_id,
            amount=amount, 
            week=current_week,
            expiration_date=expiration_date, 
            vault=self.bot.state.vault,
            challenge_accept_link=self._challenge_accept_link,
            challenge_deny_link=self._challenge_deny_link,
            denier_role_name=self.denier_role_name 
        )
        
        async with self.active_views_lock:
            self.active_views.append(view)

        message = await interaction.followup.send(embed = embed, view = view)
        view.message = message


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
        logger.error(f"[SlapChallenge] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[SlapChallenge] - Failed to send error message: {e}")


    ####################################################
    # Setup
    ####################################################

    async def setup_discord(self):
        data = await self.bot.state.discord_auth_manager.load_json(filename = self._private_filename)

        channel_id = data.get('channel_id')
        if channel_id is not None:
            self.bot.state.slaps_channel_id = int(channel_id)
        else:
            self.bot.state.slaps_channel_id = None


    async def load_challenge_variables(self):
        data = await self.bot.state.settings_manager.load_json(filename = self._challenge_filename)
        self.loser_role_name=data.get("loser_role_name")
        self.denier_role_name=data.get("denier_role_name")
        self._challenge_send_link=data.get("challenge_send_link")
        self._challenge_accept_link=data.get("challenge_accept_link")
        self._challenge_deny_link=data.get("challenge_deny_link")


    ###################################################
    # Handle Load           
    ###################################################

    async def cog_load(self):
        logger.info('[SlapChallenge] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


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
        await self.setup_discord()
        await self.load_challenge_variables()
        logger.info('[SlapChallenge] - Ready')


    ###################################################
    # Handle Exit          
    ###################################################    

    def cog_unload(self):
        logger.info('[SlapChallenge] - Cog Unload')


async def setup(bot):
    await bot.add_cog(SlapChallenge(bot))