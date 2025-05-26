import json
import os

from pathlib import Path
import string
from collections import deque

import csv
import asyncio

current_dir = Path(__file__).parent


EMPTY = '\u001b'

# Json file locks
private_lock = asyncio.Lock()
member_lock = asyncio.Lock()
week_dates_lock = asyncio.Lock()
transaction_lock = asyncio.Lock()
players_lock = asyncio.Lock()

# CSV file locks
players_csv_lock = asyncio.Lock()

###################################################
# load and store private.json file
###################################################
async def private_json_creator(file_path:str) -> dict:
    """Create private.json file if it does not exist.
    Args:
        file_path (str): Path to the private.json file
    Returns:
        dict: Data from private.json
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
    """
    Load discord private.json file.
        Returns:
            dict: Data from private.json
    """
    # load private.json file
    with open(current_dir / 'discordauth'/ 'private.json','r') as file:
        data = json.load(file)
    return data


def store_private_data(data:dict) -> None:
    """
    Store discord private.json file.
        Args:
            data (dict): Data to be stored in private.json
    """
    # store private.json file
    with open(current_dir / 'discordauth'/ 'private.json','w') as file:
        json.dump(data, file, indent = 4)


async def get_private_discord_data_async() -> dict:
    """
    Load discord private.json file asynchronously.
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


