"""
Copy the ABIs for deployed contracts.
"""
import json
from os.path import join, exists, dirname, realpath

SCRIPT_DIR = dirname(realpath(__file__))
ABI_DIR = realpath(join(SCRIPT_DIR, "../oracle/bin/abi"))


def main(args):
    artifacts_dir = join(args.core_repo, "artifacts")
    assert exists(artifacts_dir), "Smart contracts not compiled."
    contract_path = join(artifacts_dir, 
                         "contracts/oracles/Oracle.sol/Oracle.json",
                         )
    oracle = from_json(contract_path)
    to_json(oracle["abi"], join(ABI_DIR, "eth_oracle_abi.json"))

    print("done.")


def from_json(path):
    with open(path) as fp:
        result = json.load(fp)
    return result


def to_json(data, path):
    with open(path, 'w') as fp:
        json.dump(data, fp)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("core_repo",
                        type=str,
                        help="Path to Pareto's core smart contract repo",
                        )
    args = parser.parse_args()

    main(args)
