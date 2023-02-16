from oracle import bot


def main(args):
    robot = bot.OracleBot(chain=args.chain, deploy=args.deploy)
    robot.initialize("eth")
    robot.run("eth")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain",
                        type=str,
                        choices=["local", "test", "main"],
                        default="local",
                        )
    parser.add_argument("--deploy",
                        action="store_true",
                        default=False,
                        help="If true, post to chain (default False)",
                        )
    args = parser.parse_args()

    main(args)
