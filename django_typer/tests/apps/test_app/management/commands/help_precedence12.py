import json

from django.utils.translation import gettext_lazy as _

from .help_precedence10 import Command as BaseCommand


# should inherit docstring up from multiple levels up
class Command(BaseCommand):
    def handle(self, arg1: str, arg2: str, arg3: float = 0.5, arg4: int = 1):
        assert self.__class__ is Command
        opts = {"arg1": arg1, "arg2": arg2, "arg3": arg3, "arg4": arg4}
        return json.dumps(opts)
