import typing as t

from django_typer import TyperCommand, command


class Command(TyperCommand, rich_markup_mode="markdown", chain=True):

    suppressed_base_arguments = [
        "--verbosity",
        "--traceback",
        "--no-color",
        "--force-color",
        "--skip_checks",
        "--settings",
        "--pythonpath",
        "--version",
    ]

    @command()
    def command1(self, option: t.Optional[str] = None):
        """This is a *markdown* help string"""
        print(f"command1")
        return option

    @command()
    def command2(self, option: t.Optional[str] = None):
        """This is a *markdown* help string"""
        print(f"command2")
        return option
