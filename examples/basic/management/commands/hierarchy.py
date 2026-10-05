import typing as t
from functools import reduce

from django.utils.translation import gettext_lazy as _
from typer import Argument, Option

from django_typer.management import TyperCommand, group


class Command(TyperCommand):
    # values returned from the commands are written to stdout
    print_result = True

    help = _("A more complex command that defines a hierarchy of subcommands.")

    precision = 2

    @group(help=_("Do some math at the given precision."))
    def math(
        self,
        precision: t.Annotated[
            int, Option(help=_("The number of decimal places to output."))
        ] = precision,
    ):
        self.precision = precision

    @math.command(help=_("Multiply the given numbers."))
    def multiply(
        self,
        numbers: t.Annotated[
            t.List[float], Argument(help=_("The numbers to multiply"))
        ],
    ):
        return f"{reduce(lambda x, y: x * y, [1, *numbers]):.{self.precision}f}"

    @math.command()
    def divide(
        self,
        numerator: t.Annotated[float, Argument(help=_("The numerator"))],
        denominator: t.Annotated[float, Argument(help=_("The denominator"))],
        floor: t.Annotated[bool, Option(help=_("Use floor division"))] = False,
    ):
        """
        Divide the given numbers.
        """
        if floor:
            return str(numerator // denominator)
        return f"{numerator / denominator:.{self.precision}f}"
