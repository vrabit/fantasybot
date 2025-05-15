import json
import os

from pathlib import Path
import string
from collections import deque

import csv
import asyncio

current_dir = Path(__file__).parent


EMPTY = '\u001b'
private_lock = asyncio.Lock()
member_lock = asyncio.Lock()

###################################################
# load and store private.json file
###################################################
async def private_json_creator(file_path):
    """Create private.json file if it does not exist.
    Args:
        file_path (str): Path to the private.json file
    """
    async with private_lock:
    # create private.json file
        with open(file_path, 'w') as file:
            data = {
                'news_channel_id': None,
                'channel_id': None
            }
            json.dump(data, file, indent=4)
        
    return data


def get_private_data() -> dict:
    """Load discord private.json file.
    Returns:
        dict: Data from private.json
    """
    # load private.json file
    with open(current_dir / 'discordauth'/ 'private.json','r') as file:
        data = json.load(file)
    return data


def store_private_data(data) -> None:
    """Store discord private.json file.
    Args:
        data (dict): Data to be stored in private.json
    """
    # store private.json file
    with open(current_dir / 'discordauth'/ 'private.json','w') as file:
        json.dump(data, file, indent = 4)


async def get_private_discord_data_async() -> dict:
    """Load discord private.json file asynchronously.
    Returns:
        dict: Data from private.json
    """
    file_path = current_dir / 'discordauth' / 'private.json'
    if file_path.exists():
        async with private_lock:
            # load private.json file
            with open(file_path,'r') as file:
                data = json.load(file)
        return data
    else:
        return await private_json_creator(file_path)


async def set_private_discord_data_async(data) -> None:
    """Store discord private.json file asynchronously.
    Args:
        data (dict): Data to be stored in private.json
    """
    file_path = current_dir / 'discordauth' / 'private.json'
    async with private_lock:
        # store private.json file
        with open(file_path,'w') as file:
            json.dump(data, file, indent = 4)


###################################################
# store obj
###################################################