async def set_private_discord_data_async(data:dict) -> None:
    """
    Store discord private.json file asynchronously.
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

async def store_matchups(serialized_data:dict, filename:str):
    """
    Store serialized data to a JSON file.
        Args:
            serialized_data (dict): Data to be stored
            filename (str): Name of the file to store the data
        Returns:
            None
    """
    recap_dir = current_dir / 'recap'
    if not os.path.exists(recap_dir):
        os.makedirs(recap_dir,exist_ok=True)

    if not os.path.exists(current_dir / 'recap' / filename):
        with open(current_dir / 'recap' / filename,'w') as file:
            json.dump(serialized_data, file, indent = 2)


###################################################
# player ID          
###################################################

def load_players() -> dict:
    """
    Load player IDs from the player_ids.csv file.
        Returns:
            dict: Dictionary of yahoo names and their corresponding IDs
    """
    new_dict = {}
    with open(current_dir / 'persistent_data' / 'player_ids.csv','r') as file:
        csv_reader = csv.DictReader(file)

        for row in csv_reader:
            key = row['yahoo_name']
            value = row['yahoo_id']

            new_dict[key] = value

    return new_dict

async def load_players_async() -> dict:
    """
    Load player IDs from the player_ids.csv file.
        Returns:
            dict: Dictionary of yahoo names and their corresponding IDs
    """
    new_dict = {}
    with open(current_dir / 'persistent_data' / 'player_ids.csv','r') as file:
        csv_reader = csv.DictReader(file)

        for row in csv_reader:
            key = row['yahoo_name']
            value = row['yahoo_id']

            new_dict[key] = value

    return new_dict


async def store_players(players_dict:dict) -> None:
    filename= current_dir / 'persistent_data' / 'player_ids.csv'
    async with players_csv_lock:
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)

            writer.writerow(['yahoo_id', 'yahoo_name'])

            for player_id, name in players_dict.items():
                writer.writerow([player_id,name])


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
# Manage player_ids        
###################################################

async def store_player_ids(player_ids:dict, filename:str):
    """
        Store player_ids to the .json file.
        Args:
            players (dict): Dictionary of player_ids and player_names
        Returns:
            None
    """
    players_file = current_dir / 'persistent_data' / filename

    async with players_lock:
        with open(players_file, 'w') as file:
            json.dump(player_ids, file, indent = 4)


async def load_player_ids(filename:str) -> dict:
    """
    Load players from the .json file.
        Returns:
            dict: Dictionary of player_ids and names
    """
    player_file = current_dir / 'persistent_data' / filename

    async with players_lock:
        if os.path.exists(player_file):
            with open(player_file, 'r') as file:
                players = json.load(file)
        else:
            return {}

    return players


###################################################
# Manage Transactions        
###################################################

async def store_transactions(transactions:dict, filename:str) -> None:
    """
    Store transactions to the .json file.
        Args:
            transactions (dict): Dictionary of transactions to store
        Returns:
            None
    """
    transaction_file = current_dir / 'persistent_data' / filename

    async with transaction_lock:
        with open(transaction_file, 'w') as file:
            json.dump(transactions, file, indent = 4)


async def load_transactions(filename:str) -> dict:
    """
    Load transactions from the .json file.
        Returns:
            dict: Dictionary of transactions
    """
    transaction_file = current_dir / 'persistent_data' / filename

    async with transaction_lock:
        if os.path.exists(transaction_file):
            with open(transaction_file,'r') as file:
                transactions = json.load(file)
        else:
            return {}

    return transactions


###################################################
# Setup persistent week dates          
###################################################

async def load_dates() -> dict:
    """
    Load week dates from the week_dates.json file.
        Returns:
            dict: Dictionary of week dates - current_week:[start_date, end_date] 
    """
    date_file = current_dir / 'persistent_data' / 'week_dates.json'

    async with week_dates_lock:
        if os.path.exists(date_file):
            with open(date_file,'r') as file:
                dates_list = json.load(file)
        else:
            return {}

    return dates_list


async def store_dates(dates_dict):
    date_file = current_dir / 'persistent_data' / 'week_dates.json'

    async with week_dates_lock:
        with open(date_file, 'w') as file:
            json.dump(dates_dict, file, indent = 4)


###############################################
# create and maintain current slap challenges
###############################################

def clear_challenges():
    """Clear the challenges.json file.
        Returns:
            None
    """
    with open(current_dir/ 'persistent_data'/ 'challenges.json', 'w') as file:
        json.dump({},file)


def load_challenges():
    """Load challenges from the challenges.json file.
        Returns:
            dict: Dictionary of challenges
    """
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


def save_challenges(challenges:dict):
    """Save challenges to the challenges.json file.
        Args:
            challenges (dict): Dictionary of challenges to save
        Returns:
            None
        """
    serializable = {}
    for key, value in challenges.items():
        serializable[key] = list(value)

    with open(current_dir/ 'persistent_data'/ 'challenges.json', 'w') as file:
        json.dump(serializable, file, indent = 4)


def check_queue_exists(queue:deque, team_id:int):
    """Check if a team ID exists in a queue.
        Args:
            queue (deque): The queue to check
            team_id (int): Team ID to check for
            
        Returns:
            bool: True if the team ID exists in the queue, False otherwise
        """
    return team_id in queue


def check_exists(challenger_team_id:int, challengee_team_id:int, challenges:dict):
    """Check if a challenge exists in the challenges.json file.
        Args:
            challenger_team_id (int): Team ID of the challenger
            challengee_team_id (int): Team ID of the challengee
            
        Returns:
            bool: True if the challenge exists, False otherwise
        """
    challenger_queue = challenges.get(challenger_team_id)
    challengee_queue = challenges.get(challengee_team_id)
    
    # Check if the challenge exists in either queue
    if challenger_queue and check_queue_exists(challenger_queue, challengee_team_id):
        return True
    if challengee_queue and check_queue_exists(challengee_queue, challenger_team_id):
        return True
    
    return False


def add_challenges(challenger_team_id:int, challengee_team_id:int):
    """Add a challenge to the challenges.json file.
        Args:
            challenger_team_id (int): Team ID of the challenger
            challengee_team_id (int): Team ID of the challengee
            
        Returns:
            None
        """
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


async def append_memlist_member(member, id):
    async with member_lock:
        with open(current_dir / 'persistent_data'/ 'members.json', 'r') as read_file:
            members =json.load(read_file)

    members.append(format_member(member,id))

    with open(current_dir / 'persistent_data'/ 'members.json','w') as write_file:
        json.dump(members, write_file, indent = 4)


async def teamid_to_discord(team_id:int)-> str | None:
    """
    Convert team id to discord id.
        Args:
            team_id (int): Team id
        Returns:
            str: Discord id
    """
    async with member_lock:
        with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
            members = json.load(file)

    for i in range(len(members)):
        if members[i].get('id') == str(team_id):
            return members[i].get('discord_id')
        
    return None


async def teamid_to_name(team_id:int) -> str | None:
    """
    Convert team id to name.
        Args:
            team_id (int): Team id
        Returns:
            str: Team name
    """
    async with member_lock:
        with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
            members = json.load(file)

    for i in range(len(members)):
        if members[i].get('id') == str(team_id):
            return members[i].get('name')
        
    return None


async def discord_to_teamid(discord_id:int) -> int | None:
    '''
    Convert discord id to team id
        Args:
            discord_id (int): Discord id
        Returns:
            str: Team_id
    '''
    async with member_lock:
        with open(current_dir/ 'persistent_data'/ 'members.json', 'r') as file:
            members = json.load(file)

    for i in range(len(members)):
        if members[i].get('discord_id') == str(discord_id):
            return members[i].get('id')
        
    return None


async def discord_to_name(discord_id:int) -> str | None:
    """
    Convert discord id to name
        Args:
            discord_id (int): Discord id
        Returns:
            str: Team name
    """
    async with member_lock:
        with open(current_dir/ 'persistent_data'/ 'members.json', 'r') as file:
            members = json.load(file)

    for i in range(len(members)):
        if members[i].get('discord_id') == str(discord_id):
            return members[i].get('name')
        
    return None
    

def id_to_mention(user) -> str:
    """ 
    Convert user id to mention format.
        Args:
            user (int): User id
        Returns:
            str: User mention in the format <@user_id>
    """
    return '<@'+str(user) + '>'


def arg_to_int(arg:int | float | str | bool) -> int | None:
    """
    Convert argument to int.
        Args:
            arg (int | float | str | bool): Argument to convert
        Returns:
            int | None: Converted integer or None if conversion fails
    """
    try:
        to_int = int(arg)
        return to_int
    except ValueError:
        print(f"{arg} is not a valid integer")
        return None


# Capitalizes words - numbers are blue
def to_red_text(text):
    """
    Convert text to red capitalized text.
        Args:
            text (str): Text to convert
        Returns:
            str: Converted text in red capitalized format
    """
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
