import pytest
from datetime import datetime, timedelta, date
from collections import deque
from exceptions.vault_exceptions import ExpirationDateError

from bet_vault.vault import Vault


#############################################################################
# fixtures
#############################################################################

@pytest.fixture(autouse=True)
def fresh_vault():
    Vault.accounts.clear()
    for _, value in Vault.contracts.items():
        value.clear()


@pytest.fixture
def setup_accounts():
    account1 = Vault.BankAccount('banana','<@59729789855555555>','59729789855555555', '3', 100)
    account2 = Vault.BankAccount('pesado','<@59729789855555555>','59729789855555555', '4', 100)
    Vault.accounts['3'] = account1
    Vault.accounts['4'] = account2
    return account1, account2

@pytest.fixture
def setup_three_accounts():
    account1 = Vault.BankAccount(name='banana', discord_tag='<@59729789855555555>', discord_id='59729789855555555', fantasy_id='3', money=100)
    account2 = Vault.BankAccount(name='pesado', discord_tag='<@95444595755555555>', discord_id='95444595755555555', fantasy_id='4', money=100)
    account3 = Vault.BankAccount(name='taco', discord_tag='<@95648312555555555>', discord_id='95648312555555555', fantasy_id='5', money=100)
    Vault.accounts['3'] = account1
    Vault.accounts['4'] = account2
    Vault.accounts['5'] = account3
    return account1, account2, account3


@pytest.fixture 
async def setup_vault_accounts():
    accounts_dict = {}
    contracts_deque = deque()
    account1 = Vault.BankAccount(name='banana', discord_tag='<@59729789855555555>', discord_id='59729789855555555', fantasy_id='3', money=100)
    account2 = Vault.BankAccount(name='pesado', discord_tag='<@95444595755555555>', discord_id='95444595755555555', fantasy_id='4', money=100)
    account3 = Vault.BankAccount(name='taco', discord_tag='<@95648312555555555>', discord_id='95648312555555555', fantasy_id='5', money=100)
    accounts_dict[account1.fantasy_id] = account1
    accounts_dict[account2.fantasy_id] = account2
    accounts_dict[account3.fantasy_id] = account3

    await Vault.initialize(accounts_dict, contracts_deque)

@pytest.fixture 
async def setup_vault_accounts_and_slap_contracts():
    accounts_dict = {}
    contracts_deque = deque()
    account1 = Vault.BankAccount(name='banana', discord_tag='<@59729789855555555>', discord_id='59729789855555555', fantasy_id='3', money=100)
    account2 = Vault.BankAccount(name='pesado', discord_tag='<@95444595755555555>', discord_id='95444595755555555', fantasy_id='4', money=100)
    account3 = Vault.BankAccount(name='taco', discord_tag='<@95648312555555555>', discord_id='95648312555555555', fantasy_id='5', money=100)
    accounts_dict[account1.fantasy_id] = account1
    accounts_dict[account2.fantasy_id] = account2
    accounts_dict[account3.fantasy_id] = account3

    await Vault.initialize(accounts_dict, contracts_deque)

    yesterday = datetime.today() - timedelta(days = 1)
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account2.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account3.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )      

@pytest.fixture 
async def setup_vault_accounts_and_wager_contracts():
    accounts_dict = {}
    account1 = Vault.BankAccount(name='banana', discord_tag='<@59729789855555555>', discord_id='59729789855555555', fantasy_id='3', money=100)
    account2 = Vault.BankAccount(name='pesado', discord_tag='<@95444595755555555>', discord_id='95444595755555555', fantasy_id='4', money=100)
    account3 = Vault.BankAccount(name='taco', discord_tag='<@95648312555555555>', discord_id='95648312555555555', fantasy_id='5', money=100)
    accounts_dict[account1.fantasy_id] = account1
    accounts_dict[account2.fantasy_id] = account2
    accounts_dict[account3.fantasy_id] = account3

    await Vault.initialize(accounts_dict)

    yesterday = datetime.today() - timedelta(days = 1)
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')

    # slaps
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account2.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account3.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )   

    # wagers
    await Vault.create_contract(team_1_id='1', team_2_id='2', expiration_date=yesterday, week=5, contract_type=Vault.GroupWagerContract.__name__)
    await Vault.create_contract(team_1_id='3', team_2_id='4', expiration_date=yesterday, week=5, contract_type=Vault.GroupWagerContract.__name__)
    await Vault.create_contract(team_1_id='5', team_2_id='6', expiration_date=yesterday, week=5, contract_type=Vault.GroupWagerContract.__name__)

