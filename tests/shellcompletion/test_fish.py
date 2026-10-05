import shutil
import sys
from pathlib import Path
import typing as t

import pytest
from django.test import TestCase
from django.core.management import CommandError

from tests.shellcompletion import (
    _ScriptCompleteTestCase,
    _InstalledScriptCompleteTestCase,
    flat_scrub,
    _WrappedScriptCompleteTestCase,
    wrapped_environment,
)


class _FishMixin:
    shell = "fish"
    profile: Path
    tabs = "\t"
    directory = Path("~/.config/fish/completions").expanduser()
    interactive_opt = "--interactive"
    # Fish disables interactive features (incl. completion) without a
    # proper controlling TTY -- it prints "warning: No TTY for interactive
    # shell (tcgetpgrp failed)" and degrades into a non-interactive mode.
    requires_controlling_terminal = True

    environment = [
        f"set -x DJANGO_SETTINGS_MODULE 'tests.settings.completion'",
        f"source {Path(sys.executable).absolute().parent / 'activate.fish'}",
    ]

    def _render_output(self, output: str) -> str:
        # Fish's pager draws candidate menus and then erases them with
        # cursor-up + \x1b[J before redrawing the prompt. pyte's screen
        # simulation loses the candidates because they've been erased on
        # screen. flat_scrub keeps the transmitted bytes so we can assert
        # against what fish actually emitted.
        return flat_scrub(output)

    def verify_install(self, script=None, directory: t.Optional[Path] = None):
        directory = directory or self.directory
        if not script:
            script = self.manage_script
        self.assertTrue((self.directory / f"{script}.fish").exists())

    def verify_remove(self, script=None, directory: t.Optional[Path] = None):
        directory = directory or self.directory
        if not script:
            script = self.manage_script
        self.assertFalse((self.directory / f"{script}.fish").exists())


@pytest.mark.skipif(shutil.which("fish") is None, reason="Fish not available")
class FishShellTests(_FishMixin, _ScriptCompleteTestCase, TestCase):
    def test_shell_complete(self):
        with self.assertRaises(CommandError):
            self.install()

    @pytest.mark.rich
    @pytest.mark.no_rich
    @pytest.mark.skip(reason="fish does not support script installations")
    def test_rich_output(self): ...

    @pytest.mark.rich
    @pytest.mark.skip(reason="fish does not support script installations")
    def test_no_rich_output(self): ...

    @pytest.mark.skip(reason="fish does not support script installations")
    def test_settings_pass_through(self): ...

    @pytest.mark.skip(reason="fish does not support script installations")
    def test_pythonpath_pass_through(self): ...

    @pytest.mark.skip(reason="fish does not support script installations")
    def test_fallback(self): ...

    @pytest.mark.skip(reason="fish does not support script installations")
    def test_reentrant_install_uninstall(self): ...

    @pytest.mark.skip(reason="fish does not support script installations")
    def test_path_completion(self): ...


@pytest.mark.skipif(shutil.which("fish") is None, reason="Fish not available")
class FishExeShellTests(_FishMixin, _InstalledScriptCompleteTestCase, TestCase):
    @pytest.mark.rich
    @pytest.mark.no_rich
    @pytest.mark.skip(reason="fish does not support ansi control sequences")
    def test_rich_output(self): ...

    @pytest.mark.rich
    @pytest.mark.skip(reason="fish does not support ansi control sequences")
    def test_no_rich_output(self): ...


@pytest.mark.skipif(shutil.which("fish") is None, reason="Fish not available")
class FishWrappedShellTests(_FishMixin, _WrappedScriptCompleteTestCase, TestCase):
    """The manage script is run through a ``manage`` wrapper on the path."""

    environment = wrapped_environment(_FishMixin.environment)
