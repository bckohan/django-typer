"""
Parsers derived from the deprecated django_typer.parsers.ParamType keep working.
"""

import typing as t
import warnings

import typer

from django_typer.management import TyperCommand

from django_typer.parsers import ParamType

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)

    class Upper(ParamType):
        name = "upper"

        def convert(self, value, param, ctx):
            if value == "bad":
                self.fail(f"{value} is not allowed.", param, ctx)
            return value.upper()


class Command(TyperCommand):
    def handle(self, value: t.Annotated[str, typer.Argument(parser=Upper())]):
        return value
