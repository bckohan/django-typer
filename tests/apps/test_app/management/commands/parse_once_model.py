"""
A model argument on the root command must be looked up once - see issue #210.
"""

import typing as t

import typer

from django_typer.management import TyperCommand
from django_typer.parsers.model import ModelObjectParser
from tests.apps.test_app.models import ShellCompleteTester


class Command(TyperCommand):
    def handle(
        self,
        obj: t.Annotated[
            ShellCompleteTester,
            typer.Argument(parser=ModelObjectParser(ShellCompleteTester, "char_field")),
        ],
    ):
        return obj.char_field
