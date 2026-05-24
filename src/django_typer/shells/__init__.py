import collections.abc as cabc
import io
import sys
import typing as t
from abc import abstractmethod
from functools import cached_property
from importlib.resources import files
from pathlib import Path

from click.core import Command as ClickCommand
from click.shell_completion import CompletionItem, ShellComplete, add_completion_class
from django.template import Context, Engine
from django.template.backends.django import Template as DjangoTemplate
from django.template.base import Template as BaseTemplate
from django.template.loader import TemplateDoesNotExist, get_template
from django.utils.translation import gettext as _

__all__ = ["DjangoTyperShellCompleter", "register_completion_class"]

if t.TYPE_CHECKING:  # pragma: no cover
    from django_typer.management.commands.shellcompletion import (
        Command as ShellCompletion,
    )


class DjangoTyperShellCompleter(ShellComplete):
    """
    An extension to the click shell completion classes that provides a Django specific
    shell completion implementation. If you wish to support a new shell, you must
    derive from this class, implement all of the abstract methods, and register the
    class with
    :func:`~django_typer.management.commands.shellcompletion.register_completion_class`

    :param cli: The click command object to complete
    :param ctx_args: Additional context arguments to pass to the typer/click context of
        the management command being completed
    :param prog_name: The name of the command to complete
    :param complete_var: The name of the environment variable to pass the completion
        string (unused)
    :param command: The Django shellcompletion command
    :param command_str: The command string to complete
    :param command_args: The command arguments to complete
    :param template: The name of the shell completion script template
    :param color: Allow or disallow color and formatting in the completion output
    """

    template: str
    """
    The name of the shell completion function script template.
    """

    color: bool = False
    """
    By default, allow or disallow color and formatting in the completion output.
    """

    supports_scripts: bool = False
    """
    Does the shell support completions for uninstalled scripts? (i.e. not on the path)
    """

    complete_var: str = ""

    command: "ShellCompletion"
    command_str: str
    command_args: t.List[str]

    console = None  # type: ignore[var-annotated]

    rich_console = None  # type: ignore[var-annotated]
    console_buffer: io.StringIO

    color_default: bool = True

    def __init__(
        self,
        cli: t.Optional[ClickCommand] = None,
        ctx_args: cabc.MutableMapping[str, t.Any] = {},
        prog_name: str = "",
        complete_var: str = "",
        command: t.Optional["ShellCompletion"] = None,
        command_str: t.Optional[str] = None,
        command_args: t.Optional[t.List[str]] = None,
        template: t.Optional[str] = None,
        color: t.Optional[bool] = None,
        color_default: bool = color_default,
        **kwargs,
    ):
        # we don't always need the initialization parameters during completion
        self.prog_name = prog_name
        if command:
            self.command = command
        if command_str is not None:
            self.command_str = command_str
        if command_args is not None:
            self.command_args = command_args
        if template is not None:
            self.template = template
        if color is not None:
            self.color = color
        self.color_default = color_default

        self.console_buffer = io.StringIO()
        try:
            from rich.console import Console

            self.console = Console(
                # do not disable color output if not explicitly disabled
                color_system="auto" if self.color_default or self.color else None,
                force_terminal=True,
                file=command.stdout if command else None,  # type: ignore[arg-type]
                stderr=command.stderr if command else None,  # type: ignore[arg-type]
            )
            self.rich_console = Console(
                color_system="auto" if self.color else None,
                force_terminal=True,
                file=self.console_buffer,
                width=10**6,
            )
        except ImportError:
            pass

        if cli:
            super().__init__(
                cli=cli,
                ctx_args=ctx_args,
                complete_var=complete_var,
                prog_name=prog_name,
                **kwargs,
            )

    @property
    def source_template(self) -> str:  # type: ignore
        """
        The contents of the shell's completion script template.
        """
        return Path(self.load_template().origin.name).read_text()

    def get_completions(
        self, args: t.List[str], incomplete: str
    ) -> t.List[CompletionItem]:
        """
        Get the completions for the current command string and incomplete string.
        """
        if self.command.fallback:
            return self.command.fallback(args, incomplete)
        return super().get_completions(args[1:], incomplete)

    def get_completion_args(self) -> t.Tuple[t.List[str], str]:
        """
        Return the list of completion arguments and the incomplete string.
        """
        cwords = self.command_args
        if self.command_str and self.command_str[-1].isspace():
            # if the command string ends with a space, the incomplete string is empty
            cwords.append("")
        return (
            cwords[:-1],
            cwords[-1] if cwords else "",
        )

    def source_vars(self) -> t.Dict[str, t.Any]:
        """
        This returns the context that will be used to render the completion script
        template.

        From the base class we inherit the following variables:

        * **complete_func**: the name to use for the shell's completion function
        * **complete_var**: unused because we do not use environment variables
            to pass the completion string
        * **prog_name**: the name of the command to complete

        We add the following variables:

        * **manage_script**: the manage script object - will be either a string or a
          Path, if it is a Path it will be absolute and this indicates that the script
          is not installed on the path
        * **manage_script_name**: the name of the Django manage script
        * **python**: the path to the python interpreter that is running the
          shellcompletion command
        * **django_command**: the name of the Django shellcompletion command - you may
          change this to something other than 'shellcompletion' to provide custom
          complete logic
        * **color**: the color flag to pass to shellcompletion i.e. --(force|no)-color
        * **fallback**: the fallback option to pass to ``shellcompletion complete``
        * **is_installed**: whether or not the manage script is a command on the path
        * **shell**: the name of the shell
        """
        return {
            **super().source_vars(),
            "manage_script": self.command.manage_script,
            "manage_script_name": self.command.manage_script_name,
            "python": sys.executable,
            "django_command": self.command.__module__.split(".")[-1],
            "color": "--force-color"
            if self.color
            else "--no-color"
            if self.command.force_color
            else "",
            "fallback": f"--fallback={self.command.fallback_import}"
            if self.command.fallback
            else "",
            "is_installed": self.is_installed,
            "shell": self.name,
        }

    @cached_property
    def is_installed(self) -> bool:
        """
        Whether or not the manage script is a command on the path.
        """
        return not isinstance(self.command.manage_script, Path)

    def load_template(self) -> t.Union[BaseTemplate, DjangoTemplate]:
        """
        Return a compiled Template object for the completion script template.
        """
        try:
            return get_template(self.template)  # type: ignore
        except TemplateDoesNotExist:
            # handle case where templating is not configured to find our default
            # templates
            return Engine(
                dirs=[str(files("django_typer").joinpath("templates"))],
                libraries={
                    "default": "django.template.defaulttags",
                    "filter": "django.template.defaultfilters",
                },
            ).get_template(self.template)

    def source(self) -> str:
        """
        Render the completion script template to a string.
        """
        try:
            return self.load_template().render(self.source_vars())  # type: ignore
        except (AttributeError, TypeError, ValueError):
            # it is annoying that get_template() and DjangoEngine.get_template() return
            # different interfaces
            return self.load_template().render(Context(self.source_vars()))  # type: ignore

    @abstractmethod
    def install(self, prompt: bool = True) -> t.List[Path]:
        """
        Deriving classes must implement this method to install the completion script.

        This method should return the path to the installed script.

        :param prompt: If True, prompt the user for confirmation before installing
            the completion script.
        :return: The paths that were created or edited or None if the user declined
            installation or no changes were made.
        """

    @abstractmethod
    def uninstall(self):
        """
        Deriving classes must implement this method to uninstall the completion script.
        """

    @abstractmethod
    def get_user_profile(self) -> Path:
        """
        Most shells have a profile script that is sourced when the interactive shell
        starts. Deriving classes should implement this method to return the location
        of that script.
        """

    def prompt(
        self,
        source: str,
        file: Path,
        prompt: bool = True,
        start_line: int = 0,
    ) -> bool:
        """
        Prompt the user for confirmation before editing the file with the given
        source edits.

        :param source: The source string that will be written to the file.
        :param file: The path of the file that will be created or edited.
        :param prompt: Prompt toggle, if False, will not prompt the user and return True
        :param start_line: The line number the edit will start at.
        :return: True if the user confirmed the edit, False otherwise.
        """
        if not prompt:
            return True

        prompt_text = (
            _("Append the above contents to {file}?").format(file=file)
            if start_line
            else _("Create {file} with the above contents?").format(file=file)
        )
        if self.console:
            from rich.prompt import Confirm
            from rich.syntax import Syntax

            syntax = Syntax(
                source,
                self.name,
                theme="monokai",
                start_line=start_line,
                line_numbers=False,
            )
            self.console.print(syntax)
            return Confirm.ask(prompt_text, console=self.console)
        else:
            print(source)
            return input(prompt_text + " [y/N] ").lower() in {"y", "yes"}

    def process_rich_text(self, text: str) -> str:
        """
        Removes rich text markup from a string if color is disabled, otherwise it
        will render the rich markup to ansi control codes. If rich is not installed,
        none of this happens and the markup will be passed through as is.
        """
        if self.rich_console:
            if self.color:
                self.console_buffer.truncate(0)
                self.console_buffer.seek(0)
                self.rich_console.print(text, end="")
                return self.console_buffer.getvalue()
            else:
                return "".join(
                    segment.text for segment in self.rich_console.render(text)
                ).rstrip("\n")
        return text


_completers: t.Dict[str, t.Type[DjangoTyperShellCompleter]] = {}


def register_completion_class(cls: t.Type[DjangoTyperShellCompleter]) -> None:
    """
    Register a shell completion class for use with the Django shellcompletion command.
    """
    _completers[cls.name] = cls
    add_completion_class(cls)
