import asyncio
import json
import aiofiles
import csv
import io
import pickle
import pandas as pd
from typing import Optional


from pathlib import Path
from functools import wraps

import logging
logger = logging.getLogger(__name__)

current_dir = Path(__file__).parent


def async_load_error_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f'[FileManager] - Error in {func.__name__}: {e}')
            return {}
    return wrapper


def async_load_pickle_error_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f'[FileManager] - Error in {func.__name__}: {e}')
            return None
    return wrapper


class BaseFileManager:
    def __init__(self, folder_name:str):
        self._base = Path(__file__).parent
        self._path = self._base / folder_name
        self._locks = {}

    def _get_raw_path(self) -> Path:
        return self._path

    def _get_path(self, filename: str) -> Path:
        return self._path / filename
    

    def _get_lock(self, filename: str) -> asyncio.Lock:
        if filename not in self._locks:
            self._locks[filename] = asyncio.Lock()
        return self._locks[filename]
    
    @async_load_error_handler
    async def load_json(self, filename: str) -> dict:
        lock = self._get_lock(filename)
        path = self._get_path(filename)
        async with lock:
            if not path.exists():
                return {}
            async with aiofiles.open(path, 'r') as file:
                return json.loads(await file.read())


    async def write_json(self, filename: str, data: dict) -> None:
        raw_path = self._get_raw_path()
        lock = self._get_lock(filename)
        path = self._get_path(filename)

        raw_path.mkdir(parents=True, exist_ok=True) # Make sure the directory exists

        async with lock:
            async with aiofiles.open(path, 'w') as file:
                await file.write(json.dumps(data, indent=4))


    @async_load_error_handler
    async def load_simple_csv(self, filename: str, fieldnames: list[str] = ['yahoo_id', 'yahoo_name']) -> dict:
        raw_path = self._get_raw_path()
        lock = self._get_lock(filename)
        path = self._get_path(filename)

        raw_path.mkdir(parents=True, exist_ok=True) # Make sure the directory exists

        async with lock:
            if not path.exists():
                return {}
            
            async with aiofiles.open(path, 'r', newline='') as file:
                content = await file.read()
            
            buffer = io.StringIO(content)
            reader = csv.DictReader(buffer)

            return {row[fieldnames[1]]: row[fieldnames[0]] for row in reader if fieldnames[0] in row and fieldnames[1] in row}


    async def write_simple_csv(self, filename: str, data: dict, fieldnames: list[str] = ['yahoo_id', 'yahoo_name']) -> None:
        raw_path = self._get_raw_path()
        lock = self._get_lock(filename)
        path = self._get_path(filename)

        raw_path.mkdir(parents=True, exist_ok=True) # Make sure the directory exists

        async with lock:
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(fieldnames)

            for player_id, player_name in data.items():
                writer.writerow([player_id, player_name])

            async with aiofiles.open(path, 'w', newline='') as file:
                await file.write(buffer.getvalue())


    async def load_csv_formatted(self, filename: str) -> Optional[pd.DataFrame]:
        raw_path = self._get_raw_path()
        lock = self._get_lock(filename)
        thread_lock = self._get_lock('to_thread')
        path = self._get_path(filename)

        raw_path.mkdir(parents=True, exist_ok=True) # Make sure the directory exists

        async with lock:
            async with thread_lock:
                try:
                    data = await asyncio.to_thread(pd.read_csv, path)
                    return data
                except FileNotFoundError:
                    return None


    async def write_csv_formatted(self, filename: str, dataframe: pd.DataFrame) -> None:
        raw_path = self._get_raw_path()
        lock = self._get_lock(filename)
        thread_lock = self._get_lock('to_thread')
        path = self._get_path(filename)

        raw_path.mkdir(parents=True, exist_ok=True) # Make sure the directory exists

        async with lock:
            async with thread_lock:
                await asyncio.to_thread(dataframe.to_csv, path, index=False, encoding='utf-8')


    async def path_exists(self, filename: str) -> bool:
        path = self._get_path(filename)

        if path.exists():
            return True
        else:
            return False


    async def save_fig(self, fig, filepath):
        pass


    async def load_dataframe(self, filepath):
        pass


    async def save_gif(self, folder_path, filename, fps):
        pass


class PersistentManager(BaseFileManager):
    def __init__(self):
        super().__init__('persistent_data')  

class RecapManager(BaseFileManager):
    def __init__(self):
        super().__init__('recap')

class DiscordAuthManager(BaseFileManager):
    def __init__(self):
        super().__init__('discordauth')

class LiveManager(BaseFileManager):
    def __init__(self):
        super().__init__('live_data')

class SettingsManager(BaseFileManager):
    def __init__(self):
        super().__init__('settings')

class TestingManager(BaseFileManager):
    def __init__(self):
        super().__init__('testing_output')

class VaultManager(BaseFileManager):
    def __init__(self):
        super().__init__('bet_vault_persistent')

    async def write_pickle(self, filename, data) -> None:
        raw_path = self._get_raw_path()
        lock = self._get_lock(filename)
        thread_lock = self._get_lock('to_thread')
        path = self._get_path(filename)

        raw_path.mkdir(parents=True, exist_ok=True) # Make sure the directory exists

        async with lock:
            async with thread_lock:
                with open(path, 'wb') as file:
                    await asyncio.to_thread(pickle.dump, data, file)

    @async_load_pickle_error_handler
    async def load_pickle(self, filename):
        lock = self._get_lock(filename)
        thread_lock = self._get_lock('to_thread')
        path = self._get_path(filename)

        async with lock:
            if not path.exists():
                return None
            async with thread_lock:
                with open(path, 'rb') as file:
                    return await asyncio.to_thread(pickle.load, file)
                
