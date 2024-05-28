import typing as t
from django_typer import TyperCommand, command
from .handle import Command as Handle


class Command(Handle):
    help = "Test various forms of handle override."

    def handle(self) -> str:
        return "handle3"