@pytest.fixture 
async def setup_vault_accounts_and_wager_contracts_with_predictions():
    accounts_dict = {}
    account1 = Vault.BankAccount(name='banana', discord_tag='<@59729789855555555>', discord_id='59729789855555555', fantasy_id='3', money=100)
    account2 = Vault.BankAccount(name='pesado', discord_tag='<@95444595755555555>', discord_id='95444595755555555', fantasy_id='4', money=100)
    account3 = Vault.BankAccount(name='taco', discord_tag='<@95648312555555555>', discord_id='95648312555555555', fantasy_id='5', money=100)
    accounts_dict[account1.fantasy_id] = account1
    accounts_dict[account2.fantasy_id] = account2
    accounts_dict[account3.fantasy_id] = account3

    await Vault.initialize(accounts_dict)

    yesterday = datetime.today() - timedelta(days = 1)
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')

    # slaps
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account2.fantasy_id, 
        amount = 10, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account3.fantasy_id, 
        amount = 10, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )   

    # wagers
    wager_1:Vault.GroupWagerContract = await Vault.create_contract(team_1_id='1', team_2_id='2', expiration_date=yesterday, week=5, contract_type=Vault.GroupWagerContract.__name__)
    wager_2:Vault.GroupWagerContract  = await Vault.create_contract(team_1_id='3', team_2_id='4', expiration_date=yesterday, week=5, contract_type=Vault.GroupWagerContract.__name__)
    wager_3:Vault.GroupWagerContract  = await Vault.create_contract(team_1_id='5', team_2_id='6', expiration_date=yesterday, week=5, contract_type=Vault.GroupWagerContract.__name__)

    await wager_1.add_prediction(gambler= account1, prediction_id='1', prediction_points=60, amount=10)
    await wager_1.add_prediction(gambler= account2, prediction_id='2', prediction_points=65, amount=10)
    await wager_1.add_prediction(gambler= account3, prediction_id='1', prediction_points=55, amount=10)

    await wager_2.add_prediction(gambler=account1, prediction_id='3', prediction_points=40, amount=10)
    await wager_2.add_prediction(gambler=account2, prediction_id='4', prediction_points=30, amount=10)
    await wager_2.add_prediction(gambler=account3, prediction_id='3', prediction_points=48, amount=10)

    await wager_3.add_prediction(gambler=account1, prediction_id='6', prediction_points=40, amount=10)
    await wager_3.add_prediction(gambler=account2, prediction_id='5', prediction_points=30, amount=10)
    await wager_3.add_prediction(gambler=account3, prediction_id='5', prediction_points=48, amount=10)