def serialize_matchups(scoreboard):
    """Serialize matchups data to a dictionary.
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

 
def store_matchups(data, filename:str):
    recap_dir = current_dir / 'recap'
    os.makedirs(recap_dir,exist_ok=True)

    serialized_data = serialize_matchups(data)

    with open(current_dir / 'recap' / filename,'w') as file:
        json.dump(serialized_data, file, indent = 2)


###################################################
# player ID          
###################################################

def load_players():
    new_dict = {}
    with open(current_dir / 'yfpyauth'/ 'player_ids.csv','r') as file:
        csv_reader = csv.DictReader(file)

        for row in csv_reader:
            key = row['yahoo_name']
            value = row['yahoo_id']

            new_dict[key] = value

    return new_dict


###################################################
# members          
###################################################

def load_members():
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    return members


def number_of_teams():
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    return len(members)


def init_memlist(teams):
    # Create member list file
    if not os.path.exists(current_dir / 'persistent_data'/ 'members.json'):
        members = []
        for i in range(len(teams)):
            entry = {}
            entry['name'] = teams[i].name.decode('utf-8')
            entry['id'] = str(teams[i].team_id)
            members.append(entry)


        with open(current_dir / 'persistent_data'/ 'members.json', 'w') as file:
            json.dump(members, file, indent = 4)
    else:
        with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
            members = json.load(file)

        for i in range(len(members)):
            members[i]['name'] = teams[i].name.decode('utf-8')
        
        with open(current_dir / 'persistent_data'/ 'members.json', 'w') as file:
            json.dump(members, file, indent = 4)


def create_stat_file(categories):
    entry = {}
    for i in range(len(categories.stats)):
        entry[str(categories.stats[i].stat_id)] = categories.stats[i].name

    return entry

###################################################
# Setup persistent week dates          
###################################################

def load_dates():
    date_file = current_dir / 'persistent_data' / 'week_dates.json'

    with open(date_file,'r') as file:
        dates_list = json.load(file)

    return dates_list


def store_dates(dates_dict):
    date_file = current_dir / 'persistent_data' / 'week_dates.json'

    with open(date_file, 'w') as file:
        json.dump(dates_dict, file, indent = 4)


def construct_date_list(gameweek_list):
    dates_dict = {}
    for i in range(len(gameweek_list)):
        week = gameweek_list[i]['game_week'].week
        current_entry = [gameweek_list[i]['game_week'].start,gameweek_list[i]['game_week'].end]
        dates_dict[week] = current_entry

    return dates_dict

###############################################
# create and maintain current slap challenges
###############################################

def clear_challenges():
    with open(current_dir/ 'persistent_data'/ 'challenges.json', 'w') as file:
        json.dump({},file)


def load_challenges():
    challenges_file = current_dir/ 'persistent_data'/ 'challenges.json'

    if os.path.exists(challenges_file):
        with open(challenges_file, 'r') as file:
            challenges = json.load(file)
    else:
        challenges = {}
        with open(challenges_file, 'w') as file:
            json.dump(challenges,file)
            
    # convert to list to deque()
    converted = {}
    for key, value in challenges.items():
        converted[key] = deque(value)

    return challenges


def save_challenges(challenges):
    serializable = {}
    for key, value in challenges.items():
        serializable[key] = list(value)

    with open(current_dir/ 'persistent_data'/ 'challenges.json', 'w') as file:
        json.dump(serializable, file, indent = 4)


def check_queue_exists(queue, team_id):
    return team_id in queue


def check_exists(challenger_team_id, challengee_team_id, challenges):
    challenger_queue = challenges.get(challenger_team_id)
    challengee_queue = challenges.get(challengee_team_id)
    
    # Check if the challenge exists in either queue
    if challenger_queue and check_queue_exists(challenger_queue, challengee_team_id):
        return True
    if challengee_queue and check_queue_exists(challengee_queue, challenger_team_id):
        return True
    
    return False


def add_challenges(challenger_team_id, challengee_team_id):
    # load challenges
    challenges = load_challenges()

    if check_exists(challenger_team_id, challengee_team_id, challenges):
        return

    if challenges.get(challenger_team_id) is not None:
        challenges[challenger_team_id].append(challengee_team_id)
    else:
        new_deque = deque([challengee_team_id])
        challenges[challenger_team_id] = new_deque

    save_challenges(challenges)


def bind_discord(draft_id, discord_id) -> None:
    """    Bind Yahoo draft id to Discord id
    
    Args:
        draft_id (str): Yahoo draft id 
        discord_id (str): Discord id
    """
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)
    
    for i in range(len(members)):
        if members[i].get('id') == str(draft_id):
            members[i]['discord_id'] = str(discord_id)
            break

    with open(current_dir / 'persistent_data'/ 'members.json', 'w') as file:
        json.dump(members, file, indent = 4)


async def bind_discord_async(draft_id, discord_id) -> None:
    """Bind Yahoo draft id to Discord id
    
    Args:
        draft_id (str): Yahoo draft id 
        discord_id (str): Discord id
    """
    async with member_lock:
        with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
            members = json.load(file)
        
        for i in range(len(members)):
            if members[i].get('id') == str(draft_id):
                members[i]['discord_id'] = str(discord_id)
                break

        with open(current_dir / 'persistent_data'/ 'members.json', 'w') as file:
            json.dump(members, file, indent = 4)


def compose_player_key(game_key, player_id):
    return f'{game_key}.p.{player_id}'


def format_member(member,id):
    new_mem = {str(member): str(id)}
    return new_mem


def append_memlist_member(member, id):
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as read_file:
        members =json.load(read_file)

    members.append(format_member(member,id))

    with open(current_dir / 'persistent_data'/ 'members.json','w') as write_file:
        json.dump(members, write_file, indent = 4)


def teamid_to_discord(team_id):
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    for i in range(len(members)):
        if members[i].get('id') == str(team_id):
            return members[i].get('discord_id')
        
    return None


def teamid_to_name(team_id):
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    for i in range(len(members)):
        if members[i].get('id') == str(team_id):
            return members[i].get('name')
        
    return None


def discord_to_teamid(discord_id):
    with open(current_dir/ 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    for i in range(len(members)):
        if members[i].get('discord_id') == str(discord_id):
            return members[i].get('id')
        
    return None


def discord_to_name(discord_id):
    with open(current_dir/ 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    for i in range(len(members)):
        if members[i].get('discord_id') == str(discord_id):
            return members[i].get('name')
        
    return None
    

def id_to_mention(user):
    return '<@'+str(user) + '>'


def list_to_mention(member_list):
    message = ''
    for i in range(len(member_list)):
        if i == len(member_list) - 1:
            message += id_to_mention(member_list[i])
        else:
            message += id_to_mention(member_list[i]) + ' '
    return message


def list_to_str(arg_list):
    message = ''
    for i in range(len(arg_list)):
        if i == len(arg_list) - 1:
            message += arg_list[i].capitalize()
        else:
            message += arg_list[i].capitalize() + ' '
    return message


def arg_to_int(arg):
    try:
        to_int = int(arg)
        return to_int
    except ValueError:
        print(f"{arg} is not a valid integer")
        return None


def print_list(list):
    for element in list:
        print(element)
        print('\n')


# Capitalizes words - numbers are blue
def to_red_text(text):
    modified = string.capwords(text)
    return f"```ml\n- {modified}\n```"


def to_green_text(text):
    return f"```diff\n+{text}```"


# all text blue
def to_blue_text(text):
    return f"```glsl\n{text}\n```"


def to_block(text):
    return f"```text\n{text}```"


def list_to_block(text_list):
    text = ''
    for element in text_list:
        text = text + element + '\n'
    return f"```text\n{text}```"
