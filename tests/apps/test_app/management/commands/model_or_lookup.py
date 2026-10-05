from typing import Annotated
from uuid import UUID

import typer

from django_typer.management import TyperCommand
from django_typer.utils import model_parser_completer
from tests.apps.test_app.models import ShellCompleteTester


class Command(TyperCommand, rich_markup_mode="rich"):
    """
    Exercise ModelObjectParser(return_lookup_on_miss=True): fetch a row by a
    unique field, or fall through to the parsed lookup value when no row matches
    so the caller can create it.
    """

    def handle(
        self,
        email: Annotated[
            ShellCompleteTester,  # Typer rejects Model | str, annotate with the model
            typer.Argument(
                **model_parser_completer(
                    ShellCompleteTester,
                    lookup_field="email_field",
                    return_lookup_on_miss=True,
                )
            ),
        ],
        uuid: Annotated[
            ShellCompleteTester | None,
            typer.Option(
                **model_parser_completer(
                    ShellCompleteTester,
                    lookup_field="uuid_field",
                    return_lookup_on_miss=True,
                )
            ),
        ] = None,
    ):
        assert self.__class__ is Command
        if isinstance(email, ShellCompleteTester):
            result = f"found:{email.pk}"
        else:
            assert isinstance(email, str)
            result = f"new:{email}"
        if uuid is not None:
            if isinstance(uuid, ShellCompleteTester):
                result += f" found:{uuid.pk}"
            else:
                assert isinstance(uuid, UUID)
                result += f" new:{uuid}"
        return result
