import pytest
from datetime import datetime, timedelta
from collections import deque
from exceptions.vault_exceptions import ExpirationDateError

from bet_vault.vault import Vault
import file_manager



_filename_accounts = 'accounts_test.json'
_filename_contracts = 'contracts_test.json'

#######################################################
# Individual Tests
#######################################################

@pytest.fixture(autouse=True)
def fresh_vault():
    Vault.accounts.clear()
    Vault.contracts.clear()

@pytest.fixture
def setup_accounts():
    account1 = Vault.BankAccount('banana','<@59729789855555555>','59729789855555555', '3', 100)
    account2 = Vault.BankAccount('pesado','<@59729789855555555>','59729789855555555', '4', 100)
    Vault.accounts['3'] = account1
    Vault.accounts['4'] = account2
    return account1, account2

@pytest.fixture
def setup_three_accounts():
    account1 = Vault.BankAccount('banana', '<@59729789855555555>','59729789855555555', '3', 100)
    account2 = Vault.BankAccount('pesado', '<@95444595755555555>','95444595755555555', '4', 100)
    account3 = Vault.BankAccount('taco','<@95648312555555555>','95648312555555555', '5', 100)
    Vault.accounts['3'] = account1
    Vault.accounts['4'] = account2
    Vault.accounts['5'] = account3
    return account1, account2, account3

@pytest.fixture
def create_contracts_deque_and_accounts(setup_three_accounts):
    account1, account2, account3 = setup_three_accounts
    accounts_dict = {}
    accounts_dict[account1.fantasy_id] = account1
    accounts_dict[account2.fantasy_id] = account2
    accounts_dict[account3.fantasy_id] = account3

    contracts_deque = deque()
    date = datetime.today()
    contract1 = Vault.Contract(account1, account2, 10, date)
    contract2 = Vault.Contract(account1, account3, 10, date)
    contract3 = Vault.Contract(account2, account3, 10, date)
    contract4 = Vault.Contract(account3, account1, 10, date)
    contracts_deque.append(contract1)
    contracts_deque.append(contract2)
    contracts_deque.append(contract3)
    contracts_deque.append(contract4)

    return contracts_deque,accounts_dict

# object init #
@pytest.mark.asyncio
@pytest.mark.initialization
async def test_vault_initialization():
    account = Vault.BankAccount('banana','<@59729789855555555>','59729789855555555', '3', 100)
    assert account.name == 'banana'
    assert account.fantasy_id == '3'
    assert account.money == 100
    assert account.discord_tag == '<@59729789855555555>'
    assert account.discord_id == '59729789855555555'

@pytest.mark.asyncio
@pytest.mark.initialization
async def test_contract_initialization(setup_accounts):
    account1, account2 = setup_accounts
    date = datetime.today()
    contract = Vault.Contract(account1, account2, 100, date)
    assert contract.challenger == account1
    assert contract.challengee == account2
    assert contract.amount == 200 # 100 from each
    assert contract.expiration == date
    assert contract.executed == False

@pytest.mark.asyncio
@pytest.mark.initialization
async def test_contract_initialization_insufficient_funds(setup_accounts):
    account1, account2 = setup_accounts
    date = datetime.today()
    
    with pytest.raises(ValueError):
        contract = Vault.Contract(account1, account2, 101, date)

@pytest.mark.asyncio
@pytest.mark.initialization
async def test_contract_initialization_negative_amount(setup_accounts):
    account1, account2 = setup_accounts
    date = datetime.today()
    
    with pytest.raises(ValueError):
        contract = Vault.Contract(account1, account2, -50, date)

@pytest.mark.asyncio
@pytest.mark.initialization
async def test_vault_initialize_def(create_contracts_deque_and_accounts):
    contracts_deque, accounts_dict= create_contracts_deque_and_accounts
    
    manager = file_manager.TestingManager()
    await Vault.initialize(manager, _filename_contracts, _filename_accounts, accounts_dict, contracts_deque)
    assert len(Vault.accounts) == 3
    assert len(Vault.contracts) == 4


# transfer money #
@pytest.mark.asyncio
@pytest.mark.transfer_money
async def test_transfer_money(setup_accounts):
    acc1, acc2 = setup_accounts
    await Vault.transfer_money("3", "4", 50)
    assert acc1.money == 50
    assert acc2.money == 150

