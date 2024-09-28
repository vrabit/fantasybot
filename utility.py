import json
import os

from pathlib import Path
import string

import csv

current_dir = Path(__file__).parent

def load_players():

    new_dict = {}
    with open(current_dir / 'yfpyauth'/ 'player_ids.csv','r') as file:
        csv_reader = csv.DictReader(file)

        for row in csv_reader:
            key = row['yahoo_name']
            value = row['yahoo_id']

            new_dict[key] = value

    return new_dict

def load_members():
    with open(current_dir / 'persistent_data'/ 'members.json', 'r') as file:
        members = json.load(file)

    return members

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

def bind_discord( draft_id, discord_id):
    
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


# Capitalizes words - numbers are blue
def to_red_text(text):
    modified = string.capwords(text)
    return f"```ml\n- {modified}\n```"

# all text blue
def to_blue_text(text):
    return f"```glsl\n{text}\n```"

def to_block(text):
    return f"```text\n{text}```"