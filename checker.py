import json
import os
import queue

from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

starting_block = int(os.environ.get('STARTING_BLOCK'))

w3 = Web3(Web3.HTTPProvider(os.environ.get('RPC_ALCHEMY')))
with open('abis/pingpong.abi', 'r') as f:
    contract_abi = json.load(f)
contract = w3.eth.contract(address=os.environ.get('CONTRACT_ADDRESS'), abi=contract_abi)

pings = queue.Queue()
pongs = queue.Queue()

print('Get Ping events', end='', flush=True)
filter = contract.events.Ping.create_filter(fromBlock=starting_block)
for event in filter.get_all_entries():
    print('.', end='', flush=True)
    pings.put(event['transactionHash'].hex())
    
print('\nGet Pong events', end='', flush=True)
filter = contract.events.Pong.create_filter(fromBlock=starting_block)
for event in filter.get_all_entries():
    print('.', end='', flush=True)
    hash = event['transactionHash']
    tx = w3.eth.get_transaction(hash)
    pongs.put('0x' + tx['input'].hex()[10:])

print('\nChecking', end='')
for ping in list(pings.queue):
    print('.', end='', flush=True)
    pong = pongs.get()
    if ping != pong:
        print(ping, pong)
