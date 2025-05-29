import json
import os

from pathlib import Path
import string
from collections import deque

import csv
import asyncio

current_dir = Path(__file__).parent


EMPTY = '\u001b'
_member_filename = 'members.json'


def compose_player_key(game_key, player_id):
    return f'{game_key}.p.{player_id}'


def format_member(member,id):
    new_mem = {str(member): str(id)}
    return new_mem


async def teamid_to_discord(team_id:int, file_manager):
    members = await file_manager.load_json(filename=_member_filename)

    for member in members:
        if member.get('id') == str(team_id):
            return member.get('discord_id')
    return None


async def teamid_to_name(team_id:int, file_manager) -> str | None:
    """
    Convert team id to name.
        Args:
            team_id (int): Team id
        Returns:
            str: Team name
    """
    members = await file_manager.load_json(filename=_member_filename)

    for member in members:
        if member.get('id') == str(team_id):
            return member.get('name')
    return None


async def discord_to_teamid(discord_id:int, file_manager) -> int | None:
    '''
    Convert discord id to team id
        Args:
            discord_id (int): Discord id
        Returns:
            str: Team_id
    '''
    members = await file_manager.load_json(filename=_member_filename)

    for member in members:
        if member.get('discord_id') == str(discord_id):
            return member.get('id')
    return None


async def discord_to_name(discord_id:int, file_manager) -> str | None:
    """
    Convert discord id to name
        Args:
            discord_id (int): Discord id
        Returns:
            str: Team name
    """
    members = await file_manager.load_json(filename=_member_filename)

    for member in members:
        if member.get('discord_id') == str(discord_id):
            return member.get('name')
        
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


def ensure_str(data):
    if isinstance(data, bytes):
        return data.decode('utf-8')
    return data