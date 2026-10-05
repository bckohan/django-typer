"""
A chained command wrapped in a transaction. Exercises the ``atomic`` option
across every way a command can end - see issue #219.
"""

import sys

import typer
from django.core.management import CommandError
from django.db import DEFAULT_DB_ALIAS

from django_typer.management import TyperCommand, command, finalize, initialize
from tests.apps.test_app.models import ShellCompleteTester


class Command(TyperCommand, chain=True):
    atomic = True
    print_result = False

    @initialize()
    def init(self, database: str = DEFAULT_DB_ALIAS, fail_finalize: bool = False):
        self.fail_finalize = fail_finalize

    @command()
    def write(self, value: str, using: str = DEFAULT_DB_ALIAS):
        ShellCompleteTester.objects.using(using).create(char_field=value)

    @command()
    def end(self, how: str):
        if how == "return":
            return "done"
        if how == "exit0":
            raise typer.Exit(0)
        if how == "exit3":
            raise typer.Exit(3)
        if how == "abort":
            raise typer.Abort()
        if how == "sysexit0":
            sys.exit(0)
        if how == "sysexit4":
            sys.exit(4)
        if how == "interrupt":
            raise KeyboardInterrupt()
        if how == "cmderror":
            raise CommandError("boom", returncode=5)
        if how == "valueerror":
            raise ValueError("boom")
        raise CommandError(f"unknown ending: {how}")

    @finalize()
    def finish(self, results):
        if self.fail_finalize:
            raise RuntimeError("finalizer failed")
        return results