@pytest.fixture 
async def setup_vault_accounts_and_wager_contracts_with_bonus_and_predictions():
    accounts_dict = {}
    account1 = Vault.BankAccount(name='banana', discord_tag='<@59729789855555555>', discord_id='59729789855555555', fantasy_id='3', money=100)
    account2 = Vault.BankAccount(name='pesado', discord_tag='<@95444595755555555>', discord_id='95444595755555555', fantasy_id='4', money=100)
    account3 = Vault.BankAccount(name='taco', discord_tag='<@95648312555555555>', discord_id='95648312555555555', fantasy_id='5', money=100)
    accounts_dict[account1.fantasy_id] = account1
    accounts_dict[account2.fantasy_id] = account2
    accounts_dict[account3.fantasy_id] = account3

    await Vault.initialize(accounts_dict)

    yesterday = datetime.today() - timedelta(days = 1)
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')

    # slaps
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account2.fantasy_id, 
        amount = 10, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account3.fantasy_id, 
        amount = 10, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )   

    # wagers
    wager_1:Vault.GroupWagerContract = await Vault.create_contract(team_1_id='1', team_2_id='2', expiration_date=yesterday, week=5, amount=10, contract_type=Vault.GroupWagerContract.__name__)
    wager_2:Vault.GroupWagerContract  = await Vault.create_contract(team_1_id='3', team_2_id='4', expiration_date=yesterday, week=5, amount=10, contract_type=Vault.GroupWagerContract.__name__)
    wager_3:Vault.GroupWagerContract  = await Vault.create_contract(team_1_id='5', team_2_id='6', expiration_date=yesterday, week=5, amount=10, contract_type=Vault.GroupWagerContract.__name__)

    await wager_1.add_prediction(gambler= account1, prediction_id='1', prediction_points=60, amount=10)
    await wager_1.add_prediction(gambler= account2, prediction_id='2', prediction_points=65, amount=10)
    await wager_1.add_prediction(gambler= account3, prediction_id='1', prediction_points=55, amount=10)

    await wager_2.add_prediction(gambler=account1, prediction_id='3', prediction_points=40, amount=10)
    await wager_2.add_prediction(gambler=account2, prediction_id='4', prediction_points=30, amount=10)
    await wager_2.add_prediction(gambler=account3, prediction_id='3', prediction_points=48, amount=10)

    await wager_3.add_prediction(gambler=account1, prediction_id='6', prediction_points=40, amount=10)
    await wager_3.add_prediction(gambler=account2, prediction_id='5', prediction_points=30, amount=10)
    await wager_3.add_prediction(gambler=account3, prediction_id='5', prediction_points=48, amount=10)


#############################################################################
# bank_account tests
#############################################################################

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_vault_initialization():
    account = Vault.BankAccount('banana','<@59729789855555555>','59729789855555555', '3', 100)
    assert account.name == 'banana'
    assert account.fantasy_id == '3'
    assert account.money == 100
    assert account.discord_tag == '<@59729789855555555>'
    assert account.discord_id == '59729789855555555'

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_transfer_money(setup_accounts):
    acc1, acc2 = setup_accounts
    await Vault.transfer_money("3", "4", 50)
    assert acc1.money == 50
    assert acc2.money == 150

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_transfer_money_bad_input(setup_accounts):
    acc1, acc2 = setup_accounts
    with pytest.raises(TypeError):
        await Vault.transfer_money(3, "4", 50)
    with pytest.raises(TypeError):
        await Vault.transfer_money('3', 4, 50)
    with pytest.raises(TypeError):
        await Vault.transfer_money('3', '4', '50')
    with pytest.raises(TypeError):
        await Vault.transfer_money(3, 4, '50')

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_add_money_success(setup_accounts):
    account, _ = setup_accounts
    await Vault.add_money('3',50)
    assert account.money == 150
    
@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_add_money_negative(setup_accounts):
    _, account = setup_accounts
    with pytest.raises(ValueError):
        await Vault.add_money('4',-50)
    
@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_add_money_id_fail():
    with pytest.raises(ValueError):
        await Vault.add_money('6',10)

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_add_money_bad_input(setup_accounts):
    account1, account2 = setup_accounts
    with pytest.raises(TypeError):
        await Vault.add_money(3,50)
    with pytest.raises(TypeError):
        await Vault.add_money(3,'50')
    with pytest.raises(TypeError):
        await Vault.add_money('3','50')

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_deduct_money_success(setup_accounts):
    account, _= setup_accounts
    await Vault.deduct_money('3',50)
    assert account.money == 50
    await Vault.deduct_money('3',50)
    assert account.money == 0 

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_deduct_money_negative(setup_accounts):
    account, _= setup_accounts
    with pytest.raises(ValueError):
        await Vault.deduct_money('3', -50)

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_deduct_money_id_fail():
    with pytest.raises(ValueError):
        await Vault.deduct_money('6', 50)

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_deduct_money_balance_fail(setup_accounts):
    account, _= setup_accounts
    with pytest.raises(ValueError):
        await Vault.deduct_money('3', 150)

