"""
A collection of useful utilities.
"""

import inspect
import os
import sys
import typing as t
from datetime import timedelta
from functools import partial
from importlib.util import find_spec
from pathlib import Path
from threading import local
from types import MethodType, ModuleType

from django.db.models import Model
from django.db.models.query import QuerySet

from .completers.model import ModelObjectCompleter
from .config import manage_script, traceback_config
from .parsers.model import ModelObjectParser, ReturnType

# DO NOT IMPORT ANYTHING FROM TYPER HERE - SEE patch.py

__all__ = [
    "called_from_command_definition",
    "called_from_module",
    "detect_shell",
    "duration_iso_string",
    "get_current_command",
    "get_usage_script",
    "model_parser_completer",
    "parse_iso_duration",
    "register_command_plugins",
    "rich_installed",
    "with_typehint",
]


rich_installed = find_spec("rich") is not None and os.environ.get(
    "TYPER_USE_RICH", "true"
).lower() not in {"0", "false"}


def detect_shell(max_depth: int = 10) -> tuple[str, str]:
    """
    Detect the current shell.

    :raises ShellDetectionFailure: If the shell cannot be detected
    :return: A tuple of the shell name and the shell command
    """
    from shellingham import ShellDetectionFailure
    from shellingham import detect_shell as _detect_shell

    try:
        return _detect_shell(max_depth=max_depth)
    except ShellDetectionFailure:
        login_shell = os.environ.get("SHELL", "")
        if login_shell:
            return (os.path.basename(login_shell).lower(), login_shell)
        raise


def get_usage_script(script: str | None = None) -> Path | str:
    """
    Return the script name if it is on the path or the absolute path to the script
    if it is not.

    The name is used when invoking it from the shell would run the given script. This
    is true when the name resolves on the path to the script itself, or when the
    script was launched through an absolute path (i.e. the shell resolved it from the
    path, possibly through a shim or wrapper of the same name). A script invoked
    through an explicit relative path is only reported by name if it is the same file
    the path resolves to.

    If ``script`` is not given and ``DT_MANAGE_SCRIPT`` is set, in the settings module or
    failing that in the environment, it is returned verbatim in lieu of any detection.

    :param script: The script name to check. If None the current script is used.
    :return: The script name or the relative path to the script from cwd.
    """
    import shutil

    if not script:
        override = manage_script()
        if override:
            return override

    cmd_pth = Path(script or sys.argv[0])
    on_path: str | Path | None = shutil.which(cmd_pth.name)
    on_path = on_path and Path(on_path)
    # which() may return a relative path if PATH has relative entries and on windows
    # it searches the cwd first, returning .\name - a cwd hit is not "on the path"
    if on_path and on_path.is_absolute():
        if cmd_pth.is_absolute() or not cmd_pth.is_file():
            return cmd_pth.name
        try:
            if on_path.samefile(cmd_pth):
                return cmd_pth.name
        except OSError:  # pragma: no cover
            pass
    try:
        return cmd_pth.absolute().relative_to(Path(os.getcwd()))
    except ValueError:
        return cmd_pth.absolute()


_command_context = local()


def get_current_command() -> t.Optional["TyperCommand"]:  # type: ignore  # noqa: F821
    """
    Returns the current typer command. This can be used as a way to
    access the current command object from anywhere if we are executing
    inside of one from higher on the stack. We primarily need this because certain
    monkey patches are required in typer code - namely for enabling/disabling
    color based on configured parameters.

    This function is thread safe.

    This is analogous to click's get_current_context but for
    command execution.

    :return: The current typer command or None if there is no active command.
    """
    try:
        return t.cast("TyperCommand", _command_context.stack[-1])  # type: ignore  # noqa: F821
    except (AttributeError, IndexError):
        pass
    return None


T = t.TypeVar("T")  # pylint: disable=C0103


def with_typehint(baseclass: type[T]) -> type[T]:
    """
    Type hinting mixin inheritance is really annoying. The current
    canonical way is to use Protocols but this is prohibitive when
    the super classes already exist and are extensive. All we're
    trying to do is let our type checker know about super() methods
    etc - this is a simple way to do that.
    """
    if t.TYPE_CHECKING:
        return baseclass  # pragma: no cover
    return object  # type: ignore


