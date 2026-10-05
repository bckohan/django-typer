"""
A chained command with an initializer. The initializer must not switch chain
mode off, and chained subcommands may take positional arguments.
"""

from django_typer.management import TyperCommand, command, initialize


class Command(TyperCommand, chain=True):
    print_result = False

    @initialize()
    def init(self, prefix: str = ""):
        self.prefix = prefix

    @command()
    def echo(self, value: str):
        return f"{self.prefix}{value}"

    @command()
    def upper(self, value: str):
        return f"{self.prefix}{value.upper()}"
