import discord
from discord.ext import tasks, commands
from discord import app_commands, PollLayoutType
from typing import Optional

from pathlib import Path
import asyncio

from collections import deque
from difflib import get_close_matches

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import pandas as pd
from io import BytesIO
import imageio
import matplotlib.gridspec as gridspec

from datetime import datetime, timedelta
import utility

import logging
logger = logging.getLogger(__name__)


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

        self.MAX_QUEUE = 5
        self.trades_sends = {}
        self.trades_receives = {}

        # config
        self._trade_value_config_filename = bot.state.trade_value_config_filename
        self._trade_transactions_filename = bot.state.trade_transactions_filename

        # Log data
        self._roster_csv = bot.state.roster_csv
        self._matchup_csv = bot.state.matchup_csv


    async def request_values(self, url ="https://api.fantasycalc.com/values/current?isDynasty=True&numQbs=1&numTeams=10&ppr=0.5"):
        
        try:
            async with self.bot.state.session_lock:
                async with self.bot.state.session.get(url) as response:
                    player_values = await response.json()
            
        #response = requests.get(url)
        
            #player_values = response.json()
        except ValueError:
            logger.error("[TradeValue] - Error: Received invalid response from api.fantasycalc")
        except Exception as e:
            logger.error(f'[TradeValue] - Error: {e}')
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
    # Trade Value  
    ###################################################

    def create_parts_array(self, size:int):
        newArr = [size]
        for i in range(len(newArr)):
            newArr[i] = f"{i}"

        return newArr


    async def get_names_values(self, players:deque):
        player_names:list = []
        player_values:list = []

        while players:
            player_name = players.popleft()
            async with self.bot.state.value_map_lock:
                player_obj = self.bot.state.value_map[player_name]

            player_names.append(player_obj['player']['name'])
            player_values.append(player_obj['redraftValue'])

        return player_names, player_values


    async def create_trade_value_dataframe(self, discord_user:str):
        sends = self.trades_sends[discord_user]
        receives = self.trades_receives[discord_user]

        sends_names, sends_values = await self.get_names_values(sends)
        receives_names, receives_values = await self.get_names_values(receives)

        all_deques = [sends_names, sends_values, receives_names, receives_values]
        max_len = max( len(entry) for entry in all_deques )

        # Fix uneven length
        padded_sends_names = sends_names + [None] * (max_len - len(sends_names))
        padded_sends_values = sends_values + [None] * (max_len - len(sends_values))
        padded_receives_names = receives_names + [None] * (max_len - len(receives_names))
        padded_receives_values = receives_values + [None] * (max_len - len(receives_values))

        # Define columns and data
        data = {
            'sends_names': padded_sends_names,
            'sends_values': padded_sends_values,
            'receives_names': padded_receives_names,
            'receives_values': padded_receives_values
        }

        # Create DataFrame
        df_values = pd.DataFrame(data)

        # Modify dataframe to long DataFrame
        df_sends_filtered = df_values[df_values['sends_names'].notna()][['sends_names', 'sends_values']].copy()
        df_sends_filtered = df_sends_filtered.rename(columns={'sends_names': 'player', 'sends_values': 'value'})
        df_sends_filtered['type'] = 'sends'

        df_receives_filtered = df_values[df_values['receives_names'].notna()][['receives_names', 'receives_values']].copy()
        df_receives_filtered = df_receives_filtered.rename(columns={'receives_names': 'player', 'receives_values': 'value'})
        df_receives_filtered['type'] = 'receives'

        df_combined_filtered = pd.concat([df_sends_filtered, df_receives_filtered], ignore_index=True)

        df_combined_filtered['cumulative_value'] = df_combined_filtered.groupby(['type'])['value'].cumsum()
        df_combined_filtered = df_combined_filtered.sort_values(by='cumulative_value', ascending=False)

        return df_combined_filtered


    async def create_graph(self, discord_user:str) -> tuple[Optional[str], Optional[str]]:
        if discord_user in self.trades_sends and discord_user in self.trades_receives:
            df_data = await self.create_trade_value_dataframe(discord_user)

            fig = plt.figure(figsize=(12, 8), facecolor="#FDF5E2")
            ax = sns.barplot(
                data=df_data,
                x='cumulative_value',
                y='type',
                hue='player',
                orient='h',
                palette='husl',
                dodge=False,
                ax=fig.gca()
            )
            ax.tick_params(axis='x', labelsize=12)
            ax.tick_params(axis='y', labelsize=12)

            ax.set_xlabel('Value', fontsize=12, color='gray', labelpad=10, fontweight='bold')
            ax.set_title('', fontsize=14, color='gray', pad=15, fontweight='bold')
            ax.set_xlim(0,df_data['cumulative_value'].max() + 5000)
            
            ax.set_facecolor("#E6F2EB")
            plt.title('Trade Value')
            plt.xlabel('Total Trade Value')
            plt.ylabel('')
            plt.tight_layout()

            # add labels to bars
            series_max_values = df_data.groupby(['type'])['cumulative_value'].max()        
            if series_max_values['sends'] > series_max_values['receives']:
                receives_pos = 1
            else:
                receives_pos = 0

            for _, row in enumerate(df_data.itertuples()):
            
                if row.value < 1000:
                    continue

                label = f'Total\n{row.cumulative_value:.0f}\n\n{row.player.split(' ')[-1]}\n{row.value:.0f}'
                text_x_pos = row.cumulative_value - 1 if row.cumulative_value > 0 else 0.5
                
                if row.type == 'receives':
                    pos = receives_pos
                else:
                    pos = 0 if receives_pos == 1 else 1

                ax.text(
                    text_x_pos,
                    pos,
                    label,
                    va='center',
                    ha='right',
                    fontsize=14,
                    color= 'white',
                    weight='bold'
                )

            plt.legend(
                title='Player', 
                fontsize=10,
                title_fontsize=12,
                loc='lower right'
            )

            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0) # reset to start
            return buf

        else:
            return None


    ###################################################################################
    # Player Value Radial Graph
    ###################################################################################

    async def cleanup_radar_data(self, df):
        # Create working copy
        df_cleaned = df.copy()

        # Clean up the data
        df_cleaned['week'] = pd.to_numeric(df_cleaned['week'], errors='coerce').fillna(-1).astype(int)
        df_cleaned['owner_id'] = pd.to_numeric(df_cleaned['owner_id'], errors='coerce').fillna(-1).astype(int)
        df_cleaned['redraft_value'] = pd.to_numeric(df_cleaned['redraft_value'], errors='coerce').fillna(0).astype(int)

        # Create player_lists
        # Filter out 'DEF' position - this df_cleaned_no_def will be used for player lists
        df_cleaned_no_def = df_cleaned[df_cleaned['primary_position'] != 'DEF'].copy()

        return df_cleaned_no_def


    async def create_radar_DataFrame(self, df_cleaned_no_def):
        # Prepare Right Side (Data)
        df_agg:pd.DataFrame = df_cleaned_no_def.groupby(['owner_id', 'week', 'primary_position'])['redraft_value'].sum().reset_index()

        # Get all unique owners, weeks, and positions for normalization/completeness
        all_owner_ids:list = sorted(df_agg['owner_id'].unique())
        all_weeks:list = sorted(df_agg['week'].unique())
        all_positions:list = ['QB', 'RB', 'WR', 'TE', 'K'] # Define Primary positions in specific order

        # Prepare Left Side (Index)
        full_index = pd.MultiIndex.from_product(
            [all_owner_ids, all_weeks, all_positions],
            names=['owner_id', 'week', 'primary_position']
        )
        df_full_comb = pd.DataFrame(index=full_index).reset_index()

        # Merge Left and Right and make sure data is int
        df_plot_ready = pd.merge(
            df_full_comb,
            df_agg,
            on=['owner_id', 'week', 'primary_position'],
            how='left'
        ).fillna({'redraft_value': 0})
        df_plot_ready['redraft_value'] = df_plot_ready['redraft_value'].astype(int)

        return df_plot_ready, all_owner_ids, all_weeks, all_positions


    async def radar_DataFrame(self,df):
        # Normalize redraft_value (0 to 1) for radar chart scaling
        def normalize_value(row):
            pos = row['primary_position']
            value = row['redraft_value']
            pos_min = min_max_dict[pos]['min']
            pos_max = min_max_dict[pos]['max']
            if pos_max == pos_min:
                return 0.0 if value == 0 else 1.0 # Avoid division by zero, 0 for 0, 1 for non-zero if all values same
            else:
                return (value - pos_min) / (pos_max - pos_min)

        # Create Cleaned DataFrames
        df_cleaned_no_def:pd.DataFrame = await self.cleanup_radar_data(df)

        # Create radar DataFrame
        df_plot_ready, all_owner_ids, all_weeks, all_positions = await self.create_radar_DataFrame(df_cleaned_no_def)

        # Add owner names to the plot-ready dataframe ( if data is not clean, final name is selected )
        owner_id_to_name:dict = df_cleaned_no_def[['owner_id', 'owner_name']].drop_duplicates().set_index('owner_id')['owner_name'].to_dict()
        df_plot_ready['owner_name'] = df_plot_ready['owner_id'].map(owner_id_to_name)

        # Calculate min/max redraft_value per position for normalization / add 'normalized_value' series to the plot DataFrame
        min_max_per_position = df_plot_ready.groupby('primary_position')['redraft_value'].agg(['min', 'max']).reset_index()
        min_max_dict = min_max_per_position.set_index('primary_position').to_dict('index')
        df_plot_ready['normalized_value'] = df_plot_ready.apply(normalize_value, axis=1)

        return df_plot_ready, df_cleaned_no_def, all_weeks, all_positions
    

    async def filtered_DataFrame(self, df_plot_ready, selected_owner_ids=None) -> tuple[pd.DataFrame, list]:
        if selected_owner_ids and len(selected_owner_ids) <= 2:
            logger.info(f"Generating charts for selected owners: {selected_owner_ids}")
            df_plot_ready_filtered:pd.DataFrame = df_plot_ready[df_plot_ready['owner_id'].isin(selected_owner_ids)].copy()
        else:
            logger.info("Generating charts for all owners (player lists will not be generated).")
            df_plot_ready_filtered:pd.DataFrame = df_plot_ready.copy()
            # If not 2 owners, clear selected_owner_ids to prevent player list generation
            selected_owner_ids = [] # If more than 2 provided, prevent player list generation

        owners_to_plot_in_this_session:list = sorted(df_plot_ready_filtered['owner_id'].unique())

        return df_plot_ready_filtered, owners_to_plot_in_this_session


    async def generate_season_radar_chart(self, df_plot_ready:pd.DataFrame, df_cleaned_no_def, all_weeks, all_positions, selected_owner_ids=None) -> list[BytesIO]:
        df_plot_ready_filtered, owners_to_plot_in_this_session = await self.filtered_DataFrame(df_plot_ready, selected_owner_ids)

        # Hold all buffers in a list to later convert to GIF
        image_buffer_list = []

        logger.info("\nStarting radar chart generation...")
        for week in all_weeks:
            data_for_week_radar:pd.Series = df_plot_ready_filtered[df_plot_ready_filtered['week'] == week].copy()
            # Filter df_cleaned_full for the current week for individual player data
            df_cleaned_for_week:pd.Series = df_cleaned_no_def[df_cleaned_no_def['week'] == week].copy()
            if not data_for_week_radar.empty:
                logger.info(f"Generating {week} buffer.")
                buf = await self.draw_radar_chart_frames(data_for_week_radar, df_cleaned_for_week, week, all_positions, owners_to_plot_in_this_session)
                image_buffer_list.append(buf)
            else:
                logger.info(f"No data for Week {week} for selected owners. Skipping chart generation.")
        return image_buffer_list


    async def generate_radar_chart(self, df_plot_ready:pd.DataFrame, df_cleaned_no_def, current_week, all_positions, selected_owner_ids=None) -> list[BytesIO]:
        df_plot_ready_filtered, owners_to_plot_in_this_session = await self.filtered_DataFrame(df_plot_ready, selected_owner_ids)


        logger.info("\nStarting radar chart generation...")

        data_for_week_radar:pd.Series = df_plot_ready_filtered[df_plot_ready_filtered['week'] == current_week].copy()
        # Filter df_cleaned_full for the current week for individual player data
        df_cleaned_for_week:pd.Series = df_cleaned_no_def[df_cleaned_no_def['week'] == current_week].copy()
        if not data_for_week_radar.empty:
            logger.info(f"Generating {current_week} buffer.")
            buf = await self.draw_radar_chart_frames(data_for_week_radar, df_cleaned_for_week, current_week, all_positions, owners_to_plot_in_this_session)
            return buf
        else:
            logger.info(f"No data for Week {current_week} for selected owners. Skipping chart generation.")
            return None


    async def get_player_list_text(self, owner_id:int, df_players_for_week:pd.DataFrame, owner_name_map:map):
        owner_name = owner_name_map.get(owner_id, f"Owner {owner_id}")
        players_data = df_players_for_week[
            (df_players_for_week['owner_id'] == owner_id)
        ].sort_values(by=['primary_position', 'redraft_value'], ascending=[True, False])

        text_output = f"--- {owner_name} Players ---\n"
        current_pos = ""
        for _, row in players_data.iterrows():
            if row['primary_position'] != current_pos:
                text_output += f"\n{row['primary_position']}:\n"
                current_pos = row['primary_position']
            text_output += f"- {row['name']} ({row['redraft_value']})\n"
        return text_output


    async def bind_colors_to_teams(self,owner_ids:list) -> dict[int, tuple[float,float,float]]:
        num_owners = len(owner_ids)
        owner_colors:list[tuple[float,float,float]] = sns.color_palette("Set2", num_owners)
        owner_color_map:dict[int, tuple[float,float,float]] = {owner: owner_colors[i] for i, owner in enumerate(owner_ids)}
        return owner_color_map


    async def draw_radar_chart_frames(self, data_for_week_radar:pd.Series, df_cleaned_for_week:pd.DataFrame, week:int, all_positions:list, owners_to_plot_in_this_chart:list):
        # Generate Color_map
        owner_ids_list = sorted(data_for_week_radar['owner_id'].unique())
        owner_color_map = await self.bind_colors_to_teams(owner_ids_list)

        # Set radar axis lines
        num_positions = len(all_positions)
        angles = np.linspace(0, 2 * np.pi, num_positions, endpoint=False).tolist()
        angles_plot = angles + [angles[0]]

        # Define Grid 
        gs = gridspec.GridSpec(1, 3, width_ratios=[0.6, 0.2, 0.2], wspace=0.1)

        # Create Figure
        fig = plt.figure(figsize=(14, 8), facecolor="#F0F0F0")

        # Define Subplot-1, Radar Graph
        ax_radar = fig.add_subplot(gs[0, 0], projection='polar')
        ax_radar.set_facecolor("#DDEEEE")
        ax_radar.set_theta_offset(np.pi / 2)    # Plot Starting at the top
        ax_radar.set_theta_direction(-1)        # Clockwise
        ax_radar.set_yticks(np.linspace(0, 1, 5))
        ax_radar.set_yticklabels(['0', '0.25', '0.5', '0.75', '1.0'], color="gray", size=8)
        ax_radar.set_ylim(0, 1)
        ax_radar.set_xticks(angles)
        ax_radar.set_xticklabels(all_positions, fontsize=10, weight='bold', color='dimgray')
        ax_radar.plot(angles_plot, [0] * len(angles_plot), 'k-', linewidth=0.5, zorder=1) # angle, value, solid black, width, layer

        lines = []
        owner_id_to_name:dict = df_cleaned_for_week[['owner_id', 'owner_name']].drop_duplicates().set_index('owner_id')['owner_name'].to_dict()
        for owner_id in owners_to_plot_in_this_chart:
            owner_name = owner_id_to_name.get(owner_id, f"Owner {owner_id}")
            owner_data = data_for_week_radar[data_for_week_radar['owner_id'] == owner_id].copy()

            if owner_data.empty:
                logger.info(f"Warning: Owner {owner_id} has no data for Week {week} after filtering for radar plot. Skipping.")
                continue

            owner_data['angle'] = owner_data['primary_position'].map({pos: angles[i] for i, pos in enumerate(all_positions)})
            owner_data = owner_data.sort_values(by='angle')

            values = owner_data['normalized_value'].tolist()
            values_plot = values + [values[0]]

            color = owner_color_map.get(owner_id, 'gray')

            line, = ax_radar.plot(angles_plot, values_plot, color=color, linewidth=2, linestyle='solid', label=owner_name, zorder=3)
            lines.append(line)
            ax_radar.fill(angles_plot, values_plot, color=color, alpha=0.25, zorder=2)

        ax_radar.set_title(f"Positional Strength - Week {week}\n(Normalized Values)", va='bottom', fontsize=14, weight='bold')
        ax_radar.legend(loc='lower left', bbox_to_anchor=(1.05, 0.0), borderaxespad=0., fontsize=9, title="Teams")

        ax_player_1 = fig.add_subplot(gs[0, 1])
        ax_player_2 = fig.add_subplot(gs[0, 2])

        for a in [ax_player_1, ax_player_2]:
            a.axis('off')
            a.set_xlim(0, 1)
            a.set_ylim(0, 1)

        if len(owners_to_plot_in_this_chart) == 2:
            owner1_id = owners_to_plot_in_this_chart[0]
            owner2_id = owners_to_plot_in_this_chart[1]

            text_owner1 = await self.get_player_list_text(owner1_id, df_cleaned_for_week, owner_id_to_name)
            text_owner2 = await self.get_player_list_text(owner2_id, df_cleaned_for_week, owner_id_to_name)

            # Increased fontsize from 8 to 9
            ax_player_1.text(0.05, 0.95, text_owner1, transform=ax_player_1.transAxes, va='top', ha='left', fontsize=9, wrap=True) 
            ax_player_2.text(0.05, 0.95, text_owner2, transform=ax_player_2.transAxes, va='top', ha='left', fontsize=9, wrap=True) 

        elif len(owners_to_plot_in_this_chart) == 1:
            owner1_id = owners_to_plot_in_this_chart[0]

            text_owner1 = await self.get_player_list_text(owner1_id, df_cleaned_for_week, owner_id_to_name)

            # Increased fontsize from 8 to 9
            ax_player_1.text(0.05, 0.95, text_owner1, transform=ax_player_1.transAxes, va='top', ha='left', fontsize=9, wrap=True) 

        else:
            ax_player_1.text(0.5, 0.5, "Select at most 2 teams\nto display player lists.",
                            transform=ax_player_1.transAxes, va='center', ha='center', fontsize=9, color='gray')
            ax_player_2.text(0.5, 0.5, "Select at most 2 teams\nto display player lists.",
                            transform=ax_player_2.transAxes, va='center', ha='center', fontsize=9, color='gray')


        # Return Buffer of file
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0) # reset to start
        return buf
    

    ###################################################
    # add players to compare    
    ###################################################

    async def refine_transaction_df(self, transaction_id:int):
        df_raw = await self.bot.state.persistent_manager.load_csv_formatted(filename=self._trade_transactions_filename)
        df = df_raw.copy()

        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(-1).astype(int)
        df['value'] = pd.to_numeric(df['value'], errors='coerce').fillna(-1).astype(int)
        
        exists = (df['id'] == transaction_id).any()
        if not exists:
            return None

        df = df[df['id'] == transaction_id]
        df['cumulative_value'] =  df.groupby(['source_team_key'])['value'].cumsum()
        df = df.sort_values(by='cumulative_value', ascending=False).reset_index(drop=True)

        team_names:list =df['source_team'].unique()

        return df, team_names[0], team_names[1]


    async def create_transaction_graph(self, transaction_id:int) -> tuple[Optional[str], Optional[str]]:
        df_data, team_1_name, team_2_name = await self.refine_transaction_df(transaction_id)
        if df_data is None:
            return None
        
        fig = plt.figure(figsize=(12, 8), facecolor="#FDF5E2")
        ax = sns.barplot(
            data=df_data,
            x='cumulative_value',
            y='source_team',
            hue='name',
            orient='h',
            palette='husl',
            dodge=False,
            ax=fig.gca()
        )
        ax.tick_params(axis='x', labelsize=12)
        ax.tick_params(axis='y', labelsize=12)

        ax.set_xlabel('Value', fontsize=12, color='gray', labelpad=10, fontweight='bold')
        ax.set_title('', fontsize=14, color='gray', pad=15, fontweight='bold')
        ax.set_xlim(0,df_data['cumulative_value'].max() + 2000)
        
        ax.set_facecolor("#E6F2EB")
        plt.title('Trade Value')
        plt.xlabel('Total Trade Value')
        plt.ylabel('')
        plt.tight_layout()

        # add labels to bars
        max_team_key = df_data['source_team_key'].iloc[0]

        

        for _, row in enumerate(df_data.itertuples()):
        
            if row.value < 1000:
                continue

            label = f'Total\n{row.cumulative_value:.0f}\n\n{row.name.split(' ')[-1]}\n{row.value:.0f}'
            text_x_pos = row.cumulative_value - 1 if row.cumulative_value > 0 else 0.5
            
            if row.source_team_key == max_team_key:
                pos = 0
            else:
                pos = 1

            ax.text(
                text_x_pos,
                pos,
                label,
                va='center',
                ha='right',
                fontsize=14,
                color= 'white',
                weight='bold'
            )

        plt.legend(
            title='Player', 
            fontsize=10,
            title_fontsize=12,
            loc='lower right'
        )
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0) # reset to start
        return buf, team_1_name, team_2_name


    ###################################################
    # add players to compare    
    ###################################################

    async def create_poll(self, question:str, answers:list, hours:int = 8, layout:int = 1, multiple=False):
        if layout != 1 and layout != 3:
            layout = 1

        EMOJI = {
            1:'1️⃣',
            2:'2️⃣',
            3:'3️⃣',
            4:'4️⃣'
        }

        duration = timedelta(hours=hours)
        poll_layout = PollLayoutType(layout)

        poll = discord.Poll(question=question, duration=duration, layout_type=poll_layout, multiple=multiple)

        for i, answer in enumerate(answers):
            poll.add_answer(text=answer, emoji = EMOJI.get(i+1))

        return poll


    @app_commands.command(name="evaluate_transaction",description="Evaluate trade value")
    @app_commands.describe(transaction_id="Transaction ID number")
    async def evaluate_transaction(self,interaction:discord.Interaction, transaction_id: int):
        await interaction.response.defer(ephemeral=False)

        try:
            buf, team_1_name, team_2_name = await self.create_transaction_graph(transaction_id)
        except Exception as e:
            await interaction.followup.send('Error: Failed to create graph.')
            logger.error(f'[TradeValue][trade_evaluate] - Error: {e}')
            return
        
        if buf:
            filename = 'trade_value.png'
            file = discord.File(fp=buf, filename=filename)
            embed = discord.Embed(title = "",description = "",color = self.emb_color)
            embed.set_image(url=f"attachment://{filename}")

            await interaction.followup.send(embed=embed, file=file)  
            poll = await self.create_poll("Who Won?", [team_1_name,team_2_name], layout=1)
            await interaction.followup.send(poll=poll)  
        else:
            await interaction.followup.send("Failed")


    @app_commands.command(name="trade_send",description="Add player to sender side for comparison")
    @app_commands.describe(player="NFL player name")
    async def trade_send(self,interaction:discord.Interaction,player:str):
        await interaction.response.defer(ephemeral=True)

        async with self.bot.state.value_map_lock:
            closest_key = get_close_matches(player,self.bot.state.value_map,n=1,cutoff=0.6)
        if len(closest_key) == 0:
            await interaction.followup.send("Failed to match player.")
        else:
            await self.add_sends(closest_key[0], str(interaction.user.id))
            message = await interaction.followup.send(f"Added {closest_key[0]} to send")

            await asyncio.sleep(10)
            await message.delete()


    @app_commands.command(name="trade_receive",description="Add player to receive side for comparison")
    @app_commands.describe(player="NFL player name")
    async def trade_receive(self,interaction:discord.Interaction, player:str):
        await interaction.response.defer(ephemeral=True)

        async with self.bot.state.value_map_lock:
            closest_key = get_close_matches(player,self.bot.state.value_map,n=1,cutoff=0.6)
        if len(closest_key) == 0:
            await interaction.followup.send("Failed to match player.")
        else:
            await self.add_receives(closest_key[0], str(interaction.user.id))
            message = await interaction.followup.send(f"Added {closest_key[0]} to receive")

            await asyncio.sleep(10)
            await message.delete()


    @app_commands.command(name="trade_evaluate",description="Evaluate trade value")
    async def trade_evaluate(self,interaction:discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        try:
            buf = await self.create_graph(str(interaction.user.id))
        except Exception as e:
            await interaction.followup.send('Error: Failed to create graph.')
            logger.error(f'[TradeValue][trade_evaluate] - Error: {e}')
            return
        
        if buf:
            filename = 'trade_value.png'
            file = discord.File(fp=buf, filename=filename)
            embed = discord.Embed(title = "",description = "",color = self.emb_color)
            embed.set_image(url=f"attachment://{filename}")

            await interaction.followup.send(embed = embed, file = file)  
        else:
            await interaction.followup.send("Failed")


    @app_commands.command(name="trade_clear",description="Clear your current Trade Proposal")
    async def trade_clear(self,interaction:discord.Interaction):
        await interaction.response.defer()
        await self.clear_trades(str(interaction.user.id))
        await interaction.followup.send("Trade Cleared")      


    async def convert_buffers_list_to_gif_buffer(self,buffers:list[BytesIO], fps=0.5) -> BytesIO:
        frames = []
        for buf in buffers:
            frames.append(imageio.v3.imread(buf))

        gif_buffer = BytesIO()
        imageio.v3.imwrite(gif_buffer, frames, format='GIF', fps=fps, loop=0)
        gif_buffer.seek(0)
        return gif_buffer


    @app_commands.command(name='season_team_value_comparison', description='Create a Radial Plot GIF depicting player trade value by position for the season.')
    @app_commands.describe(discord_user="Discord Tag")
    async def season_team_value_comparison(self, interaction:discord.Interaction, discord_user:discord.User):
        await interaction.response.defer()
        user_team_id:str = await utility.discord_to_teamid(interaction.user.id, self.bot.state.persistent_manager)
        opponent_team_id:str = await utility.discord_to_teamid(discord_user.id, self.bot.state.persistent_manager)

        if not user_team_id or not opponent_team_id:
            await interaction.followup.send('Unable to find valid user IDs.')
            return

        df_roster = await self.bot.state.recap_manager.load_csv_formatted(self._roster_csv)

        df_plot_ready, df_cleaned_full, all_weeks, all_positions = await self.radar_DataFrame(df_roster)
        buffer_list = await self.generate_season_radar_chart(df_plot_ready, df_cleaned_full, all_weeks, all_positions, [int(user_team_id), int(opponent_team_id)])
        if buffer_list:
            filename = 'radial_comparison.gif'
            gif_buffer = await self.convert_buffers_list_to_gif_buffer(buffer_list)
            file = discord.File(gif_buffer, filename=filename)
            embed = discord.Embed(title = "", description = "", color = self.emb_color)
            embed.set_image(url=f'attachment://{filename}')

            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send('Failed to generate gif')


    @app_commands.command(name='team_value_comparison', description='Create a Radial Plot image depicting player trade value by position for the current week.')
    @app_commands.describe(discord_user="Discord Tag")
    async def team_value_comparison(self, interaction:discord.Interaction, discord_user:discord.User):
        await interaction.response.defer()
        user_team_id:str = await utility.discord_to_teamid(interaction.user.id, self.bot.state.persistent_manager)
        opponent_team_id:str = await utility.discord_to_teamid(discord_user.id, self.bot.state.persistent_manager)

        if not user_team_id or not opponent_team_id:
            await interaction.followup.send('Unable to find valid user IDs.')
            return

        async with self.bot.state.league_lock:
            league = self.bot.state.league
        current_week = league.current_week

        df_roster = await self.bot.state.recap_manager.load_csv_formatted(self._roster_csv)

        df_plot_ready, df_cleaned_full, _, all_positions = await self.radar_DataFrame(df_roster)
        buffer = await self.generate_radar_chart(df_plot_ready, df_cleaned_full, current_week, all_positions, [int(user_team_id), int(opponent_team_id)])
        if buffer:
            filename = f'{user_team_id}-{opponent_team_id}_comparicon.png'
            file = discord.File(buffer, filename=filename)
            embed = discord.Embed(title = "", description = "", color = self.emb_color)
            embed.set_image(url=f'attachment://{filename}')

            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send('Failed to generate gif')


    ###################################################
    # Update values every 24 hours      
    ###################################################

    @tasks.loop(minutes=1440)
    async def trade_value(self):
        current_date = datetime.today() 
        if self.date is None or self.date != current_date:
            logger.info('[TradeValue] - Updating Trade Values')
            async with self.bot.state.player_values_lock:
                self.bot.state.player_values = await self.request_values(url=self.bot.state.trade_value_url)

                async with self.bot.state.value_map_lock:
                    self.bot.state.value_map = self.format_values(self.bot.state.player_values)
            self.date = current_date
            self.bot.state.trade_value_ready = True
            logger.info('[TradeValue] - Trade Values .. Done')


    ###################################################
    # Loop Error Handling          
    ###################################################

    @trade_value.error
    async def trade_value_error(self,error):
        logger.error(f'[TradeValue][trade_value] - Error: {error}\n [TradeValue][trade_value]: Unable to Setup Trade Value.')


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
        logger.error(f"[TradeValue] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[TradeValues] - Failed to send error message: {e}")


    ###################################################
    # Setup          
    ###################################################
    
    async def generate_url(self):
        config = await self.bot.state.settings_manager.load_json(filename=self._trade_value_config_filename)

        if not config:
            self.bot.state.trade_value_url="https://api.fantasycalc.com/values/current?isDynasty=True&numQbs=1&numTeams=10&ppr=0.5"
        else:
            self.bot.state.trade_value_url = f"https://api.fantasycalc.com/values/current?isDynasty={config.get('Dynasty')}&numQbs={config.get('numQbs')}&numTeams={config.get('numTeams')}&ppr={config.get('ppr')}"


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
        await self.generate_url()
        await self.wait_for_fantasy()
        self.trade_value.start()
        logger.info('[TradeValue] - Initialized TradeValue')


    ####################################################
    # Handle Load
    ####################################################

    async def cog_load(self):
        logger.info('[TradeValue] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        self.trade_value.cancel()
        logger.info('[TradeValue] - Cog Unload')


async def setup(bot):
    await bot.add_cog(TradeValue(bot))