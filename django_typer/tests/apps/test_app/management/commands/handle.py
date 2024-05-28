import typing as t
from django_typer import TyperCommand


class Command(TyperCommand):
    help = "Test various forms of handle override."

    def handle(self) -> str:
        return "handle"
