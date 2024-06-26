import os
import shutil
import sys
from pathlib import Path

import pytest
from django.test import TestCase

from tests.shellcompletion import (
    _DefaultCompleteTestCase,
    _InstalledScriptTestCase,
)


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash not available")
class BashShellTests(_DefaultCompleteTestCase, TestCase):
    shell = "bash"
    directory = Path("~/.bash_completions").expanduser()

    def set_environment(self, fd):
        # super().set_environment(fd)
        os.write(fd, f"export PATH={Path(sys.executable).parent}:$PATH\n".encode())
        os.write(
            fd,
            f'export DJANGO_SETTINGS_MODULE={os.environ["DJANGO_SETTINGS_MODULE"]}\n'.encode(),
        )
        os.write(fd, "source ~/.bashrc\n".encode())
        os.write(fd, "source .venv/bin/activate\n".encode())

    def verify_install(self, script=None):
        if not script:
            script = self.manage_script
        self.assertTrue((self.directory / f"{script}.sh").exists())

    def verify_remove(self, script=None):
        if not script:
            script = self.manage_script
        self.assertFalse((self.directory / f"{script}.sh").exists())


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash not available")
class BashExeShellTests(_InstalledScriptTestCase, BashShellTests):
    shell = "bash"
