import utility


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
        return 'https://fantasysports.yahooapis.com/fantasy/v2/league/' + self.yahoo_query.get_league_key() + '/transactions'
    

    @property
    def SEASON(self):
        return self.league.season


    def __init__(self, yahoo_query):
        self.yahoo_query = yahoo_query  
        self.stat_dict = self.create_stat_file(self.get_stat_categories())
        self.league_key = self.yahoo_query.get_league_key()
        self.league = self.get_league()['league']


    def create_stat_file(self,categories):
        entry = {}
        for i in range(len(categories.stats)):
            entry[str(categories.stats[i].stat_id)] = categories.stats[i].name

        return entry


    def get_league_teams(self):
        return self.yahoo_query.get_league_teams()

    
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
        season_stats = self.yahoo_query.get_player_stats_for_season(player_key)
        return season_stats


    def get_league(self):
        league_url = self.LEAGUE_URL
        return self.yahoo_query.query(league_url,[],data_type_class=None, sort_function=None)
        

    def get_players(self, start=0, count=25):
        league_url = self.LEAGUE_URL
        url=f'{league_url}/players?count={count}&start={start}'
        return self.yahoo_query.query(url,[],data_type_class=None, sort_function=None)


    def get_league_info(self):
        return self.yahoo_query.get_league_info()
    

    def check_recent_transactions(self,start=0,count=25):
        response = self.yahoo_query.query(f'{self.TRANSACTIONS_URL};start={start};count={count}',[],data_type_class=None, sort_function=None)
        return response
    

    def pull_batch_transactions(self,start,count=25):
        return self.yahoo_query.query(f'{self.TRANSACTIONS_URL};start={start};count={count}',[],data_type_class=None, sort_function=None)


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
        team_stats = self.yahoo_query.get_player_stats_by_week(player_key, week)
        return team_stats


    def get_stat_categories(self):
        game_id = self.yahoo_query.game_id
        stat_categories = self.yahoo_query.get_game_stat_categories_by_game_id(game_id)
        return stat_categories


    def get_game_weeks_by_game_id(self):
        return self.yahoo_query.get_game_weeks_by_game_id(self.yahoo_query.game_id)


    def get_team_stats(self, week, team_id):
        team_stats = self.yahoo_query.get_team_stats_by_week(team_id, week)
        return team_stats


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
