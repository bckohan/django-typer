"""
A command the command tree cache tests register new commands on at runtime.
Nothing else should depend on the exact set of commands it ends up with.
"""

from django_typer.management import TyperCommand, command, group, initialize


class Command(TyperCommand):
    @initialize()
    def init(self, verbose: bool = False):
        self.verbose = verbose

    @command()
    def cmd1(self):
        return "cmd1"

    @group()
    def grp(self):
        pass

    @grp.command()
    def sub1(self):
        return "sub1"
