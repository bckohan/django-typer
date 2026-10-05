import typing as t
from functools import reduce

from django.utils.translation import gettext_lazy as _
from typer import Argument, Option

from django_typer.management import Typer

app = Typer(
    help=_("A more complex command that defines a hierarchy of subcommands.")
)


# values returned from the commands are written to stdout
app.django_command.print_result = True

math_grp = Typer(help=_("Do some math at the given precision."))

app.add_typer(math_grp, name="math")


@math_grp.callback()
def math(
    self,
    precision: t.Annotated[
        int, Option(help=_("The number of decimal places to output."))
    ] = 2,
):
    self.precision = precision


@math_grp.command(help=_("Multiply the given numbers."))
def multiply(
    self,
    numbers: t.Annotated[
        t.List[float], Argument(help=_("The numbers to multiply"))
    ],
):
    return f"{reduce(lambda x, y: x * y, [1, *numbers]):.{self.precision}f}"


@math_grp.command()
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
