from __future__ import annotations
from typing import Type, overload, Optional
from functools import wraps
from collections import deque
from datetime import datetime, date
from exceptions.vault_exceptions import ExpirationDateError
from file_manager import BaseFileManager
from fantasy import fantasyQuery

import logging
logger = logging.getLogger(__name__)


def validate_contract_type(registry):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            contract_type = kwargs.get('contract_type')
            if contract_type is None:
                raise ValueError('contract_type is missing.')
            if contract_type not in registry:
                raise ValueError(f'Invalid contract_type: {contract_type}')
            return await func(*args, **kwargs)
        return wrapper
    return decorator


###################################################################
# Vault
###################################################################

class Vault():

    ###################################################################
    # Contracts of different types
    ###################################################################

    class Contract():
        def __init__(self, amount:int, expiration_date:datetime, week:int, executed:bool=False, new:bool = True):
            if not isinstance(expiration_date, datetime): 
                raise TypeError('Invalid datetime input type.')
            if not isinstance(amount, int):
                raise TypeError('Expect integer for amount.')
            if amount < 0:
                raise ValueError('Contract amount cannot be negative')
       
            self._expiration = expiration_date
            self._executed = executed
            self._week = week
            self._contract_type = self.__class__.__name__         
            self._amount = amount
            self._new = new


        def __str__(self):
            return(
                f'Contract(\n'
                f'amount={self.amount}\n'
                f'expiration={self.expiration}'
                f'week={self.week}'
                f'executed={self.executed}\n'
                ')'
            )
        

        @property
        def executed(self):
            return self._executed
        

        @property
        def expiration(self):
            return self._expiration
        

        @property
        def week(self):
            return self._week
        

        @executed.setter
        def executed(self, value):
            if not isinstance(value, bool):
                raise ValueError('Boolean expected.')
            self._executed = value


        @property
        def amount(self):
            return self._amount 
               

        @property
        def winnings(self):
            raise NotImplementedError


        @property
        def contract_type(self):
            return self._contract_type
        

        @classmethod
        async def contract_from_serialized(cls, serialized_contract):
            raise NotImplementedError


        async def serialize(self):
            raise NotImplementedError


        async def should_execute(self):
            return datetime.today() > self.expiration


        async def execute_contract(self):
            raise NotImplementedError


    ###################################################################
    # SlapContract
    ###################################################################

    class SlapContract(Contract):
        def __init__(self,challenger:Vault.BankAccount, challengee:Vault.BankAccount, amount:int, expiration_date:datetime, week:int, executed:bool=False, new:bool = True):
            super().__init__(amount, expiration_date, week, executed, new)

            if not isinstance(challenger, Vault.BankAccount) or not isinstance(challengee, Vault.BankAccount):
                raise TypeError('Invalid Object type.')

            self._challenger:Vault.BankAccount = challenger
            self._challengee:Vault.BankAccount = challengee
            self._contract_type = self.__class__.__name__

            if new:
                if challenger.money < amount or challengee.money < amount:
                    raise ValueError('Not enough Funds within one of the Accounts.')
                challenger.money -= amount
                challengee.money -= amount


        @property
        def challenger(self):
            return self._challenger
        

        @property
        def challengee(self):
            return self._challengee
        

        @property
        def winnings(self):
            return self._amount * 2


        def __str__(self):
            return(
                f'SlapContract(\n'
                f'challenger={self.challenger}\n'
                f'challengee={self.challengee}\n'
                f'amount={self.amount}\n'
                f'expiration={self.expiration}'
                f'week={self.week}\n'
                f'executed={self.executed}\n'
                ')'
            )
        

        def __eq__(self, value):
            if not isinstance(value, Vault.SlapContract):
                raise TypeError(f'Expected {self.__class__.__name__}')
            return {self.challenger, self.challengee} == {value.challenger, value.challengee}


        @classmethod
        async def contract_from_serialized(cls:Type[Vault.SlapContract], serialized_contract:dict):
            challenger_dict = serialized_contract.get('challenger')
            challenger_fantasy_id = challenger_dict.get('fantasy_id')
            challenger = Vault.accounts.get(challenger_fantasy_id)

            challengee_dict = serialized_contract.get('challengee')
            challengee_fantasy_id = challengee_dict.get('fantasy_id')
            challengee = Vault.accounts.get(challengee_fantasy_id)

            expiration = datetime.fromisoformat(serialized_contract.get('expiration'))
            week = serialized_contract.get('week')
            executed = serialized_contract.get('executed') == 'True'
            amount = serialized_contract.get('amount')
            
            return cls(challenger, challengee, amount, expiration, week, executed, False)


        async def serialize(self):
            entry = {}
            entry['challenger'] = await self.challenger.serialize()
            entry['challengee'] = await self.challengee.serialize()
            entry['expiration'] = self.expiration.isoformat()
            entry['week'] = self.week
            entry['executed'] = str(self.executed)
            entry['amount'] = self._amount
            entry['type'] = str(self.contract_type)
            return entry


        async def execute_contract(self, winner:Vault.BankAccount):
            if self.executed:
                raise ValueError('Executed is True.')

            if not isinstance(winner, Vault.BankAccount):
                raise TypeError('Invalid input type.')

            if date.today() < self.expiration.date():
                raise ExpirationDateError(f'Contract Expires on {date.today()}')

            if self.challenger != winner and self.challengee != winner:
                raise ValueError(f'Invalid winner account.')
            else:
                winner.money += self.winnings
            self.executed = True


        async def refund(self):
            self.challenger.money += self.amount
            self.challengee.money += self.amount
            self.executed = True


    ###################################################################
    # GroupWagerContract
    ###################################################################

    class GroupWagerContract(Contract):
        class Prediction():
            def __init__(self, gambler:Vault.BankAccount, prediction_team:str, prediction_points:int):
                self.gambler:Vault.BankAccount = gambler
                self.prediction_team = prediction_team
                self.prediction_points = prediction_points


            @classmethod
            async def prediction_from_serialized(cls:Type[Vault.GroupWagerContract.Prediction], serialized_prediction):
                gambler_dict = serialized_prediction.get('gambler')
                gambler_fantasy_id = gambler_dict.get('fantasy_id')
                gambler = Vault.accounts.get(gambler_fantasy_id)

                prediction_team = serialized_prediction.get('prediction_team')
                prediction_points = serialized_prediction.get('prediction_points')
                return cls(gambler, prediction_team, prediction_points)


            async def serialize(self):
                entry = {}
                entry['gambler'] = await self.gambler.serialize()
                entry['prediction_team'] = self.prediction_team
                entry['prediction_points'] = self.prediction_points
                return entry


            def __str__(self):
                return(
                    f'Prediction(\n'
                    f'gambler={self.gambler}\n'
                    f'prediction_team={self.prediction_team}\n'
                    f'prediction_points={self.prediction_points}\n'
                    ')'
                )


            def __eq__(self, value):
                if not isinstance(value,Vault.GroupWagerContract.Prediction):
                    return False
                return value.gambler == self.gambler


        def __init__(
            self, team_1_id:str, team_2_id:str, 
            expiration_date:datetime, week:int, amount:int=0, executed:bool = False
        ):
            super().__init__(amount, expiration_date, week, executed)
            if not isinstance(team_1_id,str) or not isinstance(team_2_id,str):
                raise TypeError('Invalid team_id type.')
            if team_1_id == team_2_id:
                raise ValueError("Both id's must be unique.")

            self._contract_type = self.__class__.__name__
            self._team_1_id = team_1_id
            self._team_2_id = team_2_id
            self._amount:int = amount
            self._bonus:int = amount
            self._predictions_deque:deque[Vault.GroupWagerContract.Prediction] = deque()


        @property
        def team_1_id(self):
            return self._team_1_id


        @property
        def team_2_id(self):
            return self._team_2_id


        @property
        def predictions(self):
            return self._predictions_deque
        
        @property
        def bonus(self):
            return self._bonus

        @property
        def winnings(self):
            return self.amount
        

        @predictions.setter
        def predictions(self, result):
            if not isinstance(result, deque):
                raise TypeError('Prediction expects a deque.')
            self._predictions_deque = result


        def predictions_str(self):
            predict_string = '\n'.join(f'{prediction}' for prediction in self.predictions)
            return predict_string + '\n'


        def __str__(self):
            predictions = self.predictions_str()
            return(
                f'GroupWagerContract(\n'
                f'prediction={predictions}'
                f'team_1_id={self.team_1_id}\n'
                f'team_2_id={self.team_2_id}\n'
                f'amount={self.amount}\n'
                f'pot={self.winnings}'
                f'expiration={self.expiration}'
                f'week={self.week}\n'
                f'executed={self.executed}\n'
                ')'
            )


        def __eq__(self, value):
            if not isinstance(value,Vault.GroupWagerContract):
                return False
            return {value.team_1_id, value.team_2_id} == {self.team_1_id, self.team_2_id} and value.expiration == self.expiration


        async def empty(self): 
            if len(self.predictions) <= 0:
                return True
            return False


        async def found(self, id:int):
            if self._team_1_id == id or self._team_2_id == id:
                return True
            return False
        

        async def prediction_exists(self, gambler:Vault.BankAccount):
            for prediction in self.predictions:
                if prediction.gambler == gambler:
                    return True
            return False
        
        
        async def points_prediction_exists(self, team_id:str, points:int):
            for prediction in self.predictions:
                if prediction.prediction_team == team_id and prediction.prediction_points == points:
                    return True
            return False


        async def add_prediction(self, gambler:Vault.BankAccount, prediction_id:str, prediction_points:int, amount):
            if not isinstance(gambler, Vault.BankAccount):
                raise TypeError('Predictions expect type Vault.BankAccount')
            if gambler.money < amount:
                raise ValueError('Not enough Funds within the gambler account.')
            if await self.prediction_exists(gambler):
                raise ValueError('Duplicates are not allowed.')
            if await self.points_prediction_exists(team_id=prediction_id, points=prediction_points):
                raise ValueError('Point predictions must be unique per team.')
            
            new_prediction = self.Prediction(gambler=gambler, prediction_team=prediction_id, prediction_points=prediction_points)
            self.predictions.append(new_prediction)
            self._amount += amount
            gambler.money -= amount
        

        async def init_contract_deque(self, new_deque):
            if not isinstance(new_deque, deque):
                raise TypeError('init-Expected type deque.')
            self.predictions = new_deque


        @classmethod
        async def contract_from_serialized(cls:Type[Vault.GroupWagerContract], serialized_contract) -> Vault.GroupWagerContract:
            team_1_id = serialized_contract.get('team_1_id')
            team_2_id = serialized_contract.get('team_2_id')
            expiration = datetime.fromisoformat(serialized_contract.get('expiration'))
            week = serialized_contract.get('week')
            executed = serialized_contract.get('executed') == 'True'
            amount = serialized_contract.get('amount')
            contract = cls(
                team_1_id=team_1_id, 
                team_2_id=team_2_id, 
                amount=amount, 
                expiration_date=expiration, 
                week=week, 
                executed=executed
            )

            # create new deque and use that to init 
            new_deque = deque()
            serialized_predictions_list = serialized_contract.get('predictions')
            for prediction in serialized_predictions_list:
                new_prediction = await cls.Prediction.prediction_from_serialized(prediction)
                new_deque.append(new_prediction)

            await contract.init_contract_deque(new_deque)
            return contract


        async def construct_serialized_list(self):
            predictions_list = []
            for entry in self.predictions:
                serialized = await entry.serialize()
                predictions_list.append(serialized)
            return predictions_list


        async def serialize(self):
            entry = {}
            entry['predictions'] = await self.construct_serialized_list()
            entry['team_1_id'] = self.team_1_id
            entry['team_2_id'] = self.team_2_id
            entry['expiration'] = self.expiration.isoformat()
            entry['week'] = self.week
            entry['executed'] = str(self.executed)
            entry['amount'] = self._amount
            entry['type'] = str(self.contract_type)
            return entry
        

        async def account_in_deque(self, acc):
            for prediction in self.predictions:
                if acc == prediction.gambler:
                    return True   
            return False


        async def execute_contract(self, winner:Vault.BankAccount):
            if self.executed:
                raise ValueError('executed is True.')
            if not isinstance(winner, Vault.BankAccount):
                raise TypeError('Invalid input type.')

            if date.today() < self.expiration.date():
                raise ExpirationDateError(f'Contract Expires on {date.today()}')

            if not await self.account_in_deque(winner):
                raise ValueError(f'Invalid winner account.')

            winner.money += self.winnings
            self.executed = True


        async def refund(self):
            number_of_predictions = len(self.predictions)
            amount_per = (self.amount - self.bonus) / number_of_predictions
            for prediction in self.predictions:
                prediction.gambler.money += amount_per
            self.executed = True


    ###################################################################
    # BankAccount
    ###################################################################

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
        

        @name.setter
        def name(self, result):
            if not isinstance(result, str):
                raise ValueError(f'Expecting a string.')
            self._name = result


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
                raise NotImplementedError
            return self.fantasy_id == other.fantasy_id


        def __hash__(self):
            return hash(self.fantasy_id)


        @classmethod
        async def from_serialized(cls:Type[Vault.BankAccount],serialized_account:dict):
            name = serialized_account.get('name')
            discord_tag = serialized_account.get('discord_tag')
            discord_id = serialized_account.get('discord_id')
            fantasy_id = serialized_account.get('fantasy_id')
            money = serialized_account.get('money')
            return cls(name=name, discord_tag=discord_tag, discord_id=discord_id, fantasy_id=fantasy_id, money=money)


        async def serialize(self):
            entry = {}
            entry['name'] = self.name
            entry['discord_tag'] = self.discord_tag
            entry['discord_id'] = self.discord_id
            entry['fantasy_id'] = self.fantasy_id
            entry['money'] = self.money
            return entry


    ###################################################################
    # Contract utility
    ###################################################################

    CONTRACT_REGISTRY = {
        SlapContract.__name__ : SlapContract.contract_from_serialized,
        GroupWagerContract.__name__ : GroupWagerContract.contract_from_serialized,
        Contract.__name__: Contract.contract_from_serialized
    }

    # all accounts {'yahoo_fantasy_id':BankAccount}
    accounts:dict[str,BankAccount] = {}

    # all current SlapContracts
    contracts:dict[str,deque[Contract]] = {key:deque() for key,_ in CONTRACT_REGISTRY.items()}


    @classmethod
    @validate_contract_type(CONTRACT_REGISTRY)
    async def len_contracts(cls, contract_type:str) -> int:
        return len(cls.contracts.get(contract_type))


    @classmethod
    @validate_contract_type(CONTRACT_REGISTRY)
    async def ready_to_execute(cls, contract_type:str) -> bool:
        if len(cls.contracts.get(contract_type)) <= 0:
            return False

        next_contract = cls.contracts.get(contract_type)[0]
        return date.today() > next_contract.expiration.date()


    @classmethod
    @validate_contract_type(CONTRACT_REGISTRY)
    async def get_next_contract(cls, contract_type):
        return cls.contracts.get(contract_type)[0]


    @classmethod
    @validate_contract_type(CONTRACT_REGISTRY)
    async def pop_contract(cls, contract_type):
        return cls.contracts.get(contract_type).popleft()


    @classmethod
    @validate_contract_type(CONTRACT_REGISTRY)
    async def get_contract_deque(cls, contract_type):
        return cls.contracts.get(contract_type)


    @classmethod
    @validate_contract_type(CONTRACT_REGISTRY)
    async def serialize_contracts(cls, contract_type):
        contract_list = []
        for element in cls.contracts.get(contract_type):
            contract = await element.serialize()
            contract_list.append(contract)
        return contract_list


    ###################################################################
    # Slaps specific
    ###################################################################

    @staticmethod
    async def create_slap_contract(challenger_fantasy_id:str, challengee_fantasy_id:str, amount:int, expiration_date:datetime, week:int):
        challenger = __class__.accounts.get(challenger_fantasy_id)
        challengee = __class__.accounts.get(challengee_fantasy_id)
        return Vault.SlapContract(challenger,challengee, amount,expiration_date, week)


    ###################################################################
    # Wagers specific
    ###################################################################

    @staticmethod
    async def create_wager_contract(team_1_id:str, team_2_id:str, expiration_date:datetime, week:int, amount:int=0, executed:bool=False):
        return Vault.GroupWagerContract(team_1_id=team_1_id, team_2_id=team_2_id, expiration_date=expiration_date, week=week, amount=amount, executed=False)


    @classmethod
    async def wager_exists(cls, contract:Vault.GroupWagerContract):
        for entry in cls.contracts.get(Vault.GroupWagerContract.__name__):
            if entry == contract:
                return True
        return False


    @classmethod
    async def wager_by_id_exists(cls, id:str) -> bool:
        for entry in cls.contracts.get(Vault.GroupWagerContract.__name__):
            if await entry.found(id=id):
                return True
        return False
    

    @classmethod
    async def get_wager(cls, fantasy_id:str) -> Vault.GroupWagerContract:
        for entry in cls.contracts.get(Vault.GroupWagerContract.__name__):
            if await entry.found(id=fantasy_id):
                return entry
        return None


    @classmethod
    async def get_all_wagers(cls) -> list[Vault.GroupWagerContract]:
        return cls.contracts.get(Vault.GroupWagerContract.__name__).copy()


    ###################################################################
    # Create Contract Interface
    ###################################################################

    @overload
    @classmethod
    async def create_contract(cls, challenger_fantasy_id:str, challengee_fantasy_id:str, amount:int, expiration_date:datetime, week:int, contract_type:str): ...


    @overload
    @classmethod
    async def create_contract(cls, team_1_id:str, team_2_id:str, expiration_date:datetime, week:int, amount:int, contract_type:str, executed:bool=False): ...


    @classmethod
    @validate_contract_type(CONTRACT_REGISTRY)
    async def create_contract(cls, *args, **kwargs):
        contract_type = kwargs.pop('contract_type')

        if contract_type == Vault.SlapContract.__name__:
            contract = await cls.create_slap_contract(**kwargs)
            cls.contracts.get(Vault.SlapContract.__name__).append(contract)
        elif contract_type == Vault.GroupWagerContract.__name__:
            contract = await cls.create_wager_contract(**kwargs)
            if not await cls.wager_exists(contract=contract):
                cls.contracts.get(Vault.GroupWagerContract.__name__).append(contract)
        else:
            return None
        return contract

    ###################################################################
    # BankAccount utility
    ###################################################################

    @classmethod
    async def serialize_accounts(cls):
        account_list = []
        for key, value in cls.accounts.items():
            account = await value.serialize()
            account_list.append(account)
        return account_list


    @classmethod
    async def fantasy_id_by_discord_id(cls, discord_id) -> str:
        for key, value in cls.accounts.items():
            if value.discord_id == discord_id:
                return key
        return None


    @classmethod
    async def bank_account_info_by_discord_id(cls, discord_id) -> Optional[str]:
        for key, value in cls.accounts.items():
            if value.discord_id == discord_id:
                return str(value)
        return None


    @classmethod
    async def bank_account_by_discord_id(cls, discord_id) -> Vault.BankAccount:
        for key, value in cls.accounts.items():
            if value.discord_id == discord_id:
                return value
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

    
    ###################################################################
    # Maintain contracts
    ###################################################################

    @classmethod
    async def initialize(cls, accounts: dict[str, BankAccount] = None, slap_contracts: deque[SlapContract] = None, wager_contracts: deque[GroupWagerContract] = None):
        if accounts is not None:
            if not isinstance(accounts, dict):
                raise TypeError("Expected a dict of accounts.")

            for key, value in accounts.items():
                if not isinstance(key, str) or not isinstance(value, Vault.BankAccount):
                    raise TypeError("Accounts must be of type dict[str, BankAccount]")
                
        if slap_contracts is not None:
            if not isinstance(slap_contracts,deque) :
                raise TypeError(f"Expected deque of {Vault.SlapContract.__name__}")

            for elements in slap_contracts:
                if not isinstance(elements,Vault.SlapContract):
                    raise TypeError(f"Contracts must be of type {Vault.SlapContract.__name__}")
            
        if wager_contracts is not None:
            if not isinstance(wager_contracts,Vault.GroupWagerContract):
                raise ValueError(f"Expected deque of {Vault.GroupWagerContract.__name__}")
            for elements in wager_contracts:
                if not isinstance(elements,Vault.GroupWagerContract):
                    raise TypeError(f"Contracts must be of type {Vault.GroupWagerContract.__name__}")
            
        cls.accounts = accounts or {}
        cls.contracts[Vault.SlapContract.__name__] = slap_contracts or deque()
        cls.contracts[Vault.GroupWagerContract.__name__] = wager_contracts or deque()


    @staticmethod
    async def accounts_from_serialized(accounts:list[dict]):
        accounts_dict = {}
        for entry in accounts:
            new_account = await Vault.BankAccount.from_serialized(entry)
            accounts_dict[new_account.fantasy_id] = new_account
        __class__.accounts = accounts_dict


    @staticmethod
    async def contracts_from_serialized(contracts:list[dict]):
        for entry in contracts:
            try:
                contract_type = entry.get('type')
                new_contract = await __class__.CONTRACT_REGISTRY.get(contract_type)(entry)
            except Exception as e:
                logger.error(f'[Vault][deserialize_contracts] - Error: {e}')
                return

            contract_deque =__class__.contracts.get(contract_type)
            contract_deque.append(new_contract)


    @classmethod
    async def initialize_from_serialized(cls, accounts:list[dict] = None, slap_contracts:list[dict] = None, wager_contracts:list[dict] = None):
        if accounts is not None:
            await cls.accounts_from_serialized(accounts)
        if slap_contracts is not None:
            await cls.contracts_from_serialized(slap_contracts)
        if wager_contracts is not None:
            await cls.contracts_from_serialized(wager_contracts)

