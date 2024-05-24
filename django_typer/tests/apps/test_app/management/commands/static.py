import json
from typing import List

from django_typer import TyperCommand, initialize, command, group


class Command(TyperCommand):
    help = "Test staticmethods."

    @initialize(invoke_without_command=True)
    @staticmethod
    def init():
        return "init"

    @command()
    @staticmethod
    def cmd1():
        return "cmd1"

    @command()
    @staticmethod
    def cmd2():
        return "cmd2"

    @group(invoke_without_command=True)
    @staticmethod
    def grp1():
        return "grp1"

    @group(invoke_without_command=True)
    @staticmethod
    def grp2():
        return "grp2"

    @grp1.command()
    @staticmethod
    def grp1_cmd():
        return "grp1_cmd"

    @grp2.command()
    @staticmethod
    def grp2_cmd():
        return "grp2_cmd"
