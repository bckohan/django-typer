"""
Tests for the documented way to get help output and tab completion working when the
manage script is run through another command, e.g. a ``just manage`` recipe,
``poetry run manage`` or ``uv run manage``: a one word wrapper script on the path that
forwards to the wrapped invocation, plus the ``DT_MANAGE_SCRIPT`` setting naming it.

https://github.com/django-commons/django-typer/issues/190
https://github.com/django-commons/django-typer/issues/191
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import override_settings

from django_typer.management import get_command
from django_typer.management.commands.shellcompletion import Command as ShellCompletion
from tests.utils import manage_py

WRAPPER = "manage"
WRAPPED_SETTINGS = "tests.settings.completion_wrapped"
UNWRAPPED_SETTINGS = "tests.settings.completion"


def make_wrapper(directory: Path, name: str = WRAPPER) -> Path:
    """
    Create a wrapper script in ``directory`` that forwards to ``python manage.py``, the
    way a ``just manage`` recipe or ``poetry run manage`` would.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        wrapper = directory / f"{name}.cmd"
        wrapper.write_text(f'@"{sys.executable}" "{manage_py}" %*\r\n')
    else:
        wrapper = directory / name
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{manage_py}" "$@"\n')
        wrapper.chmod(wrapper.stat().st_mode | 0o111)
    return wrapper


def run_wrapped(
    wrapper: Path, *args: str, settings: str = WRAPPED_SETTINGS
) -> subprocess.CompletedProcess:
    """Run the wrapper by name with its directory on the path."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": settings,
        "PATH": f"{wrapper.parent}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    if platform.system() == "Windows":
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [str(wrapper), *args],
        env=env,
        capture_output=True,
        text=True,
        cwd=manage_py.parent,
    )


def test_wrapper_help_usage(tmp_path):
    """
    Help printed through the wrapper names the wrapper, but only when
    DT_MANAGE_SCRIPT says so - otherwise the launched script is what gets detected.
    """
    wrapper = make_wrapper(tmp_path / "bin")

    result = run_wrapped(wrapper, "completion", "--help", settings=UNWRAPPED_SETTINGS)
    assert result.returncode == 0, result.stderr
    assert f"Usage: {WRAPPER} completion" not in result.stdout
    assert "manage.py completion" in result.stdout

    result = run_wrapped(wrapper, "completion", "--help")
    assert result.returncode == 0, result.stderr
    assert f"Usage: {WRAPPER} completion" in result.stdout


def test_wrapper_shellcompletion_complete(tmp_path):
    """
    The completion scripts call ``<manage script> shellcompletion complete`` with the
    typed command line. Through the wrapper, the wrapper name is recognized as the
    manage script and stripped before the command is resolved.
    """
    wrapper = make_wrapper(tmp_path / "bin")
    result = run_wrapped(
        wrapper, "shellcompletion", "--shell", "bash", "complete", f"{WRAPPER} complet"
    )
    assert result.returncode == 0, result.stderr
    assert "completion" in result.stdout


@pytest.mark.parametrize(
    "shell,registration",
    [
        ("bash", "-F {func} manage"),
        ("zsh", "compdef {func} manage"),
        ("fish", "complete -c manage"),
        ("pwsh", "-CommandName manage"),
    ],
)
def test_wrapper_completion_source(tmp_path, monkeypatch, shell, registration):
    """
    With DT_MANAGE_SCRIPT set the shellcompletion command treats the wrapper as a
    command installed on the path and renders a completion script that registers it,
    rather than a script path installation (which fish and powershell refuse).
    """
    wrapper = make_wrapper(tmp_path / "bin")
    monkeypatch.setenv("PATH", f"{wrapper.parent}{os.pathsep}{os.environ['PATH']}")
    # the process the wrapper launches sees the real script as sys.argv[0]
    monkeypatch.setattr(sys, "argv", [str(manage_py), "shellcompletion", "install"])

    command = get_command("shellcompletion", ShellCompletion)
    command.init(shell=shell)

    command.manage_script = None  # type: ignore[assignment]
    assert isinstance(command.manage_script, Path)
    assert not command.shell_class(
        prog_name=command.manage_script_name, command=command
    ).is_installed

    with override_settings(DT_MANAGE_SCRIPT=WRAPPER):
        command.manage_script = None  # type: ignore[assignment]
        assert command.manage_script == WRAPPER
        completer = command.shell_class(
            prog_name=command.manage_script_name, command=command
        )
        assert completer.is_installed
        assert registration.format(func=completer.func_name) in completer.source()
