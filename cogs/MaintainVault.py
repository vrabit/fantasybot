import discord
from discord import app_commands
from discord.ext import tasks,commands
from typing import Any

import os
import asyncio

from pathlib import Path
from bet_vault.vault import Vault
from datetime import datetime, timedelta, date

from yfpy.models import Matchup

from cogs_helpers import FantasyHelper
from collections import deque
import utility

import logging
logger = logging.getLogger(__name__)


class MaintainVault(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.bot_name = bot.user.name

        self.current_dir = Path(__file__).parent
        self.parent_dir = self.current_dir.parent
        self._ready_to_init = False
        self._ready = False
        
        # winner / loser 
        self.gold_color:discord.Color = discord.Color.gold()
        self.pink_color:discord.Color = discord.Color.pink()
        self.loser_role_name:str = None
        self.denier_role_name:str = None
        self.challenger_wins_link = None
        self.challengee_wins_link = None
        self.wager_winner_link = None
        self.tie_link = None

        # bot embed color
        self.emb_color = self.bot.state.emb_color

        # file managers
        self._persistent_manager = self.bot.state.persistent_manager
        self._vault_manager = self.bot.state.vault_manager
        self._discord_auth_manager = self.bot.state.discord_auth_manager

        # vault 
        self._vault:Vault = None
        self._initial_bank_funds:int = None
        self._weekly_bank_funds:int = None
        self._default_wager_amount:int = None
        self._default_wager_bonus:int = None

        # files
        self._members_filename = bot.state.members_filename
        self._funds_distribution_log = bot.state.weekly_funds_filename
        self._week_dates_filename = bot.state.week_dates_filename
        self._vault_accounts_filename = bot.state.vault_accounts_filename
        self._vault_slap_contracts_filename = bot.state.vault_slap_contracts_filename
        self._vault_wager_contracts_filename = bot.state.vault_wager_contracts_filename
        self._challenge_filename = bot.state.challenge_config_filename
        


    ###################################################
    # Assign Role 
    ###################################################

    async def get_slaps_channel(self):
        async with self.bot.state.slaps_channel_id_lock:
            local_id = self.bot.state.slaps_channel_id

        if local_id is None:
            logger.warning('[SlapChallenge] - Channel not set.')
            return None
       
        # get channel for message and guild.roles
        channel = self.bot.get_channel(int(local_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(local_id))
            except Exception as e:
                logger.error(f'[FantasyQuery][get_slaps_channel] - Error: {e}')
                return None
        return channel


    async def assign_role(self, discord_member_id:int, role_name:str, color:discord.Color):
        channel = await self.get_slaps_channel()
        if channel is None:
            logger.warning('[MaintainVault][assign_role] - Unable to retrive Slaps Channel.')
            return

        await FantasyHelper.assign_role_by_channel(channel=channel, discord_member_id=discord_member_id, role_name=role_name, role_color=color)
       

    ###################################################
    # Format matchup dict
    ###################################################

    async def format_matchups_to_dict(self, matchups_list:list[Matchup]):
        data_dict = {}
        try:
            for matchup in matchups_list:
                if len(matchup.teams) > 1:
                    entry_1 = {}
                    team_1_id = str(matchup.teams[0].team_id)
                    entry_1['team_id'] =  team_1_id
                    entry_1['team_opponent_id'] = str(matchup.teams[1].team_id)
                    entry_1['total_points'] = round(matchup.teams[0].team_points.total, 2)
                    entry_1['week_start'] = matchup.week_start
                    entry_1['week_end'] = matchup.week_end
                    entry_1['winner'] = matchup.winner_team_key
                    entry_1['week'] = matchup.week
                    data_dict[team_1_id] = entry_1

                    entry_2 = {}
                    team_2_id = str(matchup.teams[1].team_id)
                    entry_2['team_id'] = team_2_id
                    entry_2['team_opponent_id'] = str(matchup.teams[0].team_id)
                    entry_2['total_points'] = round(matchup.teams[1].team_points.total, 2)
                    entry_2['week_start'] = matchup.week_start
                    entry_2['week_end'] = matchup.week_end
                    entry_2['winner'] = matchup.winner_team_key
                    entry_2['week'] = matchup.week
                    data_dict[team_2_id] = entry_2
                else:
                    entry = {}
                    team_1_id = str(matchup.teams[0].team_id)
                    entry['team_id'] =  team_1_id
                    entry['team_opponent_id'] = None
                    entry['total_points'] = round(matchup.teams[0].team_points, 2)
                    entry['week_start'] = matchup.week_start
                    entry['week_end'] = matchup.week_end
                    entry['winner'] = matchup.winner_team_key
                    entry['week'] = matchup.week
                    data_dict[team_1_id] = entry

            return data_dict
        except Exception as e:
            raise ValueError(f"Failed to construct data from Matchup_list. \n Error: {e}")


    async def get_matchup_data(self, week) -> dict[str:int]:
        async with self.bot.state.fantasy_query_lock:
            matchups_list:list[Matchup] = self.bot.state.fantasy_query.get_scoreboard(week).matchups
        
        if matchups_list is None:
            raise ValueError('match_ups list is None.')
        return await self.format_matchups_to_dict(matchups_list)


    ###################################################
    # Display Challenge Results
    ###################################################

    async def send_embed(self, embed:discord.Embed):
        channel:discord.TextChannel = await self.get_slaps_channel()
        await channel.send(embed = embed)


    async def display_wager_results(self, contract:Vault.GroupWagerContract, team_1_pts:float, team_2_pts:float, total_points:float, closest_prediction:Vault.GroupWagerContract.Prediction, winners_list:list[Vault.GroupWagerContract.Prediction]):
        team_1_discord = await utility.teamid_to_discord(team_id=contract.team_1_id, file_manager=self._persistent_manager)
        team_2_discord = await utility.teamid_to_discord(team_id=contract.team_2_id, file_manager=self._persistent_manager)

        team_1_name = await utility.discord_to_name(discord_id=team_1_discord, file_manager=self._persistent_manager)
        team_2_name = await utility.discord_to_name(discord_id=team_2_discord, file_manager=self._persistent_manager)
        title = f"{team_1_name} VS {team_2_name}"
        if len(title) >= 40:
            title = f"{team_1_name.split(" ")[-1]} VS {team_2_name.split(" ")[-1]}"

        embed = discord.Embed(
            title=title, 
            description=(
                f"{closest_prediction.gambler.discord_tag} wins {contract.winnings} tokens.\n"
                f"Total Points: {total_points}"
            ),
            color=self.emb_color,
            timestamp=contract.expiration
        )
        embed.add_field(name="Points:", value=f"{team_1_pts}",inline=True) 
        embed.add_field(name = '\u200b', value = '\u200b', inline=True)
        embed.add_field(name="Points:", value=f"{team_2_pts}",inline=True)
        message = ""
        for prediction in winners_list:
            if prediction.gambler == closest_prediction.gambler:
                message += f"{prediction.gambler.name} - {prediction.gambler.discord_tag}\nPrediction: {prediction.prediction_points} pts. 🏆\n\n"
            else:
                message += f"{prediction.gambler.name} - {prediction.gambler.discord_tag}\nPrediction: {prediction.prediction_points} pts. \n\n"
        embed.add_field(name = '\u200b', value = message, inline = False)
        embed.set_image(url=self.wager_winner_link)
        embed.set_footer(text="Group Wager")
        await self.send_embed(embed=embed)


    async def display_slap_results(self, contract:Vault.SlapContract, winner_fantasy_id:str, challenger_points:float, challengee_points:float):
        if contract.challenger == winner_fantasy_id:
            description = f"{contract.challenger.discord_tag} 🏆 defeats {contract.challengee.discord_tag}\nWinner takes {contract.winnings} tokens."
            image = self.challenger_wins_link
        else:
            description = f"{contract.challenger.discord_tag} defeated by {contract.challengee.discord_tag} 🏆\nWinner takes {contract.winnings} tokens."
            image = self.challengee_wins_link

        challenger_team_name = await utility.discord_to_name(discord_id=contract.challenger.discord_id, file_manager=self._persistent_manager)
        challengee_team_name = await utility.discord_to_name(discord_id=contract.challengee.discord_id, file_manager=self._persistent_manager)

        title = f"{challenger_team_name} VS {challengee_team_name}"
        if len(title) >= 40:
            title = f"{challenger_team_name.split(" ")[-1]} VS {challengee_team_name.split(" ")[-1]}"

        embed = discord.Embed(title = title, description = description, color=self.emb_color, timestamp=contract.expiration)
        embed.add_field(name = f"{challenger_team_name}\nPoints: {challenger_points}", value="", inline=True)
        embed.add_field(name = f"{challengee_team_name}\nPoints: {challengee_points}", value="", inline=True)
        embed.set_image(url=image)
        embed.set_footer(text="Slap Challenge")
        await self.send_embed(embed=embed)


    ###################################################
    # Execute Contracts 
    ###################################################

    async def execute_wager(self, contract:Vault.GroupWagerContract, week_dict:dict[str:Any]):
        if await contract.empty():
            logger.info('[MaintainVault] - No Predictions to account to parse.')
            contract.executed = True
            return
        logger.info('[MaintainVault][execute_wager] - Evaluating Wager Winner.')

        # data
        matchup_1_dict = week_dict.get(contract.team_1_id)
        matchup_2_dict = week_dict.get(contract.team_2_id)

        # points
        team_1_total_points = matchup_1_dict.get('total_points')
        team_2_total_points = matchup_2_dict.get('total_points')
        total_points = team_1_total_points + team_2_total_points

        if len(contract.predictions) <= 1:
            await contract.refund()
            logger.info("[MaintainVault][execute_wager] - Refunding prediction.")
            return

        # winner
        if team_1_total_points > team_2_total_points:
            winner_id = contract.team_1_id
        elif team_1_total_points < team_2_total_points:
            winner_id = contract.team_2_id
        else:
            logger.info(f'[MaintainVault][execute_wager] - Tie: Refunding {contract.team_1_id}-{contract.team_2_id} matchup.')
            await contract.refund()
            return

        winner_list = [prediction for prediction in contract.predictions if prediction.prediction_team == winner_id]
        if winner_list:
            closest_prediction:Vault.GroupWagerContract.Prediction = min(winner_list, key=lambda p: abs(p.prediction_points - total_points))
            logger.info(f'[MaintainVault][execute_wager] - Team {closest_prediction.gambler.discord_tag} wins {contract.winnings} tokens.')
            await contract.execute_contract(winner=closest_prediction.gambler)
            await self.display_wager_results(contract=contract, team_1_pts=team_1_total_points, team_2_pts=team_2_total_points, total_points=total_points,closest_prediction=closest_prediction, winners_list=winner_list)
        else:
            logger.info('[MaintainVault][eecute_wager] - Winners list is empty')
            await contract.refund()


    async def execute_slap(self, contract:Vault.SlapContract, week_dict:dict[str:Any]):
        challenger_id = str(contract.challenger.fantasy_id)
        challengee_id = str(contract.challengee.fantasy_id)

        challenger_dict = week_dict.get(challenger_id)
        challengee_dict = week_dict.get(challengee_id)

        if challenger_dict.get('total_points') > challengee_dict.get('total_points'):
            await contract.execute_contract(contract.challenger)
            await self.assign_role(int(contract.challengee.discord_id), self.loser_role_name, self.gold_color)
            await self.display_slap_results(contract, challenger_id)
        elif challenger_dict.get('total_points') < challengee_dict.get('total_points'):
            await contract.execute_contract(contract.challengee)
            await self.assign_role(int(contract.challenger.discord_id), self.loser_role_name, self.gold_color)   
            await self.display_slap_results(contract, challengee_id, challenger_dict.get('total_points'), challengee_dict.get('total_points'))
        else:
            await contract.refund()
            

    async def execute_by_contract_type(self, contract_type):
        CONTRACT_EXECUTORS = {
            Vault.SlapContract.__name__ : self.execute_slap,
            Vault.GroupWagerContract.__name__ : self.execute_wager,
        }

        prev_week = None
        while await self._vault.ready_to_execute(contract_type=contract_type):
            contract = await self._vault.get_next_contract(contract_type=contract_type)
            current_week = contract.week

            if prev_week is None or prev_week != current_week:
                week_dict = await self.get_matchup_data(current_week)
                prev_week = current_week

            executor = CONTRACT_EXECUTORS.get(contract_type)
            if executor is None:
                raise ValueError("contract_type is invalid.")
            
            await executor(contract, week_dict)

            await self._vault.pop_contract(contract_type=contract_type)
            await self.store_all()


    async def execute_all_contracts(self):
        logger.info("[MaintainVault] - Executing all Contracts")
        await self.execute_by_contract_type(contract_type=Vault.SlapContract.__name__)
        await self.execute_by_contract_type(contract_type=Vault.GroupWagerContract.__name__)


    ###################################################
    # Create Contract Commands        
    ###################################################

    class MatchupTextPredictionValue(discord.ui.Modal):
        def __init__(self, outer:"MaintainVault", team_name:str, team_id:str, wager:Vault.GroupWagerContract, prediction_account:Vault.BankAccount):
            super().__init__(
                title='Wager',
            )
            self.outer = outer
            self.team_name = team_name
            self.team_id = team_id
            self.wager = wager
            self.prediction_account = prediction_account
            self.points_prediction = discord.ui.TextInput(
                label="Total Cumulative Points Prediction", 
                style=discord.TextStyle.short,
                placeholder='Example: 200',
                required=True
            )
            self.add_item(self.points_prediction)


        async def on_error(self, interaction, error):
            return await super().on_error(interaction, error)
        

        async def on_submit(self, interaction: discord.Interaction):
            try:
                points = int(self.points_prediction.value)
            except ValueError:
                await interaction.response.send_message("Invalid type, expected an integer.")

            gambler:Vault.BankAccount = await Vault.bank_account_by_discord_id(str(interaction.user.id))              
            try:
                prediction = await Vault.bank_account_by_discord_id(self.team_id)
                if not prediction:
                    raise ValueError("Member doesn't exist")
                await self.wager.add_prediction(gambler=gambler, prediction_id=prediction.fantasy_id, prediction_points=points, amount = self.outer._default_wager_amount)
            except Exception as e:
                message = f"Add prediction failed. Error: {e}"
                logger.warning(message)
                await interaction.response.send_message(message)
                return
            await self.outer.store_all()

            message = f"{interaction.user.mention} successfully placed {self.outer._default_wager_amount} tokens on {self.prediction_account.discord_tag}."
            logger.info(message)
            await interaction.response.send_message(message)


    class MatchupSelectConfirmView(discord.ui.View):

        def __init__(self, outer: "MaintainVault", selected_matchups:list, options:list, wagers_deque, team_1_name:str, team_2_name:str):
            super().__init__()
            self.outer = outer
            self.bot = outer.bot
            self.wagers_deque = wagers_deque # This is a copy
            self.members_filename = self.bot.state.members_filename
            self.selected_matchups_index = selected_matchups[0]
            self.options = options
            self.team_1_name = team_1_name
            self.team_2_name = team_2_name

            team_1_button = discord.ui.Button(label=team_1_name.split(' ')[-1], style=discord.ButtonStyle.primary)
            team_1_button.callback = self.select_first
            self.add_item(team_1_button)

            team_2_button = discord.ui.Button(label=team_2_name.split(' ')[-1], style=discord.ButtonStyle.primary)
            team_2_button.callback = self.select_second
            self.add_item(team_2_button)


        ##############################################################
        # Helpers
        ##############################################################

        async def disable_buttons(self):
            for child in self.children:
                if isinstance(child,discord.ui.Button):
                    child.disabled = True


        ##############################################################
        # Overloaded def - Errors
        ##############################################################

        async def on_timeout(self):
            await self.disable_buttons()


        async def on_error(self,interaction:discord.Interaction, error, item):
            if interaction.response.is_done():
                await interaction.followup.send(f'Error: {error}', ephemeral=True)
            else:
                await interaction.response.send_message(f'Error: {error}', ephemeral=True)


        async def select_first(self, interaction:discord.Interaction):
            await self.disable_buttons()

            prediction = self.wagers_deque[int(self.selected_matchups_index)]
            chosen_yahoo_id = prediction.team_1_id

            chosen_discord_id = await utility.teamid_to_discord(chosen_yahoo_id,self.outer._persistent_manager)
            prediction_bank_account:Vault.BankAccount = await Vault.bank_account_by_discord_id(discord_id=str(chosen_discord_id))
            wager:Vault.GroupWagerContract = await Vault.get_wager(fantasy_id = prediction_bank_account.fantasy_id)
            
            if wager is None:
                await interaction.response.send_message()('Matchup not found.')
                return
            
            modal = MaintainVault.MatchupTextPredictionValue(self.outer, self.team_1_name, chosen_discord_id, wager, prediction_bank_account)
            await interaction.response.send_modal(modal)


        async def select_second(self, interaction:discord.Interaction):
            await self.disable_buttons()

            prediction = self.wagers_deque[int(self.selected_matchups_index)]
            chosen_yahoo_id = prediction.team_2_id

            chosen_discord_id = await utility.teamid_to_discord(chosen_yahoo_id,self.outer._persistent_manager)
            prediction_bank_account:Vault.BankAccount = await Vault.bank_account_by_discord_id(discord_id=str(chosen_discord_id))
            wager:Vault.GroupWagerContract = await Vault.get_wager(fantasy_id = prediction_bank_account.fantasy_id)
            
            if wager is None:
                await interaction.response.send_message()('Matchup not found.')
                return
            
            modal = MaintainVault.MatchupTextPredictionValue(self.outer, self.team_2_name, chosen_discord_id, wager, prediction_bank_account)
            await interaction.response.send_modal(modal)
            await interaction.response.edit_message(view=self)


        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
        async def second_button_callback(self, interaction:discord.Interaction, button:discord.Button):
            await self.disable_buttons()
            await interaction.response.send_message("Canceled operation.", ephemeral=True)


    class MatchupSelect(discord.ui.Select):
        def __init__(self, outer: "MaintainVault", wagers_deque):
            super().__init__(
                min_values=1,
                max_values=1
            )
            self.outer = outer
            self.wagers_deque = wagers_deque
            self.bot = outer.bot
            self.members_filename = outer.bot.state.members_filename


        async def callback(self, interaction: discord.Interaction):
            index = int(self.values[0])
            wager = self.wagers_deque[index]
            team_1_name = await utility.teamid_to_name(int(wager.team_1_id), self.outer._persistent_manager)
            team_2_name = await utility.teamid_to_name(int(wager.team_2_id), self.outer._persistent_manager)

            view = MaintainVault.MatchupSelectConfirmView(self.outer,self.values, self.options, self.wagers_deque, team_1_name, team_2_name)
            await interaction.response.send_message("Place your wager.", view=view, ephemeral=True)


    async def construct_week_wagers_select(self):
        wagers_deque:deque[Vault.GroupWagerContract] = await Vault.get_all_wagers()

        # build Select
        select = self.MatchupSelect(self, wagers_deque)
        for i, value in enumerate(wagers_deque):
            team_1_id = value.team_1_id
            team_2_id = value.team_2_id

            team_1_name = await utility.teamid_to_name(team_1_id, self._persistent_manager)
            team_2_name = await utility.teamid_to_name(team_2_id, self._persistent_manager)

            select.add_option(label=f"{team_1_name} VS {team_2_name}", value=f'{i}', default=False)
        return select


    @app_commands.command(name='wager', description="Place a wager on one of this week's matchups.")
    async def wager(self, interaction:discord.Interaction):
        if not self.bot.state.bot_features.vault_enabled and not self.bot.state.bot_features.wagers_enabled:
            message = f"Either Wagers or Vault Disabled. \n {self.bot.state.bot_features}"
            logger.warning(f'[MaintainVault] - {message}')
            await interaction.followup.send(message)
            return

        if not await Vault.ready_to_execute(contract_type=Vault.GroupWagerContract.__name__):
            await self.create_current_week_wagers()

        select = await self.construct_week_wagers_select()
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("Select Matchup to Wager on.", view=view, ephemeral=True)


    @app_commands.command(name='wager_leaderboard', description="Token Leaderboard.")
    async def wager_leaderboard(self, interaction:discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.bot.state.bot_features.vault_enabled:
            logger.warning('[MaintainVault] - enable_vault to use wager_leaderboard.')
            await interaction.follow.send('Vault not enabled. Use enable_vault to use wager features.')
            return
        
        today = datetime.today()
        embed = discord.Embed(title='Wager Leaderboard', description='Current token standings.', color=self.emb_color, timestamp=today)

        accounts = await self._vault_manager.load_json(filename=self._vault_accounts_filename)
        sorted_accounts = sorted(accounts, key=lambda x:int(x.get('money')), reverse=True)

        for account in sorted_accounts:

            value = utility.to_block(f'Tokens: {account.get('money')}\nFantasy ID: {account.get('fantasy_id')}') + f'{account.get('discord_tag')}'
            embed.add_field(name=account.get('name'), value=value, inline=False)

        await interaction.followup.send(embed=embed)


    ###################################################
    # Manual Slash Commands        
    ###################################################

    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='enable_vault', description='Enables Vault and wagers. Only run after binding all users.')
    async def enable_vault(self,interaction:discord.Interaction):
        await interaction.response.defer()
        await self.bot.state.bot_features.enable_wagers()
        await interaction.followup.send('Vault and Wagers Enabled.')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='execute_contracts', description='manually execute contracts.')
    async def execute_contracts(self,interaction:discord.Interaction):
        await interaction.response.defer()
        if not self._ready:
            await interaction.followup.send('Failed startup. try again.')
            return
        try:
            await self.execute_all_contracts()
        except Exception as e:
            await interaction.followup.send(f'Error: Failed to execute. {e}')
        await interaction.followup.send('Done.')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='add_money', description='Add funds to user account')
    @app_commands.describe(discord_user="User's Discord Tag", amount="Amount to add.")
    async def add_money(self,interaction:discord.Interaction, discord_user:discord.User, amount:int):
        await interaction.response.defer()
        if not self._ready:
            await interaction.followup.send('Failed startup. try again.')
            return

        fantasy_id = await self._vault.fantasy_id_by_discord_id(str(discord_user.id))
        if fantasy_id is None:
            await interaction.followup.send('Error: User not found.')
        else:
            await self._vault.add_money(fantasy_id=fantasy_id, amount = amount)
            balance_info = await self._vault.bank_account_info_by_discord_id(str(discord_user.id))
            await interaction.followup.send(f'```{balance_info}```')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='deduct_money', description='Deduct funds to user account')
    @app_commands.describe(discord_user="User's Discord Tag", amount="Amount to deduct.")
    async def deduct_money(self, interaction:discord.Interaction, discord_user:discord.User, amount:int):
        await interaction.response.defer()
        if not self._ready:
            await interaction.followup.send('Failed startup. try again.')
            return

        fantasy_id = await self._vault.fantasy_id_by_discord_id(str(discord_user.id))
        if fantasy_id is None:
            await interaction.followup.send('Error: User not found.')
        else:
            await self._vault.deduct_money(fantasy_id=fantasy_id, amount = amount)
            balance_info = await self._vault.bank_account_info_by_discord_id(str(discord_user.id))
            await interaction.followup.send(f'```{balance_info}```')


    @app_commands.checks.has_role(int(os.getenv('MANAGER_ROLE')))
    @app_commands.command(name='transfer_money', description='Transfer funds to user account')
    @app_commands.describe(discord_user_from="User's Discord Tag to deduct.", discord_user_to="User's Discord Tag to add.", amount="Amount to transfer.")
    async def transfer_money(self, interaction:discord.Interaction, discord_user_from:discord.User, discord_user_to:discord.User, amount:int):
        await interaction.response.defer()
        if not self._ready:
            await interaction.followup.send('Failed startup, try again.')
            return

        fantasy_id_to = await self._vault.fantasy_id_by_discord_id(str(discord_user_to.id))
        fantasy_id_from = await self._vault.fantasy_id_by_discord_id(str(discord_user_from.id))
        if fantasy_id_to is None or fantasy_id_from is None:
            await interaction.followup.send('Error: User not found.')
        else:
            await self._vault.transfer_money(to_fantasy_id=fantasy_id_to, from_fantasy_id=fantasy_id_from, amount = amount)
            balance_info_to = await self._vault.bank_account_info_by_discord_id(str(discord_user_to.id))
            balance_info_from = await self._vault.bank_account_info_by_discord_id(str(discord_user_from.id))
            await self._vault_manager.write_pickle(filename=self._vault_pickle_filename, data=self._vault)
            await interaction.followup.send(f'```{balance_info_to}```\n```{balance_info_from}```')


    ###################################################
    # Create this weeks contracts        
    ###################################################

    async def create_wagers_from_matchup_data(self, data_dict):
        for key, value in data_dict.items():
            await Vault.create_contract(
                team_1_id=value.get('team_id'),
                team_2_id=value.get('team_opponent_id'),
                expiration_date=datetime.strptime(value.get('week_end'), '%Y-%m-%d'),
                week=value.get('week'),
                amount = 0,
                bonus = self._default_wager_bonus,
                contract_type=Vault.GroupWagerContract.__name__
            )
            await self.store_all()


    async def check_contracts_ready(self) -> bool:
        group_wager_ready = await Vault.ready_to_execute(contract_type=Vault.GroupWagerContract.__name__)
        slap_wager_ready = await Vault.ready_to_execute(contract_type=Vault.SlapContract.__name__)
        if group_wager_ready or slap_wager_ready:
            logger.info("Last Week's contracts must be executed.")
            await self.execute_all_contracts()
        
        if await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__):
            logger.info("Current week contracts already created.")
            return False
        return True


    async def create_current_week_wagers(self):
        async with self.bot.state.league_lock:
            league = self.bot.state.league
        current_week = league.current_week

        if not await self.check_contracts_ready():
            return
        
        data_dict = await self.get_matchup_data(current_week)
        await self.create_wagers_from_matchup_data(data_dict)


    @tasks.loop(minutes=1440)
    async def update_wagers(self):
        await self.create_current_week_wagers()
        

    ###################################################
    # Weekly Maintenance
    ###################################################

    async def distribute_weekly_funds(self, current_week_data:dict):
        for key, _ in Vault.accounts.items():
            await Vault.add_money(key,self._weekly_bank_funds)

        current_week_data["distibuted_funds"] = self._weekly_bank_funds
        current_week_data["distributed"] = True


    async def create_funds_log(self):
        loaded_dates:dict = await FantasyHelper.load_week_dates(bot=self.bot, week_dates_filename=self._week_dates_filename)

        funds_log_dict = {}
        for key, value in loaded_dates.items():
            funds_log_dict[key] = {
                "start_date":value[0],
                "end_date":value[1],
                "distibuted_funds":0,
                "distributed":False
            }
        return funds_log_dict
    

    @tasks.loop(minutes=1440)
    async def week_start_check(self):
        data = await self._persistent_manager.load_json(filename=self._funds_distribution_log)

        if not data:
            data = await self.create_funds_log()

        async with self.bot.state.league_lock:
            fantasy_league = self.bot.state.league

        current_week = fantasy_league.current_week

        current_week_data = data.get(str(current_week))
        if not current_week_data:
            raise ValueError("[MaintainVault][week_start_check] - Invalid week.")
            
        if current_week_data.get("distributed"):
            return
        
        await self.distribute_weekly_funds(current_week_data=current_week_data)
        await self._persistent_manager.write_json(filename=self._funds_distribution_log, data=data)


    ###################################################
    # Remove Week Roles      
    ###################################################

    async def remove_challenge_roles(self):
        channel:discord.TextChannel = await self.get_slaps_channel()
        if channel is None:
            logger.warning('Unable to remove challenge roles. Channel is None')
        
        guild:discord.Guild = channel.guild

        try:
            await FantasyHelper.remove_role_members_by_guild(guild=guild, role_name=self.loser_role_name)
        except Exception as e:
            logger.error(f"Unable to remove member's {self.loser_role_name}. Error: {e}")
            return
        
        try:
            await FantasyHelper.remove_role_members_by_guild(guild=guild, role_name=self.denier_role_name)
        except Exception as e:
            logger.error(f"Unable to remove member's {self.denier_role_name}. Error: {e}")
            return

    @tasks.loop(minutes=1440)
    async def end_week_tasks(self):
        async with self.bot.state.league_lock:
            fantasy_league = self.bot.state.league
        current_week:int = fantasy_league.current_week

        _, end_date = await FantasyHelper.get_current_week_dates(self.bot, current_week, self._week_dates_filename)
        
        if date.today() == end_date.date():
            logger.info("[MaintainVault][end_week_tasks] - End of Week: Removing week's assigned roles.")
            await self.remove_challenge_roles()
        else:
            logger.info(f"[MaintainVault][end_week_tasks] - Week {current_week}'s end date: {end_date}, Current date: {date.today()}")


    ###################################################
    # Error Handling         
    ###################################################

    @update_wagers.error
    async def update_wagers_error(self,error):
        logger.error(f'[MaintainVault][update_wagers_error] - Error: {error}')


    @end_week_tasks.error
    async def end_week_tasks_error(self,error):
        logger.error(f"[MaintainVault][end_week_tasks_error] - Error: {error}")


    @week_start_check.error
    async def week_start_check_error(self,error):
        logger.error(f"[MaintainVault][week_start_check_error] - Error: {error}")


    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        message = ""
        if isinstance(error, app_commands.CommandNotFound):
            message = "This command does not exist."
        elif isinstance(error, app_commands.CheckFailure):
            message = "You do not have permission to use this command."
        else:
            message = "An error occurred. Please try again."

        logger.error(f"[MaintainVault] - Error: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error(f"[MaintainVault] - Failed to send error message: {e}")


    ###################################################
    # Setup          
    ###################################################

    async def construct_new_bank_accounts(self) -> dict[str,Vault.BankAccount]:
        members:list[dict] = await self._persistent_manager.load_json(filename = self._members_filename)

        if not members:
            raise AttributeError(f'[MaintainVault][construct_new_bank_accounts] - Error: expected {self._members_filename} to be populated.' )
        else:
            accounts:dict[str, Vault.BankAccount] = {}
            for entry in members:
                if entry.get('discord_id') is None:
                    raise ValueError('[MaintainVault][construct_new_bank_accounts] - Error: Use bind commands to bind yahoo_id to discord_tag.')

                bank_account = Vault.BankAccount(
                    entry.get('name'),
                    utility.id_to_mention(entry.get('discord_id')),
                    entry.get('discord_id'),
                    entry.get('id'),
                    self._initial_bank_funds
                )
                accounts[entry.get('id')] = bank_account
            return accounts
        

    async def get_member_dict(self, fantasy_id:str):
        members:list[dict] = await self._persistent_manager.load_json(filename = self._members_filename)
        for member in members:
            if member.get('id') == fantasy_id:
                return member


    async def update_account_names(self):
        for key, value in Vault.accounts.items():
            member = await self.get_member_dict(key)
            value.name = member.get('name')


    ####################################################
    # Load and store accounts/contracts
    ####################################################

    async def store_accounts(self):
        serialized_accounts = await self._vault.serialize_accounts()
        await self._vault_manager.write_json(self._vault_accounts_filename, serialized_accounts)
        

    async def store_contracts(self):
        serialized_slap_contracts = await self._vault.serialize_contracts(contract_type=Vault.SlapContract.__name__)
        serialized_wager_contracts = await self._vault.serialize_contracts(contract_type=Vault.GroupWagerContract.__name__)
        await self._vault_manager.write_json(self._vault_slap_contracts_filename, serialized_slap_contracts)
        await self._vault_manager.write_json(self._vault_wager_contracts_filename, serialized_wager_contracts)


    async def store_all(self):
        await self.store_accounts()
        await self.store_contracts()
        logger.info('[MaintainVault][store_accounts] - Bank accounts, slap contracts and wagers saved.')


    async def load_filename(self, filename):
        data = await self._vault_manager.load_json(filename)
        if data:
            return data
        return None

    async def load_all(self) -> Vault:
        serialized_accounts = await self.load_filename(self._vault_accounts_filename)
        serialized_slap_contracts = await self.load_filename(self._vault_slap_contracts_filename)
        serialized_wager_contracts = await self.load_filename(self._vault_wager_contracts_filename)

        if not serialized_accounts:
            return None

        new_vault = Vault()
        await new_vault.initialize_from_serialized(accounts=serialized_accounts, slap_contracts=serialized_slap_contracts, wager_contracts=serialized_wager_contracts)
        return new_vault


    ####################################################
    # Setup
    ####################################################

    async def is_enabled(self):
        while(not self.bot.state.bot_features.vault_enabled):
            await asyncio.sleep(2)


    async def init_vault(self):
        loaded_vault = await self.load_all()
        if loaded_vault is None:
            try:
                loaded_vault = Vault()
                accounts:dict[str,Vault.BankAccount] = await self.construct_new_bank_accounts()
                await loaded_vault.initialize(accounts=accounts)

            except Exception as e:
                logger.error('[MaintainVault][Initialization] - Failed to initialize new Vault.')
                logger.error(f'[MaintainVault][Initialization] - Error: {e}')
                return
        else:
            await self.update_account_names()

        self.bot.state.vault = loaded_vault
        self._vault = self.bot.state.vault
        await self.store_accounts()
        self._ready = True


    async def wait_for_fantasy_and_memlist(self):
        while not self._ready_to_init:
            async with self.bot.state.fantasy_query_lock:
                fantasy_query = self.bot.state.fantasy_query
            async with self.bot.state.memlist_ready_lock:
                memlist_ready = self.bot.state.memlist_ready
            if memlist_ready and fantasy_query is not None:
                self._ready_to_init = True
            else:
                await asyncio.sleep(1)   


    async def load_challenge_variables(self):
        data = await self.bot.state.settings_manager.load_json(filename = self._challenge_filename)
        self.loser_role_name=data.get("loser_role_name")
        self.denier_role_name=data.get("denier_role_name")
        self._initial_bank_funds= int(data.get("initial_bank_funds"))
        self._weekly_bank_funds= int(data.get("weekly_bank_funds"))
        self._default_wager_amount = int(data.get("default_wager_amount"))
        self._default_wager_bonus = int(data.get("default_bonus_amount"))
        self.challenger_wins_link = data.get("challenger_wins_link")
        self.challengee_wins_link = data.get("challengee_wins_link")
        self.tie_link = data.get("tie_link")
        self.wager_winner_link = data.get("wager_winner_link")


    async def create_and_store_contract(self):
        expiration = datetime.today() - timedelta(days=4)
        try:
            await Vault.create_contract(
                challenger_fantasy_id='3',
                challengee_fantasy_id='5',
                amount=10, 
                expiration_date=expiration, 
                week=4, 
                contract_type=Vault.SlapContract.__name__
            )
            await self.store_all()
        except Exception as e:
            logger.error(f'[MaintainVault][create_and_store] - Failed to create Contract. Error:{e}')
            
        
    @commands.Cog.listener()
    async def on_ready(self): 
        # Wait for FantasyQuery Init and memlist init
        await self.wait_for_fantasy_and_memlist()
        logger.info('[MaintainVault] - Memlist and Fantasy Query Awaited.')

        # Wait for Feature Enable
        await self.is_enabled()
        logger.info('[MaintainVault] - Enabled')

        await self.init_vault()
        await self.load_challenge_variables()
        logger.info('[MaintainVault] - Initialized MaintainVault')

        self.week_start_check.start()
        self.update_wagers.start()
        ## temporary for testing ##
        #await self.create_and_store_contract()


    ####################################################
    # Handle Load
    ####################################################

    async def cog_load(self):
        logger.info('[MaintainVault] - Cog Load .. ')
        guild = discord.Object(id=self.bot.state.guild_id)
        for command in self.get_app_commands():
            self.bot.tree.add_command(command, guild=guild)


    ###################################################
    # Handle Exit           
    ###################################################

    def cog_unload(self):
        logger.info('[MaintainVault] - Cog Unload')



async def setup(bot):
    await bot.add_cog(MaintainVault(bot))