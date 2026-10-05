"""
typer.Exit raised from a handle()-only command, which can also be called
directly as a function - see issue #318.
"""

import typer

from django_typer.management import TyperCommand


class Command(TyperCommand):
    def handle(self, code: int = 0):
        raise typer.Exit(code)
