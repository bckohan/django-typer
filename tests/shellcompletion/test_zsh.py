import glob
import shutil
from pathlib import Path
import typing as t

import pytest
from django.test import TestCase, override_settings
import sys
import os
import platform

from tests.shellcompletion import (
    _ScriptCompleteTestCase,
    _InstalledScriptCompleteTestCase,
    _WrappedScriptCompleteTestCase,
    wrapped_environment,
)


@pytest.mark.skipif(shutil.which("zsh") is None, reason="Z-Shell not available")
class ZshTests(_ScriptCompleteTestCase, TestCase):
    shell = "zsh"
    directory = Path("~/.zfunc").expanduser()
    interactive_opt = "-i"
    tabs = "\t\t\t"

    environment = [
        f"PATH={Path(sys.executable).parent}:$PATH",
        f"DJANGO_SETTINGS_MODULE=tests.settings.completion",
    ]

    def setUp(self):
        # Force a fresh compinit on every shell spawn. A stale
        # ~/.zcompdump (which persists across test methods on macOS CI
        # runners, where a single $HOME is shared for the whole job)
        # can cause a newly-installed completion function -- e.g. the
        # one rewritten by test_fallback with a --fallback arg -- to
        # be missed entirely on the first TAB. Costs ~200-500ms per
        # test for the full compinit security check, no risk of
        # regressing other tests.
        for f in glob.glob(str(Path.home() / ".zcompdump*")):
            try:
                os.unlink(f)
            except OSError:
                pass
        super().setUp()

    def verify_install(self, script=None, directory: t.Optional[Path] = None):
        directory = directory or self.directory
        if not script:
            script = self.manage_script
        self.assertTrue((directory / f"_{script}").exists())

    def verify_remove(self, script=None, directory: t.Optional[Path] = None):
        directory = directory or self.directory
        if not script:
            script = self.manage_script
        self.assertFalse((directory / f"_{script}").exists())


@pytest.mark.skipif(shutil.which("zsh") is None, reason="Z-Shell not available")
class ZshExeTests(_InstalledScriptCompleteTestCase, ZshTests, TestCase):
    shell = "zsh"

    @pytest.mark.skipif(
        not bool(os.environ.get("ENABLE_CI_ONLY_TESTS", False)),
        reason="This test is dangerous to run on a user machine, "
        "because it may nuke their shell profile file.",
    )
    def test_no_zshrc_file(self):
        zshrc = ""
        try:
            if (Path.home() / ".zshrc").exists():
                zshrc = (Path.home() / ".zshrc").read_text()
                os.unlink(Path.home() / ".zshrc")
            self.test_shell_complete()
            os.unlink(Path.home() / ".zshrc")
            self.remove()
            self.verify_remove()
        finally:
            if zshrc:
                (Path.home() / ".zshrc").write_text(zshrc)

    @override_settings(TEMPLATES=[])
    def test_no_template_config(self):
        self.test_shell_complete()

    if platform.system() != "Windows":

        def test_prompt_install(self, env={}, directory=None):
            zdot_dir = Path(__file__).parent / "zdotdir"
            try:
                zdot_dir.mkdir(exist_ok=True)
                super().test_prompt_install(
                    env={"ZDOTDIR": str(zdot_dir.absolute())},
                    directory=zdot_dir / ".zfunc",
                )
            finally:
                if zdot_dir.exists():
                    shutil.rmtree(zdot_dir)


@pytest.mark.skipif(shutil.which("zsh") is None, reason="Z-Shell not available")
class ZshWrappedTests(_WrappedScriptCompleteTestCase, ZshTests, TestCase):
    """The manage script is run through a ``manage`` wrapper on the path."""

    shell = "zsh"
    environment = wrapped_environment(ZshTests.environment)

    if platform.system() != "Windows":

        def test_prompt_install(self, env={}, directory=None):
            zdot_dir = Path(__file__).parent / "zdotdir"
            try:
                zdot_dir.mkdir(exist_ok=True)
                super().test_prompt_install(
                    env={"ZDOTDIR": str(zdot_dir.absolute()), **env},
                    directory=zdot_dir / ".zfunc",
                )
            finally:
                if zdot_dir.exists():
                    shutil.rmtree(zdot_dir)
