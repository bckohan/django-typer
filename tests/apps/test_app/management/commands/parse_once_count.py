"""
A custom parser on the root command must run once - see issue #210.
"""

import typing as t

import typer

from django_typer.management import TyperCommand

conversions = 0


def counting_parser(value: str) -> str:
    global conversions
    conversions += 1
    return value.upper()


class Command(TyperCommand):
    def handle(self, value: t.Annotated[str, typer.Argument(parser=counting_parser)]):
        return f"{value} {conversions}"
