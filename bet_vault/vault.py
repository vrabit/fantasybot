from __future__ import annotations
from collections import deque
from datetime import datetime
from exceptions.vault_exceptions import ExpirationDateError
from file_manager import BaseFileManager

class Vault():

    class Contract():
        def __init__(self, challenger:Vault.BankAccount, challengee:Vault.BankAccount, amount:int, expiration_date:datetime):
            self._challenger:Vault.BankAccount = challenger
            self._challengee:Vault.BankAccount = challengee
            self._expiration = expiration_date
            self._executed = False

            if not isinstance(challenger, Vault.BankAccount) or not isinstance(challengee, Vault.BankAccount):
                raise TypeError('Invalid Object type.')
            if not isinstance(expiration_date, datetime): 
                raise TypeError('Invalid input type.')
            if not isinstance(amount, int):
                raise TypeError('Expect integer for amount.')
            if amount < 0:
                raise ValueError('Contract amount cannot be negative')
            if challenger.money < amount or challengee.money < amount:
                raise ValueError('Not enough Funds within one of the Accounts.')
            
            challenger.money -= amount
            challengee.money -= amount
            self._amount = amount * 2

        def __str__(self):
            return(
                f'Contract(\n'
                f'challenger={self.challenger}\n'
                f'challengee={self.challengee}\n'
                f'amount={self.amount}\n'
                f'executed={self.executed}\n'
                ')'
            )

        @property
        def challenger(self):
            return self._challenger
        
        @property
        def challengee(self):
            return self._challengee
        
        @property
        def executed(self):
            return self._executed
        
        @property
        def expiration(self):
            return self._expiration
        
        @executed.setter
        def executed(self, value):
            if not isinstance(value, bool):
                raise ValueError('Boolean expected.')
            self._executed = value

        @property
        def amount(self):
            return self._amount

        async def execute_contract(self, winner:Vault.BankAccount):
            if not isinstance(winner, Vault.BankAccount):
                raise TypeError('Invalid input type.')

            if datetime.today() < self.expiration:
                raise ExpirationDateError(f'Contract Expires on {datetime.today()}')

            if self.challenger != winner and self.challengee != winner:
                raise ValueError(f'Invalid winner account.')
            else:
                winner.money += self.amount
            self.executed = True
    

    class BankAccount():
        def __init__(self, name:str, discord_tag:str, discord_id:str, fantasy_id:str, money:int):
            self._name:str = name
            self._discord_tag:str = discord_tag
            self._discord_id:str = discord_id
            self._fantasy_id:int = fantasy_id
            self._money:int = money

        @property
        def name(self) -> str:
            return self._name

        @property
        def discord_tag(self) -> str:
            return self._discord_tag
        
        @property
        def discord_id(self) -> str:
            return self._discord_id

        @property
        def fantasy_id(self) -> str:
            return self._fantasy_id

        @property
        def money(self) -> int:
            return self._money
        
        @money.setter
        def money(self, result):
            if result < 0:
                raise ValueError(f'Balance cannot be negative.')
            self._money = result

        def __str__(self):
            return ( 
                f'BankAccount(\n'
                f"discord_tag='{self._discord_tag}', \n"
                f"discord_id='{self._discord_id}', \n"
                f'fantasy_id={self._fantasy_id}, \n'
                f'money={self._money}\n'
                ')'
            )

        def __eq__(self, other):
            if not isinstance(other, Vault.BankAccount):
                return NotImplemented
            
            return self.fantasy_id == other.fantasy_id

    # filemanager
    _file_manager = None
    _accounts_filename = None
    _contracts_filename = None

    # all accounts {'yahoo_fantasy_id':BankAccount}
    accounts:dict[str,BankAccount] = {}
    accounts_filename = 'vault_accounts.json'

    # all current contracts
    contracts:deque[Contract] = deque()
    contracts_filename = 'vault_contracts.json'

    @classmethod
    async def fantasy_id_by_discord_id(cls, discord_id):
        for key, value in cls.accounts.items():
            if value.discord_id == discord_id:
                return key
        return None

    @classmethod
    async def bank_account_info_by_discord_id(cls, discord_id):
        for key, value in cls.accounts.items():
            if value.discord_id == discord_id:
                return str(value)
        return None

    @classmethod
    async def transfer_money(cls,from_fantasy_id:str, to_fantasy_id:str, amount:int):
        send_account = cls.accounts.get(from_fantasy_id)
        receive_account= cls.accounts.get(to_fantasy_id)

        if not isinstance(amount, int) or not isinstance(from_fantasy_id,str) or not isinstance(to_fantasy_id,str):
            raise TypeError(f'Expecting an integer for amount.')
        if not send_account or not receive_account:
            raise ValueError(f'Account not found.')
        if send_account.money < amount:
            raise ValueError(f'Insufficient funds. Current Balance{send_account.money}')
        
        send_account.money -= amount
        receive_account.money += amount
        await cls.store_accounts(cls.accounts, file_manager = cls._file_manager, filename=cls._accounts_filename)


    @classmethod
    async def deduct_money(cls,fantasy_id:str, amount:int):
        account = cls.accounts.get(fantasy_id)

        if not isinstance(amount, int) or not isinstance(fantasy_id,str):
            raise TypeError(f'Invalid entry types.')
        if amount < 0:
            raise ValueError(f'Amount cannot be negative.')
        if not account:
            raise ValueError(f'Account not found.')
        if account.money < amount:
            raise ValueError(f'Insufficient funds. Current Balance {account.money}')

        account.money -= amount
        await cls.store_accounts(cls.accounts, file_manager = cls._file_manager, filename=cls._accounts_filename)

    @classmethod
    async def add_money(cls, fantasy_id:str, amount:int):
        account = cls.accounts.get(fantasy_id)

        if not isinstance(amount, int) or not isinstance(fantasy_id,str):
            raise TypeError(f'Invalid entry types.')
        if amount < 0:
            raise ValueError(f'Amount cannot be negative.')
        if not account:
            raise ValueError(f'Account {fantasy_id} not found.')
        account.money += amount
        await cls.store_accounts(cls.accounts, file_manager = cls._file_manager, filename=cls._accounts_filename)


    @classmethod
    async def new_account(cls, fantasy_id, account:BankAccount):
        if fantasy_id not in cls.accounts:
            cls.accounts[fantasy_id] = account

    
    @classmethod
    async def add_contract(cls, account1:Vault.BankAccount, account2:Vault.BankAccount, amount:int, expiration:datetime):
        contract = Vault.Contract(account1,account2,amount,expiration)
        cls.contracts.append(contract)


    @staticmethod
    async def store_contracts(contracts:deque[Contract], file_manager, filename):
        output = []
        for contract in contracts:
            entry = {}
            entry['challenger'] = contract.challenger
            entry['challengee'] = contract.challengee
            entry['expiration'] = contract.expiration
            entry['executed'] = str(contract.executed)
            entry['amount'] = contract.amount
            output.append(entry)
        await file_manager.write_json(filename = filename, data=output)


    @staticmethod
    async def store_accounts(accounts:dict[str,BankAccount], file_manager, filename):
        output = {}
        for key, value in accounts.items():
            entry = {}
            entry['name'] = value.name
            entry['discord_tag'] = value.discord_tag
            entry['discord_id'] = value.discord_id
            entry['fantasy_id'] = value.fantasy_id
            entry['money'] = value.money
            output[key] = entry
        await file_manager.write_json(filename = filename, data = output)


    @classmethod
    async def store_all(cls):
        await cls.store_contracts(cls.contracts, cls._file_manager, cls.contracts_filename)
        await cls.store_accounts(cls.accounts, cls._file_manager, cls.accounts_filename)


    @classmethod
    async def initialize(cls, file_manager, contracts_filename, accounts_filename, accounts: dict[str, BankAccount], contracts: deque[Contract]):
        cls._file_manager = file_manager
        cls._contracts_filename = contracts_filename
        cls._accounts_filename = accounts_filename
        
        if not isinstance(file_manager, BaseFileManager):
            raise TypeError('Improper file_manager type')

        if not isinstance(accounts, dict):
            raise TypeError("Expected a dict of accounts.")

        # Optionally check the contents
        for key, value in accounts.items():
            if not isinstance(key, str) or not isinstance(value, Vault.BankAccount):
                raise TypeError("accounts must be of type dict[str, BankAccount]")
            
        if not isinstance(contracts,deque):
            raise TypeError("Expected deque of Contract")

        for elements in contracts:
            if not isinstance(elements,Vault.Contract):
                raise TypeError("contracts must be of type Vault.Contract")

        cls.accounts = accounts
        cls.contracts = contracts
