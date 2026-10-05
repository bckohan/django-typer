"""
typer.Exit raised from a chained subcommand - see issue #318.
"""

import typer

from django_typer.management import TyperCommand, command


class Command(TyperCommand, chain=True):
    @command()
    def a(self):
        print("a ran")

    @command()
    def b(self, code: int = 0):
        raise typer.Exit(code)