@pytest.mark.asyncio
@pytest.mark.transfer_money
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


# add money #
@pytest.mark.asyncio
@pytest.mark.add_money
async def test_add_money_success(setup_accounts):
    account, _ = setup_accounts
    await Vault.add_money('3',50)
    assert account.money == 150
    
@pytest.mark.asyncio
@pytest.mark.add_money
async def test_add_money_negative(setup_accounts):
    _, account = setup_accounts
    with pytest.raises(ValueError):
        await Vault.add_money('4',-50)
    
@pytest.mark.asyncio
@pytest.mark.add_money
async def test_add_money_id_fail():
    with pytest.raises(ValueError):
        await Vault.add_money('6',10)

@pytest.mark.asyncio
@pytest.mark.add_money
async def test_add_money_bad_input(setup_accounts):
    account1, account2 = setup_accounts
    with pytest.raises(TypeError):
        await Vault.add_money(3,50)
    with pytest.raises(TypeError):
        await Vault.add_money(3,'50')
    with pytest.raises(TypeError):
        await Vault.add_money('3','50')


# deduct money #
@pytest.mark.asyncio
@pytest.mark.deduct_money
async def test_deduct_money_success(setup_accounts):
    account, _= setup_accounts
    await Vault.deduct_money('3',50)
    assert account.money == 50
    await Vault.deduct_money('3',50)
    assert account.money == 0 

@pytest.mark.asyncio
@pytest.mark.deduct_money
async def test_deduct_money_negative(setup_accounts):
    account, _= setup_accounts
    with pytest.raises(ValueError):
        await Vault.deduct_money('3', -50)

@pytest.mark.asyncio
@pytest.mark.deduct_money
async def test_deduct_money_id_fail():
    with pytest.raises(ValueError):
        await Vault.deduct_money('6', 50)

@pytest.mark.asyncio
@pytest.mark.deduct_money
async def test_deduct_money_balance_fail(setup_accounts):
    account, _= setup_accounts
    with pytest.raises(ValueError):
        await Vault.deduct_money('3', 150)

@pytest.mark.asyncio
@pytest.mark.deduct_money
async def test_deduct_money_bad_input(setup_accounts):
    account1, account2 = setup_accounts
    with pytest.raises(TypeError):
        await Vault.deduct_money(3,50)
    with pytest.raises(TypeError):
        await Vault.deduct_money(3,'50')
    with pytest.raises(TypeError):
        await Vault.deduct_money('3','50')


#######################################################
# Contract Tests
#######################################################


@pytest.mark.asyncio
@pytest.mark.execute_contract
async def test_execute_contract_success(setup_accounts):
    account1, account2 = setup_accounts
    today = datetime.today()
    contract = Vault.Contract(account1, account2, 50, today)

    await contract.execute_contract(account1)
    assert contract.executed == True

@pytest.mark.asyncio
@pytest.mark.execute_contract
async def test_execute_contract_date_fail(setup_accounts):
    account1, account2 = setup_accounts
    tomorrow = datetime.today() + timedelta(days=1)
    contract = Vault.Contract(account1, account2, 50, tomorrow)

    with pytest.raises(ExpirationDateError):
        await contract.execute_contract(account1)

@pytest.mark.asyncio
@pytest.mark.execute_contract
async def test_execute_contract_input_type_fail(setup_accounts):
    account1, account2 = setup_accounts
    tomorrow = datetime.today() - timedelta(days=1)
    contract = Vault.Contract(account1, account2, 50, tomorrow)

    with pytest.raises(TypeError):
        await contract.execute_contract('banana')
    with pytest.raises(TypeError):
        await contract.execute_contract('banana')
    with pytest.raises(TypeError):
        await contract.execute_contract(contract)

@pytest.mark.asyncio
@pytest.mark.execute_contract
async def test_execute_contract_invalid_account(setup_three_accounts):
    account1, account2, account3 = setup_three_accounts
    yesterday = datetime.today() - timedelta(days=1)
    contract = Vault.Contract(account1, account2, 50, yesterday)

    with pytest.raises(ValueError):
        await contract.execute_contract(account3)

