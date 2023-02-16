"""
Fetch data from various APIs.
"""
import time
import requests
from collections import defaultdict

BASE_TOKENS = [
    "eth",
]


def get_time():
    """Get current time in unix"""
    return int(time.time())


class BaseAPI:
    r"""Base class of API to inherit from."""

    def __init__(self, min_wait_sec=30):
        assert self.check_connection(), "Failed to connect to API"

        # Minimum seconds to cache call
        self.min_wait_sec = min_wait_sec

        # maps from token to values
        self.cached_time = defaultdict(lambda: 0)
        self.cached_data = defaultdict(lambda: 0)

    def get_base_url(self):
        # Base API url
        raise NotImplementedError

    def get_data_url(self):
        # Endpoint url
        raise NotImplementedError

    @staticmethod
    def get_endpoint(base, url):
        return f"{base}{url}"

    def parse_response(self, r):
        # Fetch price from successful response
        raise NotImplementedError

    def check_connection(self):
        # Check connection with API
        # By default, this does not check liveness
        return True

    def get_data(self, base):
        assert base in BASE_TOKENS, f"Unsupported base token: {base}"

        now = get_time()

        if (now - self.cached_time[base]) < self.min_wait_sec:
            return self.cached_data[base]

        endpoint = self.get_endpoint(self.get_base_url(), self.get_data_url(base))
        r = requests.get(endpoint)

        if r.ok:
            r = r.json()
            data = self.parse_response(r)

            if data is not None:
                self.cached_time[base] = get_time()
                self.cached_data[base] = data

                return data

        return None


class BinanceAPI(BaseAPI):
    r"""Get spot data from Binance API."""

    BASE_URL = "https://api.binance.com"

    def check_connection(self):
        r = requests.get(self.get_endpoint(self.get_base_url(), "/api/v3/ping"))
        return r.ok

    def get_base_url(self):
        return "https://api.binance.com"

    def get_data_url(self, base_token):
        return f"/api/v3/ticker/price?symbol={base_token.upper()}USDC"

    def parse_response(self, r):
        data = None
        if 'price' in r:
            try:
                # Try to cast a float
                data = float(r["price"])
            except:
                data = None
        
        return data



class FTXAPI(BaseAPI):
    r"""Get spot data from FTX API."""

    def get_base_url(self):
        return "https://ftx.com/api"

    def get_data_url(self, base_token):
        return f"/markets/{base_token.upper()}/USD"

    def parse_response(self, r):
        data = None
        if 'result' in r:
            if 'price' in r['result']:
                try:
                    data = float(r['result']['price'])
                except:
                    data = None
        return data


class BitFinexAPI(BaseAPI):
    r"""Get spot data from BitFinex API."""

    def check_connection(self):
        r = requests.get(self.get_endpoint(self.get_base_url(), "/platform/status"))
        if r.ok:
            return r.json()[0] == 1
        return False

    def get_base_url(self):
        return "https://api-pub.bitfinex.com/v2"

    def get_data_url(self, base_token):
        return f"/ticker/t{base_token.upper()}USD"

    def parse_response(self, r):
        data = None
        if len(r) > 6:
            row = r[6]
            try:
                data = float(row)
            except:
                data = None
        return data


class CompoundV2API(BaseAPI):
    r"""Get risk-free interest rates from Compound V2 API."""

    def __init__(self, min_wait_sec=30):
        assert self.check_connection(), "Failed to connect to API"
        self.min_wait_sec = min_wait_sec
        self.cached_time = 0
        self.cached_data = 0

    def get_base_url(self):
        return "https://api.compound.finance/api/v2"

    def get_data_url(self):
        usdc = "0x39AA39c021dfbaE8faC545936693aC917d5E7563"
        now = int(time.time())
        return f"/market_history/graph?asset={usdc}&min_block_timestamp={now-86400}&max_block_timestamp={now}&num_buckets=1"

    def parse_response(self, r):
        data = None
        if 'supply_rates' in r:
            if len(r['supply_rates']) > 0:
                row = r['supply_rates'][-1]
                if 'rate' in row:
                    data = row['rate']
        return data

    def get_data(self):
        now = get_time()
        if (now - self.cached_time) < self.min_wait_sec:
            return self.cached_data

        endpoint = self.get_endpoint(self.get_base_url(), self.get_data_url())
        r = requests.get(endpoint)

        if r.ok:
            r = r.json()
            data = self.parse_response(r)

            self.cached_time = get_time()
            self.cached_data = data

            return data

        return None


if __name__ == "__main__":
    # api = BinanceAPI()
    # api = FTXAPI()
    # api = BitFinexAPI()
    api = CompoundV2API()
    print(api.get_data())

