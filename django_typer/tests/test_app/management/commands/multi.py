from django_typer import TyperCommand, command
from typing import List
import json


class Command(TyperCommand):
    
    help = 'Test multiple sub-commands.'

    @command()
    def cmd1(self, files: List[str], flag1: bool = False):
        """
        A command that takes a list of files and a flag.
        """
        assert self.__class__ == Command
        return json.dumps({
            'files': files,
            'flag1': flag1
        })
    
    @command()
    def sum(self, numbers: List[float]):
        """
        Sum the given numbers.
        """
        assert self.__class__ == Command
        return str(sum(numbers))

    @command()
    def cmd3(self):
        """
        A command with no arguments.
        """
        assert self.__class__ == Command
        return json.dumps({})