@pytest.mark.asyncio
@pytest.mark.bank_account
async def test_deduct_money_bad_input(setup_accounts):
    account1, account2 = setup_accounts
    with pytest.raises(TypeError):
        await Vault.deduct_money(3,50)
    with pytest.raises(TypeError):
        await Vault.deduct_money(3,'50')
    with pytest.raises(TypeError):
        await Vault.deduct_money('3','50')


#############################################################################
# contract
#############################################################################

@pytest.mark.asyncio
@pytest.mark.contract
async def test_contract_initialization():
    date_today = datetime.today()
    contract = Vault.Contract(amount=100, expiration_date=date_today, week=4)

    assert contract.expiration.date() == date.today()    
    assert contract.executed == False
    assert contract.week == 4
    assert contract.contract_type == 'Contract'
    assert contract.amount == 100 
    assert contract._new == True


#############################################################################
# slap_contract
#############################################################################

@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_slap_contract_initialization(setup_accounts):
    account1, account2 = setup_accounts
    date_today = datetime.today()
    contract = Vault.SlapContract(challenger=account1, challengee=account2, amount = 100, expiration_date=date_today, week=4)

    assert contract.challenger == account1
    assert contract.challengee == account2
    assert contract.challenger.money == 0
    assert contract.challengee.money == 0 
    assert contract.expiration.date() == date.today()    
    assert contract.executed == False
    assert contract.week == 4
    assert contract.contract_type == 'SlapContract'
    assert contract.amount == 100 
    assert contract._new == True


@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_contract_initialization_insufficient_funds(setup_accounts):
    account1, account2 = setup_accounts
    date_today = datetime.today()
    
    with pytest.raises(ValueError):
        contract = Vault.SlapContract(challenger=account1, challengee=account2, amount = 101, expiration_date=date_today, week=4)


@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_contract_initialization_negative_amount(setup_accounts):
    account1, account2 = setup_accounts
    date_today = datetime.today()
    
    with pytest.raises(ValueError):
        contract = Vault.SlapContract(challenger=account1, challengee=account2, amount = -50, expiration_date=date_today, week=4)


@pytest.mark.asyncio
@pytest.mark.general
async def test_execute_vault_initialize(setup_vault_accounts):
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    slaps_length = await Vault.len_contracts(contract_type=Vault.SlapContract.__name__)
    wagers_length = await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__)
    assert slaps_length == 0
    assert wagers_length == 0
    assert account1.money == 100
    assert account2.money == 100


@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_execute_slap_contract_success(setup_vault_accounts):
    yesterday = datetime.today() - timedelta(days = 1)
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    contract = Vault.SlapContract(challenger=account1, challengee=account2, amount=50, expiration_date=yesterday, week=4)
    assert account1.money == 50
    assert account2.money == 50
    assert contract.executed == False

    await contract.execute_contract(account1)
    assert account1.money == 150
    assert account2.money == 50
    assert contract.executed == True


@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_def_create_contract_slap(setup_vault_accounts):
    yesterday = datetime.today() - timedelta(days = 1)
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account2.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )
 
    assert account1.money == 50
    assert account2.money == 50
    contracts_length = await Vault.len_contracts(contract_type=Vault.SlapContract.__name__)
    assert contracts_length == 1


@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_def_create_contract_slap_multiple(setup_vault_accounts):
    yesterday = datetime.today() - timedelta(days = 1)
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account2.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account3.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )

    assert account1.money == 0
    assert account2.money == 50
    assert account3.money == 50
    contracts_length = await Vault.len_contracts(contract_type=Vault.SlapContract.__name__)
    assert contracts_length == 2


