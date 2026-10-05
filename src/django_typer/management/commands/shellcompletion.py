"""
The shellcompletion command is a Django_ management command that installs and removes
shellcompletion scripts for supported shells (bash, fish, zsh, powershell). This
command is also the entry point for running the completion logic and can be used to
debug completer code.

.. typer:: django_typer.management.commands.shellcompletion.Command:typer_app
    :prog: django-admin shellcompletion
    :width: 80
    :convert-png: latex

:func:`~django_typer.management.commands.shellcompletion.Command.install` invokes
typer's shell completion installation logic, but does have to patch the installed
scripts. This is because there is only one installation for all Django_ management
commands, not each individual command. The completion logic here will failover to
Django_'s builtin autocomplete if the command in question is not a
:class:`~django_typer.management.TyperCommand`. To promote compatibility with other
management command libraries or custom completion logic, a fallback completion function
can also be specified.
"""

import contextlib
import io
import os
import platform
import re
import sys
import typing as t
from pathlib import Path
from types import ModuleType

from django.core.management import CommandError, ManagementUtility
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from shellingham import ShellDetectionFailure
from typer import Argument, Option
from typer._click.core import ParameterSource
from typer._click.globals import get_current_context
from typer._click.shell_completion import CompletionItem, split_arg_string

from django_typer.completers import these_strings
from django_typer.completers.path import import_paths
from django_typer.management import (
    TyperCommand,
    command,
    get_command,
    get_typer_command,
    initialize,
)
from django_typer.shells import _completers
from django_typer.types import COMMON_PANEL
from django_typer.utils import detect_shell, get_usage_script, get_win_shell

DETECTED_SHELL = None

try:
    DETECTED_SHELL = detect_shell()[0]
except (ShellDetectionFailure, RuntimeError):  # pragma: no cover
    pass


def django_autocomplete(args: list[str], incomplete: str) -> list[CompletionItem]:
    # spoof bash environment variables
    # the first one is lopped off, so we insert a placeholder 0
    args = ["0", *args]
    if args[-1] != incomplete:
        args.append(incomplete)
    else:  # pragma: no cover
        pass
    os.environ["COMP_WORDS"] = " ".join(args)
    os.environ["COMP_CWORD"] = str(args.index(incomplete))
    os.environ["DJANGO_AUTO_COMPLETE"] = "1"
    dj_manager = ManagementUtility(args)
    capture_completions = io.StringIO()
    with contextlib.redirect_stdout(capture_completions):
        try:
            dj_manager.autocomplete()
        except SystemExit:
            pass
    return [
        CompletionItem(item) for item in capture_completions.getvalue().split() if item
    ]


