import typing as t

from django.utils.translation import gettext_lazy as _
from typer import Argument, Option

from django_typer import TyperCommand
from django_typer.parsers import ModelObjectParser
from tests.apps.examples.polls.models import Question as Poll


class Command(TyperCommand):
    help = "Closes the specified poll for voting"

    def handle(
        self,
        polls: t.Annotated[
            t.List[Poll],
            Argument(
                parser=ModelObjectParser(Poll),
                help=_("The database IDs of the poll(s) to close."),
            ),
        ],
        delete: t.Annotated[
            bool,
            Option(
                "--delete",  # we can also get rid of that unnecessary --no-delete flag
                help=_("Delete poll instead of closing it."),
            ),
        ] = False,
    ):
        """
        Closes the specified poll for voting.


        As mentioned in the last section, helps can also
        be set in the docstring
        """
        for poll in polls:
            poll.opened = False
            poll.save()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully closed poll "{poll.id}"')
            )
            if delete:
                poll.delete()
