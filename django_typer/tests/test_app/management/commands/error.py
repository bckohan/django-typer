import sys

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

from django.utils.translation import gettext_lazy as _
from typer import Option

from django_typer import TyperCommand


class Command(TyperCommand):
    help = "Test usage error behavior."

    def handle(
        self,
        arg1: int,
        flag1: bool = False,
        opt1: Annotated[int, Option(help="An option")] = 5,
    ):
        pass