@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_slap_multiple_execution(setup_vault_accounts):
    yesterday = datetime.today() - timedelta(days = 1)
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account2.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )
    await Vault.create_contract(
        challenger_fantasy_id=account1.fantasy_id, 
        challengee_fantasy_id=account3.fantasy_id, 
        amount = 50, 
        expiration_date=yesterday, 
        week=4, 
        contract_type=Vault.SlapContract.__name__
    )

    ready = await Vault.ready_to_execute(contract_type=Vault.SlapContract.__name__)
    assert ready == True
    contract = await Vault.get_next_contract(contract_type=Vault.SlapContract.__name__)
    assert contract.challenger == account1
    assert contract.challengee == account2
    await contract.execute_contract(account2)
    await Vault.pop_contract(contract_type=Vault.SlapContract.__name__)

    assert account1.money == 0
    assert account2.money == 150
    
    ready = await Vault.ready_to_execute(contract_type=Vault.SlapContract.__name__)
    assert ready == True
    contract = await Vault.get_next_contract(contract_type=Vault.SlapContract.__name__)
    await contract.execute_contract(account3)

    assert account1.money == 0
    assert account3.money == 150
    await Vault.pop_contract(contract_type=Vault.SlapContract.__name__)
    
    contract_length = await Vault.len_contracts(contract_type=Vault.SlapContract.__name__)
    assert contract_length == 0


@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_slap_load_store_accounts_serialized(setup_vault_accounts):
    account_list = await Vault.serialize_accounts()
    contract_list = []
    Vault.accounts.clear()
    for _, value in Vault.contracts.items():
        value.clear()

    assert len(Vault.accounts) == 0
    for key,value in Vault.contracts.items():
        assert len(value) == 0

    await Vault.initialize_from_serialized(accounts=account_list, slap_contracts=contract_list)

    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')
    assert account1.name == 'banana'
    assert account1.discord_tag == '<@59729789855555555>'
    assert account1.discord_id == '59729789855555555'
    assert account1.fantasy_id == '3'
    assert account1.money == 100

    assert account2.name == 'pesado'
    assert account2.discord_tag == '<@95444595755555555>'
    assert account2.discord_id == '95444595755555555'
    assert account2.fantasy_id == '4'
    assert account2.money == 100

    assert account3.name == 'taco'
    assert account3.discord_tag == '<@95648312555555555>'
    assert account3.discord_id == '95648312555555555'
    assert account3.fantasy_id == '5'
    assert account3.money == 100


@pytest.mark.asyncio
@pytest.mark.slap_contract
async def test_slap_load_store_accounts_contracts_serialized(setup_vault_accounts_and_slap_contracts):
    account_list = await Vault.serialize_accounts()
    contract_list = await Vault.serialize_contracts(contract_type=Vault.SlapContract.__name__)
    assert len(contract_list) == 2

    assert Vault.accounts.get('3').money == 0
    assert Vault.accounts.get('4').money == 50
    assert Vault.accounts.get('4').money == 50

    Vault.accounts.clear()
    for _, value in Vault.contracts.items():
        value.clear()


    assert len(Vault.accounts) == 0
    for _,value in Vault.contracts.items():
        assert len(value) == 0

    await Vault.initialize_from_serialized(accounts=account_list, slap_contracts=contract_list)

    assert len(Vault.accounts) == 3
    assert len(Vault.contracts.get(Vault.SlapContract.__name__)) == 2
    assert Vault.accounts.get('3').money == 0
    assert Vault.accounts.get('4').money == 50
    assert Vault.accounts.get('4').money == 50


#############################################################################
# group_wager tests
#############################################################################

@pytest.mark.asyncio
@pytest.mark.group_wager_contract
async def test_group_simple_wager_contract(setup_vault_accounts):
    yesterday = datetime.today() - timedelta(days = 1)
    wager = Vault.GroupWagerContract(team_1_id='1',team_2_id='2', expiration_date=yesterday,week=4, amount=0)
    
    assert wager.winnings == 0
    assert len(wager.predictions) == 0

    gambler_acc = Vault.accounts.get('3')
    await wager.add_prediction(gambler=gambler_acc, prediction_id='2', prediction_points=45, amount=5)
    assert wager.executed == False

    assert wager.winnings == 5
    assert len(wager.predictions) == 1
    assert Vault.accounts.get('3').money == 95

    await wager.execute_contract(gambler_acc)
    assert Vault.accounts.get('3').money == 100
    assert wager.executed == True

    with pytest.raises(ValueError):
        await wager.execute_contract(gambler_acc)


