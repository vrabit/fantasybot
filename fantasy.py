import os
import sys
from logging import DEBUG
from pathlib import Path

from dotenv import load_dotenv

project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

from yfpy import Data
from yfpy.logger import get_logger

import utility


#player_url = self.constants.LEAGUE_URL+'/players;player_keys=449.p.30123/stats;type=week;week=2'
#player_url = self.constants.LEAGUE_URL+ '/players;player_keys=449.p.30123/ownership;type=week;week=2'

class fantasyQuery:
    @property
    def PLAYER_URL(self):
        return 'https://fantasysports.yahooapis.com/fantasy/v2/player/'


    @property
    def LEAGUE_URL(self):
        return 'https://fantasysports.yahooapis.com/fantasy/v2/league/' + self.yahoo_query.get_league_key()


    @property
    def GAME_URL(self):
        return 'https://fantasysports.yahooapis.com/fantasy/v2/game/'   
    

    @property
    def TRANSACTIONS_URL(self):
        return 'https://fantasysports.yahooapis.com/fantasy/v2/transaction//'
    

    @property
    def SEASON(self):
        return 2024


    def __init__(self, yahoo_query):
        self.yahoo_query = yahoo_query  
        self.player_dict = utility.load_players()
        self.stat_dict = utility.create_stat_file(self.get_stat_categories())
        self.league_key = self.yahoo_query.get_league_key()


    def get_player_id(self, name):
        return self.player_dict.get(name)


    def team_info(self):
        print('called...')
        teams = self.yahoo_query.get_league_teams()
        curr_data = repr(self.yahoo_query.get_league_teams())
        print(curr_data)
        return curr_data
    

    #all matchups
    def get_teams(self):
        return self.yahoo_query.get_league_teams()
    

    def get_player_info(self,player_id):
        pass


    def get_player(self,player_id):
        game_id = self.yahoo_query.game_id
        player_key = utility.compose_player_key(game_id,player_id)

        player_url = self.PLAYER_URL + player_key
        return self.yahoo_query.query(player_url,[],data_type_class=None, sort_function=None)


    def get_player_stats(self, player_id):
        game_id = self.yahoo_query.game_id
        player_key = utility.compose_player_key(game_id,player_id)
        temp = self.yahoo_query.get_player_stats_for_season(player_key)
        return temp


    #find and replace what i use this for
    def get_league(self):
        league_url = self.LEAGUE_URL
        return self.yahoo_query.query(league_url,[],data_type_class=None, sort_function=None)
        

    def get_game(self):
        game_url = self.GAME_URL + self.yahoo_query.get_game_key_by_season(self.SEASON)
        return self.yahoo_query.query(game_url,[],data_type_class=None, sort_function=None)


    def get_league_stats(self,player_id):
        game_id = self.yahoo_query.game_id
        player_key = utility.compose_player_key(game_id,player_id)
        player_url = self.LEAGUE_URL +f'/players;player_keys={player_key};out=ownership,stats'
        return self.yahoo_query.query(player_url,[],data_type_class=None, sort_function=None)


    def get_ownership(self,player_id):
        game_id = self.yahoo_query.game_id
        week = self.get_league()['league'].current_week
        player_key = utility.compose_player_key(game_id,player_id)
        player_url = self.LEAGUE_URL+ f'/players;player_keys={player_key}/ownership;type=week;week={week}'
        return self.yahoo_query.query(player_url,[],data_type_class=None, sort_function=None)


    def get_team_roster(self,team_id,chosen_week):
        return self.yahoo_query.get_team_roster_by_week(team_id, chosen_week)


    def get_scoreboard(self, week):
        return self.yahoo_query.get_league_scoreboard_by_week(week)
    

    def get_roster(self,team_id, chosen_week):
        return self.yahoo_query.get_team_roster_by_week(team_id,chosen_week)
    

    def team_stats(self,player_id,week):
        game_id = self.yahoo_query.game_id
        player_key = utility.compose_player_key(game_id,player_id)
        temp = self.yahoo_query.get_player_stats_by_week(player_key, week)
        return temp


    def get_stat_categories(self):
        game_id = self.yahoo_query.game_id
        return self.yahoo_query.get_game_stat_categories_by_game_id(game_id)


    def get_league_transactions(self):
        game_id = self.yahoo_query.game_id
        player_url = self.TRANSACTIONS_URL
        return self.yahoo_query.query(player_url,[],data_type_class=None, sort_function=None)


    def get_game_weeks(self):
        game_url = self.GAME_URL + self.yahoo_query.get_game_key_by_season(self.SEASON)
        return self.yahoo_query.query(f'{game_url}/game_weeks',['game'],data_type_class=None, sort_function=None)
    

    def get_team_stats(self, week, team_id):
        return self.yahoo_query.get_team_stats_by_week(team_id, week)


    #doesnt quite work
    def get_player_week(self,player_id,week):
        game_id = self.yahoo_query.game_id
        player_key = utility.compose_player_key(game_id,player_id)
        player_url = self.LEAGUE_URL+ f'/players;player_keys={player_key}/stats/player_stats?type=week&week={week}'
        return self.yahoo_query.query(player_url,[],data_type_class=None, sort_function=None)
        
        
    def get_all_standings(self,number_of_teams):
        i = 1
        unsorted = []
        
        while i <= number_of_teams:
            obj = self.yahoo_query.get_team_standings(i)
            group = (i,obj)
            unsorted.append(group)
            i += 1
        return unsorted
