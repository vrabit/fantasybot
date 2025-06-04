import discord
from discord.ext import tasks, commands
from discord import app_commands

from pathlib import Path

import requests
import asyncio
import os

from collections import deque
from difflib import get_close_matches

import matplotlib.pyplot as plt
import numpy as np

from datetime import datetime, timedelta


class TradeValue(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.date = None

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready = False

        # bot embed color
        self.emb_color = self.bot.state.emb_color
        self.discord_grey = '#424549'

        self.player_values_lock = asyncio.Lock()
        self.value_map_lock = asyncio.Lock()
        self.player_values = None
        self.value_map = None

        self.MAX_QUEUE = 5
        self.trades_sends = {}
        self.trades_receives = {}

    def request_values(self, url ="https://api.fantasycalc.com/values/current?isDynasty=false&numQbs=1&numTeams=10&ppr=0.5"):
        response = requests.get(url)
        try:
            player_values = response.json()
        except ValueError:
            print("[TradeValue] - Error: Received invalid response from api.fantasycalc")
        except Exception as e:
            print(f'[TradeValue] - Error: {e}')

        return player_values

    def format_values(self,player_values):
        trade_values_map = {}
        for entry in player_values:
            trade_values_map[entry['player']['name']] = entry

        return trade_values_map

    ###################################################
    # add to trade structures   
    ###################################################

    async def text_sends(self,discord_user:str):
        if discord_user in self.trades_sends:
            output = ''
            sends = self.trades_sends[discord_user]
            while sends:
                name = sends.pop()
                output = output + name + '\n'
            return output
        else:
            return ''
        

    async def text_receives(self,discord_user:str):
        if discord_user in self.trades_receives:
            output = ''
            receives = self.trades_receives[discord_user]
            while receives:
                name = receives.pop()
                output = output + name + '\n'
            return output
        else:
            return ''
        

    async def add_sends(self, player:str, discord_user:str):
        if discord_user in self.trades_sends:
            self.trades_sends[discord_user].append(player)
        else:
            send_deque = deque(maxlen=self.MAX_QUEUE)
            send_deque.append(player)
            self.trades_sends[discord_user] = send_deque


    async def add_receives(self, player:str, discord_user:str):
        if discord_user in self.trades_receives:
            self.trades_receives[discord_user].append(player)
        else:
            send_deque = deque(maxlen=self.MAX_QUEUE)
            send_deque.append(player)
            self.trades_receives[discord_user] = send_deque


    async def clear_trades(self,discord_user:str):
        if discord_user in self.trades_sends:
            self.trades_sends[discord_user] = deque(maxlen = self.MAX_QUEUE)

        if discord_user in self.trades_receives:
            self.trades_receives[discord_user] = deque(maxlen = self.MAX_QUEUE)

    ###################################################
    # create player value graph    
    ###################################################
    def create_parts_array(self, size:int):
        newArr = [size]
        for i in range(len(newArr)):
            newArr[i] = f"{i}"

        return newArr

    async def get_names_values(self, players:deque):
        player_names = deque(maxlen=self.MAX_QUEUE)
        player_values = deque(maxlen=self.MAX_QUEUE)

        while players:
            player_name = players.pop()
            async with self.value_map_lock:
                player_obj = self.value_map[player_name]

            player_names.append(player_obj['player']['name'])
            player_values.append(player_obj['value'])

        return player_names, player_values


    async def create_graph(self, discord_user:str):
        newln = '\n'

        if discord_user in self.trades_sends and discord_user in self.trades_receives:
            # data
            sends = self.trades_sends[discord_user]
            receives = self.trades_receives[discord_user]

            sends_names, sends_values = await self.get_names_values(sends)
            receives_names, receives_values = await self.get_names_values(receives)

            # values list from deque
            sends_values_list= list(sends_values)
            receives_values_list = list(receives_values)

            MAX_VALUE = max(sum(sends_values_list),sum(receives_values_list)) + 2000

            # colors 
            colors = ['lightblue', 'skyblue', 'cornflowerblue', 'steelblue','maroon']

            # Calculate total figure height
            total_height = 3

            # Create the main figure with dynamic height
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, total_height))

            # Plot for "Sends" on ax1
            for i in range(len(sends_values_list)):
                left_value = sum(sends_values_list[:i])
                ax1.barh('Sends', sends_values_list[i], left=np.sum(sends_values_list[:i]), color=colors[i % len(colors)])
                ax1.text(left_value + sends_values_list[i] / 2, 
                         'Sends', 
                         f"{sends_names[i].replace(' ', newln)}{newln}{sends_values_list[i]}", 
                         ha='center', va='center', color='black', fontsize = 12)


            ax1.set_xlabel('', fontsize=12, color='white', labelpad=10, fontweight='bold')
            ax1.set_title('', fontsize=14, color='white', pad=15, fontweight='bold')
            ax1.set_xlim(0, MAX_VALUE)

            # font and border colors
            ax1.tick_params(axis='x', colors='none')
            ax1.tick_params(axis='y', colors='white', labelsize = 16)
            ax1.spines['top'].set_edgecolor((1, 1, 1, 0))  # RGBA format, with 0 being fully transparent
            ax1.spines['bottom'].set_edgecolor((1, 1, 1, 0))  # Fully transparent
            ax1.spines['left'].set_edgecolor((1, 1, 1, 0))  # Fully transparent
            ax1.spines['right'].set_edgecolor((1, 1, 1, 0))  # Fully transparent

            # Plot for "Receives" on ax2
            for i in range(len(receives_values_list)):
                left_value = sum(receives_values_list[:i])
                ax2.barh('Receive', receives_values_list[i], left=np.sum(receives_values_list[:i]), color=colors[i % len(colors)])
                ax2.text(left_value + receives_values_list[i] / 2, 
                         'Receive', 
                         f"{receives_names[i].replace(' ', newln)}{newln}{receives_values_list[i]}", 
                         ha='center', va='center', color='black', fontsize = 12)


            ax2.set_xlabel('', fontsize=12, color='white', labelpad=10, fontweight='bold')
            ax2.set_title('', fontsize=14, color='white', pad=15, fontweight='bold')
            ax2.set_xlim(0, MAX_VALUE)

            # font and border colors
            ax2.tick_params(axis='x', colors='white')
            ax2.tick_params(axis='y', colors='white', labelsize = 16)
            ax2.spines['top'].set_edgecolor((1, 1, 1, 0))  # RGBA format, with 0 being fully transparent
            ax2.spines['bottom'].set_edgecolor('white')  # Fully transparent
            ax2.spines['left'].set_edgecolor((1, 1, 1, 0))  # Fully transparent
            ax2.spines['right'].set_edgecolor((1, 1, 1, 0))  # Fully transparent


            plt.tight_layout()

            # create save folder
            save_folder = Path(self.parent_dir / "images")
            save_folder.mkdir(parents=True, exist_ok=True)

            # save
            current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f'{current_date}_graph.png'
            plt.savefig(save_folder/ filename, format='png', transparent=True)
            plt.close("all")
            return filename, save_folder
        else:
            return None, None



    ###################################################
    # add players to compare    
    ###################################################

    @app_commands.command(name="trade_send",description="Add player to sender side for comparison")
    @app_commands.describe(player="NFL player name")
    async def trade_send(self,interaction:discord.Interaction,player:str):
        await interaction.response.defer(ephemeral=True)

        async with self.value_map_lock:
            closest_key = get_close_matches(player,self.value_map,n=1,cutoff=0.6)
        if len(closest_key) == 0:
            await interaction.followup.send("Failed to match player")
        else:
            await self.add_sends(closest_key[0], str(interaction.user.id))
            message = await interaction.followup.send(f"Added {closest_key[0]} to send")

            await asyncio.sleep(10)
            await message.delete()


    @app_commands.command(name="trade_receive",description="Add player to receive side for comparison")
    @app_commands.describe(player="NFL player name")
    async def trade_receive(self,interaction:discord.Interaction,player:str):
        await interaction.response.defer(ephemeral=True)

        async with self.value_map_lock:
            closest_key = get_close_matches(player,self.value_map,n=1,cutoff=0.6)
        if len(closest_key) == 0:
            await interaction.followup.send("Failed to match player")
        else:
            await self.add_receives(closest_key[0], str(interaction.user.id))
            message = await interaction.followup.send(f"Added {closest_key[0]} to receive")

            await asyncio.sleep(10)
            await message.delete()


    @app_commands.command(name="compare_value",description="Evaluate trade value")
    async def compare_value(self,interaction:discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        filename, save_folder = await self.create_graph(str(interaction.user.id))

        if filename is not None:
            try:
                # attatch new image 
                file_path = save_folder/ filename
                with open(file_path, "rb") as image:
                    file = discord.File(image, filename = filename)

                    embed = discord.Embed(title = "",description = "",color = self.emb_color)
                    embed.set_image(url=f"attachment://{filename}")

                    await interaction.followup.send(embed = embed, file = file)  

                #delete after upload 
                await asyncio.sleep(1)
                os.remove(file_path)

            except Exception as e:
                await interaction.followup.send(f"Error: {e}")
    
        else:
            await interaction.followup.send("Failed")

    @app_commands.command(name="clear_trade",description="Clear your current Trade Proposal")
    async def clear_trade(self,interaction:discord.Interaction):
        await interaction.response.defer()
        await self.clear_trades(str(interaction.user.id))
        await interaction.followup.send("Trade Cleared")      


    ###################################################
    # Update values every 24 hours      
    ###################################################

    @tasks.loop(minutes=1440)
    async def trade_value(self):
        current_date = datetime.today() 
        if self.date is None or self.date != current_date:
            print('[TradeValue] - Updating Trade Values')
            async with self.player_values_lock:
                self.player_values = self.request_values()

                async with self.value_map_lock:
                    self.value_map = self.format_values(self.player_values)
            self.date = current_date
            print('[TradeValue] - Trade Values .. Done')


    ###################################################
    # Loop Error Handling          
    ###################################################

    @trade_value.error
    async def trade_value_error(self,error):
        print(f'[TradeValue][trade_value] - Error: {error}')
        print('[TradeValue][trade_value]: Unable to Setup Trade Value.\n')


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
            print(f"[TradeValue] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            print(f"[TradeValues] - Failed to send error message: {e}")


    ###################################################
    # Setup          
    ###################################################
    
    async def wait_for_fantasy(self):
        while self.bot.state.fantasy_query is None:
            asyncio.sleep(1)
        

    @commands.Cog.listener()
    async def on_ready(self): 
        await self.wait_for_fantasy()
        self.trade_value.start()
        self._ready = True
        print('[TradeValue] - Initialized TradeValue')


    ####################################################
    # Handle Load
    ####################################################

    async def cog_load(self):
        print('[TradeValue] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)

    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        self.trade_value.cancel()
        print('[TradeValue] - Cog Unload')



async def setup(bot):
    await bot.add_cog(TradeValue(bot))