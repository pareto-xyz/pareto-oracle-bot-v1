import os, json
import requests
import time
import statistics

from collections import defaultdict
from web3 import Web3, HTTPProvider

from oracle.utils import get_time
from oracle.api import BinanceAPI, FTXAPI, BitFinexAPI, CompoundV2API

bin_dir = os.path.dirname(os.path.realpath(__file__))
abi_dir = os.path.join(bin_dir, "abi")

# Store path to contract addresses
CONTRACT_ADDRS = {
    "eth": os.environ.get("ORACLE_CONTRACT"),
}

# Stores path to contract ABIs
CONTRACT_ABIS = {
    "eth": os.path.join(abi_dir, "eth_oracle_abi.json"),
}

UNDERLYING_CODES = {
    "eth": 0,
}

PRICE_PRECISION = 3
INTEREST_PRECISION = 6


class OracleBot:
    r"""Bot that fetches prices from Pareto's order book and  posts the result to an 
    on-chain oracle.

    We read frequently from API, and less frequently post on-chain. If we find
    that the price moves > 0.5%, post immediately.

    Arguments
    --
    chain: string (default: local)
        choices: local | test | main
        By default use a Ganache local chain
        If 'test', use Arbitrum's Goerli test net
        If 'main', use Arbitrum's Goerli main net
        If 'test' or 'main', requires Alchemy API key
    deploy: bool (default: True)
        By default, deploy. If false, just print value
    max_move_perc: float (default: 1% or 0.01)
        Maximum movement in data to immedately post on-chain
    post_rate: integer (default: 60)
        Rate in seconds, of posting on-chain
    read_rate: integer (default: 5)
        Rate in seconds, of reading from API

    Notes
    --
    - You must set your ethereum private key to ETH_PRIVATE_KEY as an environment variable.
    - You must set your alchemy API key to ALCHEMY_API_KEY as an environment variable.
    """
    def __init__(self,
                 chain='local',
                 deploy=True,
                 max_move_perc=0.01,
                 post_rate=60,
                 read_rate=5,
                 ):
        self.initialized = defaultdict(lambda: False)

        # Stores last time of posting on-chain
        self.last_post_time = {}
        self.last_post_data = {}

        # Initialize data sources for getting spot price
        self.spot_price_sources = [
            BinanceAPI(min_wait_sec=read_rate),
            FTXAPI(min_wait_sec=read_rate),
            BitFinexAPI(min_wait_sec=read_rate),
        ]

        # Initialize data sources for getting interest rate
        self.interest_rate_sources = [
            CompoundV2API(min_wait_sec=read_rate),
        ]

        # Save to class
        self.chain = chain
        self.deploy = deploy
        self.max_move_perc = max_move_perc
        self.post_rate = post_rate
        self.read_rate = read_rate

    def get_mark_price(self, underlying, spot_price, interest_rate):
        r"""Call an endpoint in the Pareto backend to get mark price at a particular
        spot and interest rate.
        Arguments
        --
        underlying (string): One of the keys in UNDERLYING_CODES
        spot_price (float): Spot price to compute mark price
        interest_rate (float): Risk-free rate to compute interest rate
        """
        backend_url = ("http://localhost:8080" 
                       if self.chain == 'local' else "https://paretolabs.xyz")

        code = UNDERLYING_CODES[underlying]
        params = {
            'spot': spot_price,
            'interestRate': interest_rate,
        }
        response = requests.get(f"{backend_url}/public/price/mark/{code}", 
                                params=params,
                                )

        # Check correct status code
        if response.status_code != 200:
            return None, None, False
        
        data = response.json() 

        if "message" in data:
            if "call" not in data["message"] or "put" not in data["message"]:
                return None, None, False
            
            call_marks = data["message"]["call"]
            put_marks = data["message"]["put"]

            # convert strings to real numbers
            call_marks = [round(float(x), PRICE_PRECISION) for x in call_marks]
            put_marks = [round(float(x), PRICE_PRECISION) for x in put_marks]

            return call_marks, put_marks, True

        return None, None, False

    def get_spot_price(self, underlying):
        r"""Fetch spot price for the underlying asset from APIs.
        Arguments
        --
        underlying (string): One of the keys in UNDERLYING_CODES
        """
        prices = []
        for source in self.spot_price_sources:
            # We don't need to worry about over calling this because the 
            # price feeds themselves cache API calls
            price = source.get_data(underlying)

            if price is not None:
                prices.append(price)

        if len(prices) == 0:
            return None, False
        elif len(prices) > 1:
            # Get median over sources
            data = statistics.median(prices)
        else:
            data = prices[0]

        data = round(data, PRICE_PRECISION)
        return data, True

    def get_interest_rate(self):
        r"""Fetch interest rate for the underlying asset from APIs.
        Arguments
        --
        underlying (string): One of the keys in UNDERLYING_CODES
        """
        rates = []
        for source in self.interest_rate_sources:
            rate = source.get_data()

            if rate is not None:
                rates.append(rate)

        if len(rates) == 0:
            return None, False
        elif len(rates) > 1:
            # Get median over sources
            data = statistics.median(rates)
        else:
            data = rates[0]

        data = round(data, INTEREST_PRECISION)
        return data, True

    def initialize(self, underlying):
        r"""Get when first starting to get the first run of last post data.
        Arguments
        --
        underlying (string): Symbol of base token e.g. ETH
        
        Notes
        --
        Sets the `last_post_time` and `last_post_data` variables.
        """
        assert not self.initialized[underlying]
        spot_price, success = self.get_spot_price(underlying)
        if not success:
            raise Exception('initialize: failed to get spot price')
        interest_rate, success = self.get_interest_rate()
        if not success:
            raise Exception('initialize: failed to get interest rate')
        call_prices, put_prices, success = self.get_mark_price(underlying,
                                                               spot_price,
                                                               interest_rate,
                                                               )
        if not success:
            raise Exception('initialize: failed to get mark prices')

        data = {
            'spot_price': spot_price,
            'interest_rate': interest_rate,
            'call_prices': call_prices,
            'put_prices': put_prices,
        }
        self.last_post_data[underlying] = data
        self.last_post_time[underlying] = get_time()
        self.initialized[underlying] = True

    def get_data(self, underlying):
        r"""Get all data for the underlying token.
        Arguments
        --
        underlying (string): Symbol of base token e.g. ETH

        Returns
        --
        price (float): Median price over exchanges
        """
        assert self.initialized[underlying]
        # Get current time
        cur_time = get_time()

        spot_price, spot_success = self.get_spot_price(underlying)
        if not spot_success:
            spot_price = self.last_post_data[underlying]['spot_price']

        interest_rate, rate_success = self.get_interest_rate()
        if not rate_success:
            interest_rate = self.last_post_data[underlying]['interest_rate']
        call_prices, put_prices, mark_success = self.get_mark_price(underlying,
                                                                    spot_price,
                                                                    interest_rate,
                                                                    )
        if not mark_success:
            call_prices = self.last_post_data[underlying]['call_prices']
            put_prices = self.last_post_data[underlying]['put_prices']

        data = {
            'spot_price': spot_price,
            'interest_rate': interest_rate,
            'call_prices': call_prices,
            'put_prices': put_prices,
        }

        print(f"[read, time={cur_time}] {underlying}: spot={spot_price}")

        # Compute amount the spot price moved from last posted data
        last_spot_price = self.last_post_data[underlying]['spot_price']
        spot_move = abs((spot_price - last_spot_price) / last_spot_price)

        if cur_time - self.last_post_time[underlying] > self.post_rate:
            if self.deploy:
                self.post(underlying, data)

            # Update posted data 
            self.last_post_data[underlying] = data
            self.last_post_time[underlying] = cur_time

            print(f"[posted, time={cur_time}] {underlying}: " + 
                  f"spot={spot_price}, move={round(spot_move*100,3)}%")

        elif spot_move >= self.max_move_perc:
            # If (new_data - last_data) / last_data >= max %, post
            if self.deploy:
                self.post(underlying, data)

            self.last_post_data[underlying] = data
            self.last_post_time[underlying] = cur_time

            print(f"[posted, time={cur_time}] {underlying}: " + 
                  f"spot={spot_price}, move={round(spot_move*100,3)}%")

        return 

    def get_alchemy_url(self):
        channel = "goerli" if self.test_net else "mainnet"
        return f"https://arb-{channel}.g.alchemy.com/v2" 

    def call_contract(self, contract, wallet, data):
        # https://leftasexercise.com/2021/08/22/using-web3-py-to-interact-with-a-smart-contract/
        # https://ethereum.stackexchange.com/questions/127130/how-to-call-certain-solidity-function-based-on-python-function-parameter
        return contract.functions.setLatestPrice(data['spot_price'],
                                                 data['interest_rate'],
                                                 data['call_prices'],
                                                 data['put_prices'],
                                                 ).transact({"from": wallet})

    def post(self, underlying, data):
        private_key = os.environ.get("PARETO_ADMIN_PRIVATE_KEY")
        assert private_key is not None, "You must set PRIVATE_KEY environment variable"
        assert private_key.startswith("0x"), "Private key must start with 0x hex prefix"

        if self.chain == "local":
            # Call the hardhat local chain
            w3_url = "http://127.0.0.1:8545"
        else:
            # Call Alchemy to fetch data
            env_key = "TEST_ORACLE_ALCHEMY_API_KEY" if self.test_net else "ORACLE_ALCHEMY_API_KEY"
            w3_url = f"{self.get_alchemy_url()}/{os.environ.get(env_key, '')}"

        w3 = Web3(HTTPProvider(w3_url))
        assert w3.isConnected(), "Failed to connect to web3"

        # get public address
        wallet = w3.eth.account.from_key(private_key)

        # get contract
        contract = w3.eth.contract(address=CONTRACT_ADDRS[underlying]["spot"],
                                   abi=json.loads(CONTRACT_ABIS[underlying]["spot"]))

        # call contract function
        tx_hash = self.call_contract(contract, wallet, data)
        
        # wait for transaction to be mined
        w3.eth.wait_for_transaction_receipt(tx_hash);

    def run(self, underlying):
        """
        Entry point: this continuously queries CeFi APIs and posts 
        median scores to smart contract.
        """
        if not self.initialized[underlying]:
            raise Exception(f"Please run `initialize`.")

        while True:
            self.get_data(underlying)
            time.sleep(self.read_rate)
