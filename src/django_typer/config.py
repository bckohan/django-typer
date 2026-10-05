import os
import typing as t

from django.conf import settings

TRUTHY = {"1", "true", "t", "yes", "y", "on"}


def traceback_config() -> dict[str, t.Any]:
    """
    Fetch the rich traceback installation parameters from our settings. By default
    rich tracebacks are on with show_locals = True. If the config is set to False
    or None rich tracebacks will not be installed even if the library is present.

    This allows us to have a common traceback configuration for all commands. If rich
    tracebacks are managed separately this setting can also be switched off.
    """
    default = {"show_locals": False}
    cfg = getattr(settings, "DT_RICH_TRACEBACK_CONFIG", default) or default
    if cfg is True:
        return default
    return cfg


def show_locals() -> bool | None:
    """
    Return the show_locals parameter from the rich traceback configuration.
    """
    return traceback_config().get("show_locals", None)


def use_rich_tracebacks() -> bool:
    """
    Return true if rich tracebacks should be installed, False otherwise.
    """
    from .utils import rich_installed

    cfg = getattr(settings, "DT_RICH_TRACEBACK_CONFIG", {"show_locals": False})
    return rich_installed and (
        (isinstance(cfg, dict) and not cfg.get("no_install", False)) or cfg is True
    )


def manage_script() -> str | None:
    """
    Return the ``DT_MANAGE_SCRIPT`` setting if it is set, falling back to the
    environment variable of the same name. When set, this name is used verbatim as
    the program name in command help and as the command name shell completions are
    installed for, instead of detecting it from the invoking script.
    """
    name = getattr(settings, "DT_MANAGE_SCRIPT", os.environ.get("DT_MANAGE_SCRIPT"))
    return str(name) if name else None


def print_result() -> bool:
    """
    The project wide default for whether truthy values returned from commands are
    written to stdout. Off unless the ``DT_PRINT_RESULT`` setting is true, falling
    back to the environment variable of the same name (``1``, ``true``, ``yes`` or
    ``on``, case insensitive). A command may override it with its ``print_result``
    class field.
    """
    value = getattr(settings, "DT_PRINT_RESULT", os.environ.get("DT_PRINT_RESULT", ""))
    if isinstance(value, str):
        return value.strip().lower() in TRUTHY
    return bool(value)
