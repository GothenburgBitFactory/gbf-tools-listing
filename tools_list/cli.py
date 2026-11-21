"""Command line interface of the tools-list package."""

import argparse
import sys

from tools_list.commands import COMMANDS
from tools_list.log import die


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tools-list",
        description="Generate and maintain the tools listings for taskwarrior.org and timewarrior.net.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    update = subparsers.add_parser(
        "update",
        help="regenerate the tools listing from all sources",
    )
    update.add_argument(
        "project",
        metavar="DIR",
        help="directory with config.json and the files it names",
    )

    review = subparsers.add_parser(
        "review",
        help="interactively review new tools and the current blacklist",
    )
    review.add_argument(
        "project",
        metavar="DIR",
        help="directory with config.json and the files it names",
    )
    review.add_argument(
        "--since",
        metavar="DATE|COMMIT",
        help="review tools added since DATE (YYYY-MM-DD) or since COMMIT, instead of since the recorded review commit",
    )

    purge = subparsers.add_parser(
        "purge",
        help="remove blacklisted entries whose URLs return a 404, update entries whose repositories were renamed",
    )
    purge.add_argument(
        "project",
        metavar="DIR",
        help="directory with config.json and the files it names",
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        COMMANDS[args.command](args)
    except KeyboardInterrupt:
        sys.exit(130)
    except EOFError:
        die("Aborted: no more input available.")


if __name__ == "__main__":
    main()
