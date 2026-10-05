import os
import shutil
import sys
from pathlib import Path
import typing as t

import pytest
from django.test import TestCase

from tests.shellcompletion import (
    _ScriptCompleteTestCase,
    _InstalledScriptCompleteTestCase,
    _WrappedScriptCompleteTestCase,
    wrapped_environment,
)


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash not available")
class BashTests(_ScriptCompleteTestCase, TestCase):
    shell = "bash"
    directory = Path("~/.bash_completions").expanduser()
    interactive_opt = "-i"
    tabs = "\t\t"

    environment = [
        "export DJANGO_SETTINGS_MODULE=tests.settings.completion",
        f"export PATH={Path(sys.executable).parent}:$PATH",
        "source ~/.bashrc",
        f"source {Path(sys.executable).absolute().parent / 'activate'}",
    ]

    def verify_install(self, script=None, directory: t.Optional[Path] = None):
        directory = directory or self.directory
        if not script:
            script = self.manage_script
        self.assertTrue((directory / f"{script}.sh").exists())

    def verify_remove(self, script=None, directory: t.Optional[Path] = None):
        directory = directory or self.directory
        if not script:
            script = self.manage_script
        self.assertFalse((directory / f"{script}.sh").exists())

    @pytest.mark.rich
    @pytest.mark.no_rich
    @pytest.mark.skip("Bash completer does not support rich output.")
    def test_rich_output(self): ...


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash not available")
class BashExeTests(_InstalledScriptCompleteTestCase, BashTests):
    shell = "bash"

    @pytest.mark.skipif(
        not bool(os.environ.get("ENABLE_CI_ONLY_TESTS", False)),
        reason="This test is dangerous to run on a user machine, "
        "because it may nuke their shell profile file.",
    )
    def test_no_bashrc_file(self):
        bashrc = ""
        try:
            if (Path.home() / ".bashrc").exists():
                bashrc = (Path.home() / ".bashrc").read_text()
                os.unlink(Path.home() / ".bashrc")
            self.test_shell_complete()
            os.unlink(Path.home() / ".bashrc")
            self.remove()
            self.verify_remove()
        finally:
            if bashrc:
                (Path.home() / ".bashrc").write_text(bashrc)

    def test_source_template(self):
        self.assertEqual(
            (
                Path(__file__).parent.parent.parent
                / "src/django_typer/templates/shell_complete/bash.sh"
            ).read_text(),
            self.get_completer().source_template,
        )

        self.assertEqual(
            (
                Path(__file__).parent.parent.parent
                / "src/django_typer/templates/shell_complete/zsh.sh"
            ).read_text(),
            self.get_completer(template="shell_complete/zsh.sh").source_template,
        )


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash not available")
class BashWrappedTests(_WrappedScriptCompleteTestCase, BashTests):
    """The manage script is run through a ``manage`` wrapper on the path."""

    shell = "bash"
    environment = wrapped_environment(BashTests.environment)
