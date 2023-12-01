
import json
import logging
import os
import queue
import sys
import time

from dotenv import load_dotenv
from web3 import Web3
from web3_multi_provider import MultiProvider

load_dotenv()

logger = logging.getLogger('Bot')
logger.setLevel(logging.INFO)
logger.addHandler(logging.FileHandler('/home/ubuntu/pingpongbot/bot.log'))
#logger.addHandler(logging.StreamHandler(sys.stdout))


class Bot:

    def __init__(self):
        # Init values from .env
        self.private_key = os.environ.get('PRIVATE_KEY')
        self.contract_address = os.environ.get('CONTRACT_ADDRESS')
        self.starting_block = int(os.environ.get('STARTING_BLOCK'))

        providers_list = os.environ.get('RPCS').split(',')
        providers = [ os.environ.get(f'RPC_{rpc}') for rpc in providers_list]

        # Init web3 values
        self.w3 = Web3(MultiProvider(providers))
        with open('/home/ubuntu/pingpongbot/abis/pingpong.abi', 'r') as f:
            contract_abi = json.load(f)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=contract_abi)

        self.sending_address = self.w3.eth.account.from_key(self.private_key).address
        logger.info(f'Sending address {self.sending_address}')
        self.nonce = self.w3.eth.get_transaction_count(self.sending_address)

        self.queue = queue.Queue()
        self.pending_pong_tx = None
        self.pending_pong_data = None


    def send_pong_call(self, data):
        if self.pending_pong_tx:
            logger.info(f'QUEUED Call for ping {data}')
            self.queue.put(data)
            return

        if not self.queue.empty():
            logger.info(f'QUEUED Call for ping {data}')
            self.queue.put(data)
            data = self.queue.get()

        self.build_and_send_tx(data)


    def build_and_send_tx(self, data):
        logger.info(f'Send pong call for ping {data}, nonce {self.nonce}')
        tx = self.contract.functions.pong(data).build_transaction({
            'gas': 23_151,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.nonce
        })
        signed_transation = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx = self.w3.eth.send_raw_transaction(signed_transation.rawTransaction)
        self.pending_pong_tx = tx.hex()
        self.pending_pong_data = data
        self.nonce += 1


    def recover_pending_pong_txs(self, pending_pong_txs):
        logger.info('Recovering: pending pong txs')
        data = None
        for tx in pending_pong_txs:
            logger.info(f'Recovering: pending pong tx {tx.hash.hex()}')
            self.pending_pong_tx = tx['hash'].hex()
            data = tx['input']
            self.pending_pong_data = '0x' + data.hex()[10:]
            self.nonce = tx['nonce'] + 1

        ping_tx = self.w3.eth.get_transaction(self.pending_pong_data)
        block_number = ping_tx['blockNumber']
        self.starting_block = block_number + 1

        past_pong_txs = self.get_past_pong_txs()
        past_pong_txs.append({ 'input': data })
        self.get_missing_ping_txs_at_block(block_number, past_pong_txs)


    def get_missing_ping_txs_at_block(self, block_number, pong_txs):
        # There can be several ping txs in one block
        ping_txs = []
        block = self.w3.eth.get_block(block_number, True)
        for tx in block.transactions:
            if tx.to == self.contract_address and tx['from'] != self.sending_address:
                ping_txs.append(self.w3.eth.get_transaction(tx.hash.hex()))
        
        pong_datas = ['0x' + item['input'].hex()[10:] for item in pong_txs]
        ping_hashs = [item['hash'].hex() for item in ping_txs]
        missing_ping_hashs = [h for h in ping_hashs if h not in pong_datas]
        if missing_ping_hashs:
            for hash in missing_ping_hashs:
                logger.info(f'Recovering: missing ping hash: {hash}')
                self.send_pong_call(hash)
        else:
            logger.info('Recovering: no missing ping hash')


    def recover_from_last_pong(self, pong_txs):
        logger.info('Recovering: from latest pong txs')
        
        call_data = pong_txs[-1].input.hex()[10:]
        tx = self.w3.eth.get_transaction(call_data)        
        self.get_missing_ping_txs_at_block(tx.blockNumber, pong_txs)
        
        self.starting_block = tx.blockNumber + 1
        logger.info(f'Recovering: starting block set to {self.starting_block}')            


    def get_pending_pong_txs(self):
        logger.info(f'Recovering: get pending pong txs')
        pending_txs = []
        # Infura and most providers don't support eth_newPendingTransactionFilter
        pending_block = self.w3.eth.get_block('pending', True)
        if pending_block and 'transactions' in pending_block:
            for tx in pending_block['transactions']:
                if tx['from'] == self.sending_address and tx['to'] == self.contract_address:
                    pending_txs.append(tx)

        return pending_txs


    def get_past_pong_txs(self):
        logger.info(f'Recovering: get past pong txs from block {self.starting_block}')
        pong_txs = []
        logs = self.contract.events.Pong().get_logs(fromBlock=self.starting_block)        
        for log in logs:
            tx = self.w3.eth.get_transaction(log.transactionHash.hex())
            if tx['from'] == self.sending_address:
                pong_txs.append(tx)
                
        return pong_txs
    

    def recover(self):
        # Do we have pending txs ?
        pending_pong_txs = self.get_pending_pong_txs()
        if pending_pong_txs:
            self.recover_pending_pong_txs(pending_pong_txs)
        else:
            # If no pending tx, check our latest pong txs
            pong_txs = self.get_past_pong_txs()        
            if pong_txs:
                self.recover_from_last_pong(pong_txs)
            else:
                logger.info('Recovering: starting block unchanged')
        
        # Get missed ping events
        filter = self.contract.events.Ping.create_filter(fromBlock=self.starting_block)
        for event in filter.get_all_entries():
            hash = event['transactionHash'].hex()
            logger.info(f'Recovering: ping event detected: {hash}')
            self.send_pong_call(hash)

        logger.info(f'Recovering: ended')


    def process_new_entries(self, filter):
        for event in filter.get_new_entries():
            hash = event['transactionHash'].hex()
            logger.info(f'Filter: ping event detected: {hash}')
            self.send_pong_call(hash)


    def check_pending_txs(self):
        logger.info(f'Status of tx {self.pending_pong_tx} for ping {self.pending_pong_data}')
        try:
            receipt = self.w3.eth.get_transaction_receipt(self.pending_pong_tx)
            if receipt:
                if receipt.status:
                    logger.info('[MINTED]')
                    self.pending_pong_tx = None
                else:
                    logger.error('[FAILED]')
                    logger.error(receipt)
                    sys.exit(1)
            else:
                logger.info('[PENDING]')
        except: # TransactionNotFound
            logger.info('[PENDING]')


    def consume_pong_queue(self):
        if not self.pending_pong_tx and not self.queue.empty():
            self.build_and_send_tx(self.queue.get())


    def run(self):
        if self.w3.eth.block_number != self.starting_block:
            logger.info('Need recovering')
            self.recover()

        # Filter ping events
        filter = self.contract.events.Ping.create_filter(fromBlock=self.starting_block)
        while True:
            self.process_new_entries(filter)
            if self.pending_pong_tx:
                self.check_pending_txs()
            self.consume_pong_queue()

            # Don't overflow web3 provider (About the time between 2 blocks on Goerli)
            time.sleep(12)            


Bot().run()