@pytest.mark.asyncio
@pytest.mark.group_wager_contract
async def test_group_wager_contract_duplicate(setup_vault_accounts):
    yesterday = datetime.today() - timedelta(days = 1)
    wager = Vault.GroupWagerContract(team_1_id='1',team_2_id='2', expiration_date=yesterday,week=4, amount=0)
    
    assert wager.winnings == 0
    assert len(wager.predictions) == 0

    gambler_acc_1 = Vault.accounts.get('3')
    await wager.add_prediction(gambler=gambler_acc_1, prediction_id='2', prediction_points=45, amount=5)

    with pytest.raises(ValueError):
        await wager.add_prediction(gambler=gambler_acc_1, prediction_id='3', prediction_points=60, amount=5)
    with pytest.raises(ValueError):
        await wager.add_prediction(gambler=gambler_acc_1, prediction_id='2', prediction_points=70, amount=5)


@pytest.mark.asyncio
@pytest.mark.group_wager_contract
async def test_group_wager_interface(setup_vault_accounts):
    yesterday = datetime.today() - timedelta(days = 1)
    exists = await Vault.wager_by_id_exists(id='8')
    assert exists == False

    await Vault.create_contract(team_1_id='8', team_2_id='9', expiration_date=yesterday, week=4, contract_type=Vault.GroupWagerContract.__name__)
    exists = await Vault.wager_by_id_exists(id='8')
    assert exists == True

    slap_contracts_len = await Vault.len_contracts(contract_type=Vault.SlapContract.__name__)
    wager_contract_len = await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__)
    assert slap_contracts_len == 0
    assert wager_contract_len == 1

    next_wager:Vault.GroupWagerContract = await Vault.get_next_contract(contract_type=Vault.GroupWagerContract.__name__)
    assert len(next_wager.predictions) == 0
    assert next_wager.amount == 0
    assert len(next_wager.predictions) == 0

    with pytest.raises(ValueError):
        await Vault.create_contract(team_1_id='8', team_2_id='8', expiration_date=yesterday, week=4, contract_type=Vault.GroupWagerContract.__name__)

    acc_1 = Vault.accounts.get('3')
    acc_2 = Vault.accounts.get('4')
    await next_wager.add_prediction(gambler=acc_1, prediction_id='8', prediction_points=60, amount=5)
    await next_wager.add_prediction(gambler=acc_2, prediction_id='8', prediction_points=61, amount=5)
    assert next_wager.amount == 10

    with pytest.raises(ValueError):
        await next_wager.add_prediction(gambler=acc_1, prediction_id='8', prediction_points=60, amount=5)


@pytest.mark.asyncio
@pytest.mark.group_wager_contract
async def test_group_wager_execution(setup_vault_accounts):
    yesterday = datetime.today() - timedelta(days = 1)
    await Vault.create_contract(team_1_id='8', team_2_id='9', expiration_date=yesterday, week=4, contract_type=Vault.GroupWagerContract.__name__)

    wager = await Vault.get_wager(fantasy_id='8')
    acc_1 = Vault.accounts.get('3')
    acc_2 = Vault.accounts.get('4')
    acc_3 = Vault.accounts.get('5')
    await wager.add_prediction(gambler=acc_1, prediction_id='8', prediction_points=60, amount=5)
    await wager.add_prediction(gambler=acc_2, prediction_id='9', prediction_points=60, amount=5)
    with pytest.raises(ValueError):
        await wager.add_prediction(gambler=acc_3, prediction_id='8', prediction_points=60, amount = 5)
    with pytest.raises(ValueError):
        await wager.add_prediction(gambler=acc_3, prediction_id='9', prediction_points=60, amount = 5)

    assert acc_1.money == 95
    assert acc_2.money == 95

    await wager.execute_contract(winner=acc_2)
    assert acc_1.money == 95
    assert acc_2.money == 105

    with pytest.raises(ValueError):
        await wager.execute_contract(winner=acc_2)

    len_contracts = await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__) 
    assert len_contracts == 1

    await Vault.pop_contract(contract_type=Vault.GroupWagerContract.__name__)
    len_contracts = await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__) 
    assert len_contracts == 0