class Command(TyperCommand):
    """
    This command installs autocompletion for the current shell. This command uses the
    typer/click autocompletion scripts to generate the autocompletion items, but monkey
    patches the scripts to invoke our bundled shell complete script which fails over to
    the django autocomplete function when the command being completed is not a
    :class:`~django_typer.management.TyperCommand`. When the django autocomplete
    function is used we also wrap it so that it works for any supported click/typer
    shell, not just bash.

    We also provide a remove command to easily remove the installed script.

    Great pains are taken to use the upstream dependency's shell completion logic. This
    is so advances and additional shell support implemented upstream should just work.
    However, it would be possible to add support for new shells here using the pluggable
    logic that click provides. It is probably a better idea however to add support for
    new shells at the typer level.

    Shell autocompletion can be brittle with every shell having its own quirks and
    nuances. We make a good faith effort here to support all the shells that typer/click
    support, but there can easily be system specific configuration issues that prevent
    this from working. In those cases users should refer to the online documentation for
    their specific shell to troubleshoot.
    """

    help = t.cast(str, _("Install autocompletion for the current shell."))

    # completions are returned, this setting prints them (new in 4.0)
    print_result = True

    # disable the system checks - no reason to run these for this one-off command
    requires_system_checks = ()
    requires_migrations_checks = False

    # remove unnecessary django command base parameters - these just clutter the help
    # never mutated - matches BaseCommand's declaration in django-stubs, which
    # is not a ClassVar
    suppressed_base_arguments = {  # noqa: RUF012
        "version",
        "skip_checks",
        "verbosity",
    }

    _shell: str | None = DETECTED_SHELL
    shell_module: ModuleType

    ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    _fallback: t.Callable[[list[str], str], list[CompletionItem]] | None = None
    _manage_script: str | Path | None = None

    color_default: bool = True

    @property
    def fallback(
        self,
    ) -> t.Callable[[list[str], str], list[CompletionItem]] | None:
        return self._fallback

    @fallback.setter
    def fallback(self, fb: str | None):
        try:
            self._fallback = import_string(fb) if fb else django_autocomplete
        except ImportError as err:
            raise CommandError(
                f"Unable to import fallback completion function: {err}"
            ) from err

    @property
    def fallback_import(self) -> str | None:
        return (
            f"{self.fallback.__module__}.{self.fallback.__name__}"
            if self.fallback
            else None
        )

    @property
    def manage_script(self) -> str | Path:
        """
        Returns the name of the manage command as a string if it is available as a
        command on the user path. If it is a script that is not available as a command
        on the path it will return an absolute Path object to the script.
        """
        # We do not want to hardcode this as 'manage.py' because users are free to
        # rename and implement their own manage scripts! The safest way to do this is
        # therefore to fetch the name of the script that invoked the shellcompletion
        # command and determine if that script is available on the user's path or not.

        # Most shell's completion infrastructure works best if the commands are
        # available on the path. However, it is common for Django development to be done
        # in a virtual environment with a manage.py script being invoked directly as a
        # script. Completion should work in this case as well, but it does complicate
        # the installation for some shell's so we must first figure out which mode we
        # are in.
        if not self._manage_script:
            self.manage_script = None  # type: ignore
        return self._manage_script  # type: ignore

    @manage_script.setter
    def manage_script(self, script: str | None):
        self._manage_script = get_usage_script(script)
        if isinstance(self._manage_script, Path):
            self._manage_script = self._manage_script.absolute()

    @property
    def manage_script_name(self) -> str:
        """
        Get the name of the manage script as a command available from the shell's path.
        """
        if isinstance(self.manage_script, Path):
            return self.manage_script.name
        return self.manage_script

    @property
    def shell(self) -> str:
        """
        Get the active shell. If not explicitly set, it first tries to find the shell
        in the environment variable shell complete scripts set and failing that it will
        try to autodetect the shell.
        """
        assert self._shell
        return self._shell

    @shell.setter
    def shell(self, shell: str | None):
        """Set the shell to install autocompletion for."""
        if shell:
            self._shell = shell
        if self._shell is None:
            raise CommandError(
                "Unable to detect shell. Please specify the shell to install or "
                "remove autocompletion for."
            )
        elif self._shell == "cmd" and platform.system() == "Windows":
            try:
                self._shell = get_win_shell()
            except ShellDetectionFailure:  # pragma: no cover
                pass

    @property
    def shell_class(self):
        try:
            return _completers[self.shell]
        except KeyError as err:
            raise CommandError(f"Unsupported shell: {self.shell}") from err

    @initialize()
    def init(
        self,
        shell: t.Annotated[
            str | None,
            Option(
                "--shell",
                help=t.cast(
                    str,
                    _("The shell to use."),
                ),
                metavar="SHELL",
                shell_complete=these_strings(_completers.keys()),
            ),
        ] = DETECTED_SHELL,
        no_color: t.Annotated[
            bool | None,
            Option(
                "--no-color",
                help=t.cast(
                    str,
                    _(
                        "Filter terminal formatting control sequences out of completion"
                        " text."
                    ),
                ),
                rich_help_panel=COMMON_PANEL,
            ),
        ] = None,
        force_color: t.Annotated[
            bool,
            Option(
                "--force-color",
                help=t.cast(
                    str,
                    _(
                        "Allow terminal formatting control sequences in completion "
                        "text."
                    ),
                ),
                rich_help_panel=COMMON_PANEL,
            ),
        ] = False,
    ) -> "Command":
        self.shell = shell  # type: ignore[assignment]
        assert self.shell
        self.force_color = force_color
        self.no_color = (not self.shell_class.color) if no_color is None else no_color
        if self.force_color:
            self.no_color = False
        ctx = get_current_context(silent=True)
        self.color_default = (
            (
                ctx.get_parameter_source("no_color") is ParameterSource.DEFAULT
                and ctx.get_parameter_source("force_color") is ParameterSource.DEFAULT
            )
            if ctx
            else False
        )
        return self

    @command(
        help=t.cast(str, _("Install autocompletion for the current or given shell."))
    )
    def install(
        self,
        manage_script: t.Annotated[
            str | None,
            Option(
                help=t.cast(
                    str,
                    _(
                        "The name of the django manage script to install autocompletion"
                        " for if different than the script used to invoke this command."
                    ),
                )
            ),
        ] = None,
        fallback: t.Annotated[
            str | None,
            Option(
                help=t.cast(
                    str,
                    _(
                        "The python import path to a fallback complete function to use "
                        "when the completion command is not a TyperCommand."
                    ),
                ),
                shell_complete=import_paths,
            ),
        ] = None,
        template: t.Annotated[
            str | None,
            Option(
                help=t.cast(
                    str,
                    _(
                        "The name of the template to use for the shell completion "
                        "script."
                    ),
                )
                # todo - add template name completer - see django-render-static
            ),
        ] = None,
        prompt: t.Annotated[
            bool,
            Option(
                "--no-prompt",
                help=t.cast(
                    str,
                    _("Do not ask for conformation before editing dotfiles."),
                ),
            ),
        ] = True,
    ) -> list[Path] | None:
        """
        Install autocompletion for the given shell. If the shell is not specified, it
        will try to detect the shell. If the shell is not detected, it will fail.

        We run the upstream typer installation routines, with some augmentation.

        .. typer:: django_typer.management.commands.shellcompletion.Command:typer_app:install
            :prog: django-admin shellcompletion install
            :width: 85
            :convert-png: latex

        Returns the list of edited and/or created paths or None if no edits were made.
        """
        self.fallback = fallback  # type: ignore[assignment]
        self.manage_script = manage_script  # type: ignore[assignment]
        if isinstance(self.manage_script, Path):
            if not self.shell_class.supports_scripts:
                raise CommandError(
                    f"Shell {self.shell} does not support autocompletion for scripts "
                    f"that are not installed on the path. You must create an entry "
                    f"point for {self.manage_script_name}. See "
                    f"https://setuptools.pypa.io/en/latest/userguide/entry_point.html."
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"It is not recommended to install tab completion for a script "
                        f"that is not installed on the path. This can be brittle. You "
                        f"should create an entry point for {self.manage_script_name}. "
                        f"See https://setuptools.pypa.io/en/latest/userguide/entry_point.html."
                    )
                )

        install_paths = self.shell_class(
            prog_name=str(manage_script or self.manage_script_name),
            command=self,
            template=template,
            color=not self.no_color or self.force_color,
            color_default=self.color_default,
        ).install(prompt=prompt)
        if install_paths:
            self.stdout.write(
                self.style.SUCCESS(
                    _("Installed autocompletion for {shell}").format(shell=self.shell)  # nosec B604
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    t.cast(str, _("Aborted shell completion installation."))
                )
            )
        return install_paths or None

    @command(
        help=t.cast(str, _("Uninstall autocompletion for the current or given shell."))
    )
    def uninstall(
        self,
        manage_script: t.Annotated[
            str | None,
            Option(
                help=t.cast(
                    str,
                    _(
                        "The name of the django manage script to remove shell "
                        "completion for if different than the script used to invoke "
                        "this command."
                    ),
                )
            ),
        ] = None,
    ):
        """
        Remove the autocompletion for the given shell. If the shell is not specified,
        it will try to detect the shell. If the shell is not detected, it will fail.

        Since the installation routine is upstream we first run install to determine
        where the completion script is installed and then we remove it.

        .. typer:: django_typer.management.commands.shellcompletion.Command:typer_app:uninstall
            :prog: django-admin shellcompletion uninstall
            :width: 80
            :convert-png: latex

        """
        self.manage_script = manage_script  # type: ignore[assignment]
        self.shell_class(
            prog_name=str(manage_script or self.manage_script_name),
            command=self,
            color=not self.no_color or self.force_color,
            color_default=self.color_default,
        ).uninstall()
        self.stdout.write(
            self.style.WARNING(f"Uninstalled autocompletion for {self.shell}.")
        )

    @command(
        help=t.cast(str, _("Generate autocompletion for command string.")), hidden=False
    )
    def complete(
        self,
        command: t.Annotated[
            str,
            Argument(
                help=t.cast(
                    str, _("The command string to generate completion suggestions for.")
                ),
            ),
        ] = "",
        cursor: t.Annotated[
            int | None, Argument(help=t.cast(str, _("The cursor position.")))
        ] = None,
        fallback: t.Annotated[
            str | None,
            Option(
                help=t.cast(
                    str,
                    _(
                        "The python import path to a fallback complete function to use "
                        "when the completion command is not a TyperCommand. By default,"
                        " the builtin django autocomplete function is used."
                    ),
                ),
                shell_complete=import_paths,
            ),
        ] = None,
    ):
        """
        We implement the shell complete generation script as a Django command because
        the Django environment needs to be bootstrapped for it to work. This also allows
        us to test completion logic in a platform agnostic way.

        .. tip::

            This command is super useful for debugging shell_complete logic. For example
            to enter into the debugger, we could set a breakpoint in our
            ``shell_complete`` function for the option parameter and then run the
            following command:

            .. code-block:: bash

                $ ./manage.py shellcompletion complete "./manage.py your_command --option "

        .. typer:: django_typer.management.commands.shellcompletion.Command:typer_app:complete
            :prog: django-admin shellcompletion complete
            :width: 80
            :convert-png: latex
        """
        command = command[:cursor] if cursor is not None else command
        args = split_arg_string(command.replace("\\", "\\\\"))
        if args:
            try:
                # lop the manage script off the front if it's there
                if (
                    args[0] == self.manage_script_name
                    or Path(args[0]).resolve() == Path(sys.argv[0]).resolve()
                ):
                    args = args[1:]
            except (TypeError, ValueError, OSError):  # pragma: no cover
                pass

        def get_completion() -> str:
            if args:
                # we first need to figure out which command is being invoked
                # but we cant be sure which index the command name is at so
                # we try to fetch each in order and assume the first arg
                # that resolves to a command is the command
                cmd = None
                cmd_idx = -1
                try:
                    while cmd is None:
                        cmd_idx += 1
                        try:
                            cmd = get_command(args[cmd_idx])
                        except CommandError:
                            pass
                except IndexError:
                    if command.endswith(" "):
                        # unrecognized command
                        return ""
                    # fall through to fallback

                if isinstance(cmd, TyperCommand):
                    # this will exit out so no return is needed here
                    return self.shell_class(
                        cli=get_typer_command(cmd.typer_app),
                        ctx_args={"django_command": cmd},
                        prog_name="",
                        complete_var="",
                        command=self,
                        command_str=command,
                        command_args=args,
                        color=not self.no_color or self.force_color,
                        color_default=self.color_default,
                    ).complete()

            # only try to set the fallback if we have to use it
            self.fallback = fallback  # type: ignore[assignment]
            return self.shell_class(
                command=self,
                command_str=command,
                command_args=args,
                color=not self.no_color or self.force_color,
                color_default=self.color_default,
            ).complete()

        def strip_color(text: str) -> str:
            """
            Strip ANSI color codes from a string.
            """
            if self.no_color:
                return self.ANSI_ESCAPE_RE.sub("", text)
            return text

        env = os.environ.copy()
        try:
            return strip_color(get_completion())
        finally:
            os.environ.clear()
            os.environ.update(env)
