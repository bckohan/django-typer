"""
Help type labels for parameters with parsers.
"""

import typing as t
from enum import Enum

import typer

from django_typer.management import TyperCommand


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


def named(value):
    return value


class CallableParser:
    def __call__(self, value):
        return value


class NamedCallableParser(CallableParser):
    name = "named_instance"


class Command(TyperCommand):
    def handle(
        self,
        func: t.Annotated[str, typer.Option(parser=named)] = "",
        funcs: t.Annotated[list[str] | None, typer.Option(parser=named)] = None,
        instance: t.Annotated[str, typer.Option(parser=NamedCallableParser())] = "",
        unnamed: t.Annotated[str, typer.Option(parser=CallableParser())] = "",
        anon: t.Annotated[str, typer.Option(parser=lambda v: v)] = "",
        pair: t.Annotated[tuple[str, str], typer.Option(parser=named)] = ("a", "b"),
        color: t.Annotated[Color, typer.Option(parser=Color)] = Color.RED,
    ):
        pass