@pytest.mark.asyncio
@pytest.mark.general
async def test_load_and_store(setup_vault_accounts_and_wager_contracts):
    found = await Vault.wager_by_id_exists('3')
    not_found = await Vault.wager_by_id_exists('20')
    assert found == True
    assert not_found == False
    assert len(Vault.contracts.get(Vault.SlapContract.__name__)) == 2
    assert len(Vault.contracts.get(Vault.GroupWagerContract.__name__)) == 3

    serialized_accounts = await Vault.serialize_accounts()
    serialized_slap_contracts = await Vault.serialize_contracts(contract_type=Vault.SlapContract.__name__)
    serialized_wager_contracts = await Vault.serialize_contracts(contract_type=Vault.GroupWagerContract.__name__)

    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')

    slap_1 = Vault.contracts.get(Vault.SlapContract.__name__)[0]
    slap_2 = Vault.contracts.get(Vault.SlapContract.__name__)[1]
    
    wager_1 = await Vault.get_wager('1')
    wager_2 = await Vault.get_wager('4')
    wager_3 = await Vault.get_wager('5')

    await Vault.initialize() #clear

    assert len(Vault.contracts.get(Vault.SlapContract.__name__)) == 0
    assert len(Vault.contracts.get(Vault.GroupWagerContract.__name__)) == 0
    await Vault.initialize_from_serialized(accounts=serialized_accounts, slap_contracts=serialized_slap_contracts, wager_contracts=serialized_wager_contracts)

    loaded_account1 = Vault.accounts.get('3')
    loaded_account2 = Vault.accounts.get('4')
    loaded_account3 = Vault.accounts.get('5')
    
    assert account1 == loaded_account1
    assert account1.money == loaded_account1.money
    assert account2 == loaded_account2
    assert account2.money == loaded_account2.money
    assert account3 == loaded_account3
    assert account3.money == loaded_account3.money

    slap_contracts = await Vault.get_contract_deque(contract_type=Vault.SlapContract.__name__)
    assert slap_contracts[0] == slap_1
    assert slap_contracts[1] == slap_2

    loaded_slap_1:Vault.SlapContract = await Vault.get_next_contract(contract_type=Vault.SlapContract.__name__)
    await Vault.pop_contract(contract_type=Vault.SlapContract.__name__)
    assert len(Vault.contracts.get(Vault.SlapContract.__name__)) == 1
    loaded_slap_2 = await Vault.get_next_contract(contract_type=Vault.SlapContract.__name__)
    await Vault.pop_contract(contract_type=Vault.SlapContract.__name__)
    assert len(Vault.contracts.get(Vault.SlapContract.__name__)) == 0
    slaps_len = await Vault.len_contracts(contract_type=Vault.SlapContract.__name__)

    assert slap_1 == loaded_slap_1
    assert slap_2 == loaded_slap_2
    assert slaps_len == 0

    wager_contracts = await Vault.get_contract_deque(contract_type=Vault.GroupWagerContract.__name__)
    assert wager_contracts[0] == wager_1
    assert wager_contracts[1] == wager_2
    assert wager_contracts[2] == wager_3
    
    loaded_wager_1 = await Vault.get_next_contract(contract_type=Vault.GroupWagerContract.__name__)
    await Vault.pop_contract(contract_type=Vault.GroupWagerContract.__name__)
    assert len(Vault.contracts.get(Vault.GroupWagerContract.__name__)) == 2
    loaded_wager_2 = await Vault.get_next_contract(contract_type=Vault.GroupWagerContract.__name__)
    await Vault.pop_contract(contract_type=Vault.GroupWagerContract.__name__)
    assert len(Vault.contracts.get(Vault.GroupWagerContract.__name__)) == 1
    loaded_wager_3 = await Vault.get_next_contract(contract_type=Vault.GroupWagerContract.__name__)
    await Vault.pop_contract(contract_type=Vault.GroupWagerContract.__name__)
    assert len(Vault.contracts.get(Vault.GroupWagerContract.__name__)) == 0
    wager_len = await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__)
    
    assert wager_1 == loaded_wager_1
    assert wager_2 == loaded_wager_2
    assert wager_3 == loaded_wager_3
    assert wager_len == 0


