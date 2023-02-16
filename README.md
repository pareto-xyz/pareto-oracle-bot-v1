# Pareto Oracle Bot V1

**[Disclaimer: This repository is no longer maintained and is meant for primarily educational purposes.]**

Part of the series detailed in this [whitepaper](https://github.com/pareto-xyz/pareto-order-book-whitepaper/blob/main/how_to_orderbook.pdf). 

The [Pareto smart contracts](https://github.com/pareto-xyz/pareto-core-v1) require oracles for spot and mark prices. Due to quality and speed concerns, we do not rely on Chainlink. Rather, we opt to build our own oracles. 

This repo is responsible for fetching price feeds from Binance, FTX, and Bitfinex, and posting the median price on-chain at a steady interval. The repo will also compute historical volatility for each price feed.

## Setup

Install the package locally:
```
pip install -e ./
```

This oracle is dependent on Pareto's smart contracts. Clone [this repo](https://github.com/pareto-xyz/pareto-core-v1) and run the following command in its root directory while running a hardhat node:
```
npx hardhat run ./scripts/deploy.mockusdc.ts --network localhost
```
This will return an output containing the following:
```
Deployer: ...
Private Key: ...
...
Deployed ETH spot oracle: ...
Deployed ETH mark oracle: ...
...
```
Then, set environment variable `ETH_PRIVATE_KEY` to private key of the deployer. Also set `ETH_SPOT_ORACLE` to the ETH spot price oracle address, and set `ETH_MARK_ORACLE` to the ETH mark price oracle address. It is important that this is up-to-date.

This oracle is also dependent on Pareto's order book. Clone [this repo](https://github.com/pareto-xyz/pareto-orderbook-v1) and continue with its setup instructions. Build the binary by running `go build`, which will create a binary. Run the binary to start the local server. Alternatively, you may try `go run`, though compilation is recommended. 

## Usage

Run the `main.py` script inside `oracle/bin`:
```
python oracle/bin/main.py
```

To post results on-chain, you will need to specify your private key in an environment variable `ETH_PRIVATE_KEY`.
The account associated with this private key must either be an owner or keeper of the `pareto-core-v1` smart contract.
If no key is provided or an invalid key is provided, results are not saved, only printed. 

By default this script assumes a local chain via Ganache. If you are not testing locally (e.g. Arbitrum testnet or mainnet), then you will need to ensure that you have an Alchemy key set at `ORACLE_ALCHEMY_API_KEY` for mainnet and `TEST_ORACLE_ALCHEMY_API_KEY` for mainnet. Also you will need to set the envionrment variable `ORDERBOOK_HOST` to the URL for the Pareto order book.
