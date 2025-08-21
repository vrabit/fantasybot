import discord
from discord import app_commands
from discord.ext import commands

import asyncio

from pathlib import Path
import logging
logger = logging.getLogger(__name__)

class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent

        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color


    ###################################################
    # Manual Slash Commands        
    ###################################################

    @app_commands.command(name='emote', description='Post an emote')
    @app_commands.describe(emote="emote_name")
    async def emote(self, interaction:discord.Interaction, emote:str):
        await interaction.response.defer()

        emoji = discord.utils.get(interaction.guild.emojis, name=emote)
        if emoji:
            await interaction.followup.send(f"{emoji}")
        else:
            await interaction.followup.send("Emoji not found.")


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

        logger.error(f"[Miscellaneous] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[Miscellaneous] - Failed to send error message: {e}")


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
        self._ready = True
        logger.info('[Miscellaneous] - Initialized Miscellaneous')


    ####################################################
    # Handle Load
    ####################################################

    async def cog_load(self):
        logger.info('[Miscellaneous] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[Miscellaneous] - Cog Unload')


async def setup(bot):
    await bot.add_cog(Miscellaneous(bot))