_command_plugins: dict[str, list[ModuleType]] = {}


def register_command_plugins(package: ModuleType, commands: list[str] | None = None):
    """
    Register a command plugin for the given command within the given package.

    For example, use this in your AppConfig's ready() method:

    .. code-block:: python

        from django.apps import AppConfig
        from django_typer.utils import register_command_plugins


        class MyAppConfig(AppConfig):
            name = "myapp"

            def ready(self):
                from .management import plugins

                register_command_plugins(plugins)


    :param package: The package the command extension module resides in
    :param commands: The names of the commands/modules, if not provided, all modules
        in the package will be registered as plugins
    """
    import pkgutil

    commands = commands or [
        module[1].split(".")[-1]
        for module in pkgutil.iter_modules(package.__path__, f"{package.__name__}.")
    ]
    for command in commands:
        _command_plugins.setdefault(command, [])
        if package not in _command_plugins[command]:
            _command_plugins[command].append(package)


def _load_command_plugins(command: str) -> int:
    """
    Load any plugins for the given command by loading the registered
    modules in registration order.

    :param command: The name of the command
    :return: The number of plugins loaded.
    """
    plugins = _command_plugins.get(command, [])
    if plugins:
        import importlib

        for ext_pkg in reversed(plugins):
            try:
                importlib.import_module(f"{ext_pkg.__name__}.{command}")
            except (ImportError, ModuleNotFoundError) as err:
                raise ValueError(
                    f"No extension module was found for command {command} in "
                    f"{ext_pkg.__path__}."
                ) from err
        # we only want to do this once
        del _command_plugins[command]
    return len(plugins)


def _check_call_frame(frame_name: str, look_back=1) -> bool:
    """
    Returns True if the stack frame one frame above where this function has the given
    name.

    :param frame_name: The name of the frame to check for
    """
    frame = inspect.currentframe()
    for _ in range(look_back + 1):
        if not frame:
            break
        frame = frame.f_back
    if frame:
        return frame.f_code.co_name == frame_name
    return False


called_from_module = partial(_check_call_frame, "<module>")
called_from_command_definition = partial(_check_call_frame, "Command")


def is_method(
    func_or_params: t.Callable[..., t.Any] | list[str] | None,
) -> bool | None:
    """
    This logic is used to to determine if a function should be bound as a method
    or not. Right now django-typer will treat module scope functions as methods
    when binding to command classes if they have a first argument named 'self'.

    :param func: The function to check or a list of parameter names, or None
    :return: True if the function should be considered a method, False if not and None
        if undetermined.
    """
    # ##############
    # Remove when python 3.9 support is dropped
    func_or_params = getattr(func_or_params, "__func__", func_or_params)
    ##############
    if func_or_params:
        params = (
            list(inspect.signature(func_or_params).parameters)
            if callable(func_or_params)
            else func_or_params
        )
        if params:
            return params[0] == "self"
        return isinstance(func_or_params, MethodType)
    return None


def accepts_var_kwargs(func: t.Callable[..., t.Any]) -> bool:
    """
    Determines if the given function accepts variable keyword arguments.
    """
    for param in reversed(list(inspect.signature(func).parameters.values())):
        return param.kind is inspect.Parameter.VAR_KEYWORD
    return False


def accepted_kwargs(
    func: t.Callable[..., t.Any], kwargs: dict[str, t.Any]
) -> dict[str, t.Any]:
    """
    Return the named keyword arguments that are accepted by the given function.
    """
    if accepts_var_kwargs(func):
        return kwargs
    param_names = set(inspect.signature(func).parameters.keys())
    return {k: v for k, v in kwargs.items() if k in param_names}


