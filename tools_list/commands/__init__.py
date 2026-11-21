"""The tools-list subcommands: one module per command."""

from tools_list.commands import purge, review, update

COMMANDS = {
    "update": update.run,
    "review": review.run,
    "purge": purge.run,
}
