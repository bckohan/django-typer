"""
Common types for command line argument specification.
"""

import sys
from pathlib import Path
from typing import Annotated, cast

from django.core.management import CommandError
from django.utils.translation import gettext_lazy as _
from typer import Option

from .completers.path import directories, import_paths

COMMON_PANEL = "Django"


def print_version(context, _, value):
    """
    A callback to run the :meth:`~django.core.management.BaseCommand.get_version` routine
    of the command when --version is specified.
    """
    if value:
        context.django_command.stdout.write(context.django_command.get_version())
        sys.exit()


def set_no_color(context, _, value):
    """
    If the value was provided set it on the command.
    """
    if value:
        context.django_command.no_color = value
        if context.params.get("force_color", False):
            raise CommandError(
                "The --no-color and --force-color options can't be used together."
            )
    return value


def set_force_color(context, _, value):
    """
    If the value was provided set it on the command.
    """
    if value:
        context.django_command.force_color = value
    return value


def show_locals(context, param, _):
    from typer._click.core import ParameterSource

    if context.get_parameter_source(param.name) is not ParameterSource.DEFAULT:
        from .config import traceback_config
        from .utils import install_traceback

        show = param.name == "show_locals"
        install_traceback({**traceback_config(), "show_locals": show})
        # Typer renders uncaught exceptions with its own hook using the app level
        # setting, so keep that in step with the flag as well. This callback only
        # ever runs on django-typer's own context, which always carries the
        # command (access the app on the class - on the instance it is a proxy).
        type(context.django_command).typer_app.pretty_exceptions_show_locals = show


Version = Annotated[
    bool,
    Option(
        "--version",
        help=cast(str, _("Show program's version number and exit.")),
        callback=print_version,
        is_eager=True,
        rich_help_panel=COMMON_PANEL,
    ),
]
"""
The type hint for the :meth:`--version <django.core.management.BaseCommand.get_version>`
option.

The ``--version`` option is included by default and behaves the same as on
:class:`~django.core.management.BaseCommand`.
"""


Verbosity = Annotated[
    int,
    Option(
        help=cast(
            str,
            _(
                "Verbosity level; 0=minimal output, 1=normal output, "
                "2=verbose output, 3=very verbose output"
            ),
        ),
        show_choices=True,
        min=0,
        max=3,
        rich_help_panel=COMMON_PANEL,
    ),
]
"""
The type hint for the :option:`--verbosity` option.
:class:`~django_typer.management.TyperCommand` does not include the verbosity option by
default, but it can be added to the command like so if needed.

.. code-block:: python

        from django_typer.types import Verbosity

        def handle(self, verbosity: Verbosity = 1):
            ...
"""

Settings = Annotated[
    str,
    Option(
        help=cast(
            str,
            _(
                "The Python path to a settings module, e.g. "
                '"myproject.settings.main". If this isn\'t provided, the '
                "DJANGO_SETTINGS_MODULE environment variable will be used."
            ),
        ),
        rich_help_panel=COMMON_PANEL,
        shell_complete=import_paths,
        show_default=False,
    ),
]
"""
The type hint for the :option:`--settings` option.

The :option:`--settings` option is included by default and behaves the same as on
:class:`~django.core.management.BaseCommand` use it to specify or override the settings
module to use.
"""


PythonPath = Annotated[
    Path | None,
    Option(
        help=cast(
            str,
            _(
                "A directory to add to the Python path, e.g. "
                '"/home/djangoprojects/myproject".'
            ),
        ),
        rich_help_panel=COMMON_PANEL,
        shell_complete=directories,
        show_default=False,
    ),
]
"""
The type hint for the :option:`--pythonpath` option.

The :option:`--pythonpath` option is included by default and behaves the same as on
:class:`~django.core.management.BaseCommand` use it to specify a directory to add to the
Python sys path.
"""


Traceback = Annotated[
    bool,
    Option(
        "--traceback",
        help=cast(str, _("Raise on CommandError exceptions")),
        rich_help_panel=COMMON_PANEL,
    ),
]
"""
The type hint for the :option:`--traceback` option.

The :option:`--traceback` option is included by default and behaves the same as on
:class:`~django.core.management.BaseCommand` use it to allow
:class:`~django.core.management.CommandError` exceptions to propagate out of the command
and produce a stack trace.
"""


ShowLocals = Annotated[
    bool,
    Option(
        "--show-locals",
        help=cast(
            str,
            _("Print local variables in tracebacks."),
        ),
        callback=show_locals,
        is_eager=True,
        rich_help_panel=COMMON_PANEL,
        show_default=False,
    ),
]
"""
A toggle to turn on exception traceback local variable rendering in rich
tracebacks.
"""

HideLocals = Annotated[
    bool,
    Option(
        "--hide-locals",
        help=cast(str, _("Hide local variables in tracebacks.")),
        callback=show_locals,
        is_eager=True,
        rich_help_panel=COMMON_PANEL,
        show_default=False,
    ),
]
"""
A toggle to turn off exception traceback local variable rendering in rich
tracebacks.
"""

NoColor = Annotated[
    bool,
    Option(
        "--no-color",
        help=cast(str, _("Don't colorize the command output.")),
        is_eager=True,
        callback=set_no_color,
        rich_help_panel=COMMON_PANEL,
    ),
]
"""
The type hint for the :option:`--no-color` option.

The :option:`--no-color` option is included by default and behaves the same as on
:class:`~django.core.management.BaseCommand` use it to force disable colorization of the
command. You can check the supplied value of :option:`--no-color` by checking the
no_color attribute of the command instance.
"""

ForceColor = Annotated[
    bool,
    Option(
        "--force-color",
        help=cast(str, _("Force colorization of the command output.")),
        is_eager=True,
        callback=set_force_color,
        rich_help_panel=COMMON_PANEL,
    ),
]
"""
The type hint for the :option:`--force-color` option.

The :option:`--force-color` option is included by default and behaves the same as on
:class:`~django.core.management.BaseCommand` use it to force colorization of the
command. You can check the supplied value of :option:`--force-color` by checking the
force_color attribute of the command instance.
"""

SkipChecks = Annotated[
    bool,
    Option(
        "--skip-checks",
        help=cast(str, _("Skip system checks.")),
        rich_help_panel=COMMON_PANEL,
    ),
]
"""
The type hint for the :option:`--skip-checks` option.

The :option:`--skip-checks` option is included by default and behaves the same as on
:class:`~django.core.management.BaseCommand` use it to skip system checks.
"""