def get_win_shell() -> str:
    """
    The way installed python scripts are wrapped on Windows means shellingham will
    detect cmd.exe as the shell. This function will attempt to detect the correct shell,
    usually either powershell (<=v5) or pwsh (>=v6).

    :raises ShellDetectionFailure: If the shell cannot be detected
    :return: The name of the shell, either 'powershell' or 'pwsh'
    """
    import json
    import shutil
    import subprocess  # nosec B404

    from shellingham import ShellDetectionFailure

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh:
        try:
            ps_command = """
            $parent = Get-CimInstance -Query "SELECT * FROM Win32_Process WHERE ProcessId = {pid}";
            $parentPid = $parent.ParentProcessId;
            $parentInfo = Get-CimInstance -Query "SELECT * FROM Win32_Process WHERE ProcessId = $parentPid";
            $parentInfo | Select-Object Name, ProcessId | ConvertTo-Json -Depth 1
            """
            pid = os.getpid()
            while True:
                result = subprocess.run(  # nosec B603
                    [pwsh, "-NoProfile", "-Command", ps_command.format(pid=pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip()
                if not result:
                    break
                process = json.loads(result)
                if "pwsh" in process.get("Name", ""):
                    return "pwsh"
                elif "powershell" in process.get("Name", ""):
                    return "powershell"
                pid = process["ProcessId"]

        except Exception as e:  # pragma: no cover
            raise ShellDetectionFailure("Unable to detect windows shell") from e

    raise ShellDetectionFailure("Unable to detect windows shell")


def parse_iso_duration(duration: str) -> tuple[timedelta, str | None]:
    """
    Progressively parse an ISO8601 duration type - can be a partial
    duration string. If it is a partial duration string with an ambiguous
    trailing number, the number will be returned as the second value of the
    tuple.

    .. note::
        We use a subset of ISO8601, the supported markers are Y, M, W, D, H, M, S.
        Years are approximated as 365 days and months as 30 days.

    :return: A tuple of the parsed duration and the ambiguous trailing number
    """
    import re

    original = duration
    duration = duration.upper()

    sign = -1 if duration.startswith("-") else 1
    duration = duration.lstrip("-").lstrip("+").lstrip("P")

    ambiguous: str | None = None

    class Incomplete(Exception):
        value: str

        def __init__(self, value: str):
            self.value = value

    def eat(markers: t.Sequence[str], interpret=lambda x: (int(x), True)) -> int:
        nonlocal duration
        if duration:
            match = re.match(r"(\d+)(.)?", duration)
            if match and match.group(2) in markers:
                duration = duration[match.end() :]
                return interpret(match.group(1))[0]
            if match and not match.group(2):
                duration = duration[match.end() :]
                value, ambig = interpret(match.group(1))
                if not ambig:
                    return value
                raise Incomplete(match.group(1))
        return 0

    years = 0
    months = 0
    weeks = 0
    days = 0
    hours = 0
    minutes = 0
    seconds = 0
    microseconds = 0

    # date portion: PnYnMnWnD
    try:
        years = eat(("Y",))
        months = eat(("M",))
        weeks = eat(("W",))
        days = eat(("D",))
    except Incomplete as incomplete:
        ambiguous = incomplete.value

    duration = duration.lstrip("T")

    try:
        hours = eat(("H",))
        minutes = eat(("M",))
        seconds = eat((".", "S"))
        microseconds = eat(("S",), lambda x: (int(f"{x:0<6}"), len(x) < 6))
    except Incomplete as incomplete:
        ambiguous = incomplete.value

    if duration:
        # if the string was a valid full or partial duration all characters
        # should have been consumed
        raise ValueError(f"Invalid ISO 8601 duration format: {original}")

    total_days = years * 365 + months * 30 + weeks * 7 + days

    return sign * timedelta(
        days=total_days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        microseconds=microseconds,
    ), ambiguous


def duration_iso_string(duration: timedelta) -> str:
    """
    Return an ISO8601 duration string from a timedelta. This differs from
    the Django implementation in that zeros are elided.
    """
    if not duration:
        return "PT0S"
    sign = "-" if duration < timedelta() else ""
    if sign:
        duration *= -1
    days = duration.days
    hours, seconds = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    day_str = ""
    if days:
        day_str = f"{abs(days)}D"
    if hours:
        time_parts.append(f"{abs(hours)}H")
    if minutes:
        time_parts.append(f"{abs(minutes)}M")
    if seconds or duration.microseconds:
        if duration.microseconds:
            time_parts.append(f"{abs(seconds)}.{abs(duration.microseconds):0>6}S")
        else:
            time_parts.append(f"{abs(seconds)}S")
    time_str = ""
    if time_parts:
        time_str = "T" + "".join(time_parts)
    return f"{sign}P{day_str}{time_str}"


def model_parser_completer(
    model_or_qry: type[Model] | QuerySet,
    lookup_field: str | None = None,
    case_insensitive: bool = False,
    help_field: str | None = ModelObjectCompleter.help_field,
    query: ModelObjectCompleter.QueryBuilder | None = None,
    limit: int | None = ModelObjectCompleter.limit,
    distinct: bool = ModelObjectCompleter.distinct,
    on_error: ModelObjectParser.error_handler | None = ModelObjectParser.on_error,
    order_by: str | t.Sequence[str] | None = None,
    return_type: ReturnType = ModelObjectParser.return_type,
    return_lookup_on_miss: bool = ModelObjectParser.return_lookup_on_miss,
) -> dict[str, t.Any]:
    """
    A factory function that returns a dictionary that can be used to specify
    a parser and completer for a typer.Option or typer.Argument. This is a
    convenience function that can be used to specify the parser and completer
    for a model object in one go.

    .. code-block:: python

        def handle(
            self,
            obj: t.Annotated[
                ModelClass,
                typer.Argument(
                    **model_parser_completer(ModelClass, 'field_name'),
                    help=_("Fetch objects by their field_names.")
                ),
            ]
        ):
            ...


    :param model_or_qry: the model class or QuerySet to use for lookup
    :param lookup_field: the field to use for lookup, by default the primary key
    :param case_insensitive: whether to perform case insensitive lookups and
        completions, default: False
    :param help_field: the field to use for help output in completion suggestions,
        by default no help will be provided
    :param query: a callable that will be used to build the query for completions,
        by default the query will be reasonably determined by the field type
    :param limit: the maximum number of completions to return, default: 50
    :param distinct: whether to filter out already provided parameters in the
        completion suggestions, True by default
    :param on_error: a callable that will be called if the parser lookup fails
        to produce a matching object - by default a CommandError will be raised.
        Whatever it returns becomes the parsed value.
    :param return_type: An enumeration switch to return either a model instance,
        queryset or model field value type.
    :param return_lookup_on_miss: return the (coerced) lookup value instead of
        erroring when no matching object exists, default: False
    """
    return {
        "parser": ModelObjectParser(
            model_or_qry if inspect.isclass(model_or_qry) else model_or_qry.model,  # type: ignore
            lookup_field,
            case_insensitive=case_insensitive,
            on_error=on_error,
            return_type=return_type,
            return_lookup_on_miss=return_lookup_on_miss,
        ),
        "shell_complete": ModelObjectCompleter(
            model_or_qry,
            lookup_field,
            case_insensitive=case_insensitive,
            help_field=help_field,
            query=query,
            limit=limit,
            distinct=distinct,
            order_by=order_by,
        ),
    }


def install_traceback(tb_config: dict[str, t.Any] | None = None):
    from .config import use_rich_tracebacks

    if not use_rich_tracebacks():
        return

    import rich
    from rich import traceback
    from typer import main as typer_main

    tb_config = tb_config or traceback_config()

    # install rich tracebacks if we've been configured to do so (default)
    no_color = "NO_COLOR" in os.environ
    force_color = "FORCE_COLOR" in os.environ
    traceback.install(
        console=tb_config.pop(
            "console",
            (
                rich.console.Console(
                    stderr=True,
                    no_color=no_color,
                    force_terminal=(
                        False if no_color else force_color if force_color else None
                    ),
                )
                if no_color or force_color
                else None
            ),
        ),
        **{
            param: value
            for param, value in tb_config.items()
            if param in set(inspect.signature(traceback.install).parameters.keys())
        },
    )
    # typer installs its own exception hook and it falls back to the sys hook -
    # depending on when typer was imported it may have the original fallback system hook
    # or our installed rich one - we patch it here to make sure!
    typer_main._original_except_hook = sys.excepthook
