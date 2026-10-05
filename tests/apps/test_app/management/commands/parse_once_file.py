"""
A file argument on the root command must still be open when the command runs.
Django parses and then executes in two steps - see issue #209.
"""

import typer

from django_typer.management import TyperCommand


class Command(TyperCommand):
    def handle(self, file: typer.FileBinaryRead):
        return file.read().decode()