@pytest.mark.asyncio
@pytest.mark.general
async def test_execute_all_contracts(setup_vault_accounts_and_wager_contracts_with_predictions):
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')

    assert account1.money == 50
    assert account2.money == 60
    assert account2.money == 60

    slap_len_before = await Vault.len_contracts(contract_type=Vault.SlapContract.__name__)
    while await Vault.ready_to_execute(contract_type=Vault.SlapContract.__name__):
        contract:Vault.SlapContract = await Vault.get_next_contract(contract_type=Vault.SlapContract.__name__)
        await contract.execute_contract(winner=contract.challengee)
        await Vault.pop_contract(contract_type=Vault.SlapContract.__name__)
    
    slap_len_after = await Vault.len_contracts(contract_type=Vault.SlapContract.__name__)
    assert slap_len_before == 2
    assert slap_len_after == 0

    assert account1.money == 50
    assert account2.money == 80
    assert account3.money == 80

    wager_len_before = await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__)
    while await Vault.ready_to_execute(contract_type=Vault.GroupWagerContract.__name__):
        contract:Vault.GroupWagerContract = await Vault.get_next_contract(contract_type=Vault.GroupWagerContract.__name__)
        await contract.execute_contract(winner=account2)
        await Vault.pop_contract(contract_type=Vault.GroupWagerContract.__name__)

    wager_len_after = await Vault.len_contracts(contract_type=Vault.GroupWagerContract.__name__)
    assert wager_len_before == 3
    assert wager_len_after == 0

    assert account1.money == 50
    assert account2.money == 170
    assert account3.money == 80

@pytest.mark.asyncio
@pytest.mark.general
async def test_refund(setup_vault_accounts_and_wager_contracts_with_predictions):
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')

    while await Vault.ready_to_execute(contract_type=Vault.SlapContract.__name__):
        contract:Vault.SlapContract = await Vault.get_next_contract(contract_type=Vault.SlapContract.__name__)
        assert contract.winnings == 20
        await contract.refund()
        await Vault.pop_contract(contract_type=Vault.SlapContract.__name__)

    while await Vault.ready_to_execute(contract_type=Vault.GroupWagerContract.__name__):
        contract:Vault.GroupWagerContract = await Vault.get_next_contract(contract_type=Vault.GroupWagerContract.__name__)
        assert contract.winnings == 30
        await contract.refund()
        await Vault.pop_contract(contract_type=Vault.GroupWagerContract.__name__)

    assert account1.money == 100
    assert account2.money == 100
    assert account3.money == 100

@pytest.mark.asyncio
@pytest.mark.general
async def test_refund(setup_vault_accounts_and_wager_contracts_with_bonus_and_predictions):
    account1 = Vault.accounts.get('3')
    account2 = Vault.accounts.get('4')
    account3 = Vault.accounts.get('5')

    while await Vault.ready_to_execute(contract_type=Vault.SlapContract.__name__):
        contract:Vault.SlapContract = await Vault.get_next_contract(contract_type=Vault.SlapContract.__name__)
        assert contract.winnings == 20
        await contract.refund()
        await Vault.pop_contract(contract_type=Vault.SlapContract.__name__)

    while await Vault.ready_to_execute(contract_type=Vault.GroupWagerContract.__name__):
        contract:Vault.GroupWagerContract = await Vault.get_next_contract(contract_type=Vault.GroupWagerContract.__name__)
        assert contract.winnings == 40
        await contract.refund()
        await Vault.pop_contract(contract_type=Vault.GroupWagerContract.__name__)

    assert account1.money == 100
    assert account2.money == 100
    assert account3.money == 100