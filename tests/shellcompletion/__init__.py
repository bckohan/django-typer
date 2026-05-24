import os
import re
import select
import struct
import subprocess
import sys
import time
import typing as t
from pathlib import Path
import pytest
from functools import cached_property
import re
import subprocess
import platform
from django.test import TestCase

from django_typer.utils import detect_shell

from django_typer.management import get_command
from django_typer.management.commands.shellcompletion import Command as ShellCompletion
from django_typer.shells import DjangoTyperShellCompleter
from django_typer.utils import with_typehint
from ..utils import rich_installed, manage_py

default_shell = None

try:
    default_shell = detect_shell()[0]
except Exception:
    pass


def scrub(output: str) -> str:
    """Scrub control code characters and ansi escape sequences for terminal colors from output"""
    return (
        re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", output, flags=re.IGNORECASE)
        .replace("\t", "")
        .replace("\x08", "")
    )


_SENTINEL_PREFIX = "__DJT_SENTINEL_"


def _wait_for(
    read_fn: t.Callable[[], str],
    sentinel: t.Optional[str] = None,
    quiet_period: float = 0.25,
    timeout: float = 15.0,
) -> str:
    """
    Poll ``read_fn`` until either:
      * ``sentinel`` (if provided) has appeared and no new bytes arrived
        for ``quiet_period`` seconds, OR
      * no sentinel was given and no new bytes arrived for ``quiet_period``
        seconds (pure quiescence wait).

    Always bounded by ``timeout``. Returns the full buffer.
    """
    buf = ""
    start = time.time()
    last_data = time.time()
    seen = sentinel is None
    while time.time() - start < timeout:
        data = read_fn()
        if data:
            buf += data
            last_data = time.time()
            if sentinel is not None and not seen and sentinel in buf:
                seen = True
        elif seen and (time.time() - last_data) >= quiet_period:
            return buf
        else:
            time.sleep(0.02)
    return buf


class _CompleteTestCase(with_typehint(TestCase)):
    shell: str
    manage_script: str
    launch_script: str

    interactive_opt: t.Optional[str] = None

    environment: t.List[str] = []

    tabs: str

    # Per-instance shell process state (None when no shell is running).
    _shell_state: t.Any = None
    _sentinel_counter: int = 0

    @cached_property
    def command(self) -> ShellCompletion:
        cmd = get_command("shellcompletion", ShellCompletion)
        cmd.init(shell=self.shell)
        return cmd

    def get_completer(self, **kwargs) -> DjangoTyperShellCompleter:
        return self.command.shell_class(
            **{"prog_name": self.manage_script, "command": self.command, **kwargs}
        )

    def setUp(self):
        self._shell_state = None
        self._sentinel_counter = 0
        self.remove()
        super().setUp()

    def tearDown(self):
        self.remove()
        self._invalidate_shell()
        super().tearDown()

    def _next_sentinel(self) -> str:
        self._sentinel_counter += 1
        return f"{_SENTINEL_PREFIX}{self._sentinel_counter}__"

    def _invalidate_shell(self) -> None:
        """Tear down the long-running shell, if any.

        Called whenever shell state (profile, registered completers) may
        have changed and a fresh shell process is required.
        """
        state = self._shell_state
        self._shell_state = None
        if state is None:
            return
        if platform.system() == "Windows":
            try:
                state.close()
            except Exception:
                pass
        else:
            master_fd, slave_fd, process = state
            # Close the fds first so the shell sees EOF on stdin and exits
            # cleanly.  This avoids relying on SIGTERM, which some shells
            # (notably interactive zsh) ignore.
            for fd in (master_fd, slave_fd):
                try:
                    os.close(fd)
                except Exception:
                    pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=2)
                except Exception:
                    pass

    def verify_install(self, script=None, directory: t.Optional[Path] = None):
        pass

    def verify_remove(self, script=None, directory: t.Optional[Path] = None):
        pass

    def install(
        self,
        script=None,
        force_color=False,
        no_color=None,
        fallback=None,
        no_shell=False,
        prompt=False,
    ):
        if not script:
            script = self.manage_script
        init_kwargs = {"force_color": force_color, "no_color": no_color}
        kwargs = {"prompt": prompt}
        if script:
            kwargs["manage_script"] = script
        if self.shell and not no_shell:
            init_kwargs["shell"] = self.shell
        if fallback:
            kwargs["fallback"] = fallback
        self.command.init(**init_kwargs)
        self.command.install(**kwargs)
        self.verify_install(script=script)

    def remove(self, script=None):
        if not script:
            script = self.manage_script
        kwargs = {}
        if script:
            kwargs["manage_script"] = script
        if self.shell:
            self.command.init(shell=self.shell)
        self.command.uninstall(**kwargs)
        self.get_completions("ping")  # just to reinit shell
        self.verify_remove(script=script)

    # ------------------------------------------------------------------ #
    # PTY plumbing
    #
    # Each get_completions() spawns a fresh shell, sources the environment,
    # types the command + TAB, captures output, and tears the shell down.
    # The previous implementation also spawned per-call but relied on fixed
    # time.sleep() calls (3s for the first prompt + 2s after env + 2s after
    # TAB).  Here those are replaced with sentinel-based waits (after each
    # silent command we echo a unique marker and read until it appears) and
    # pure quiescence waits after TAB (where no sentinel is possible).
    # ------------------------------------------------------------------ #

    if platform.system() == "Windows":

        def _read_shell(self) -> str:
            return self._shell_state.read() if self._shell_state is not None else ""

        def _write_shell(self, data: str) -> None:
            assert self._shell_state is not None
            self._shell_state.write(data)

        def _ensure_shell(self) -> None:
            if self._shell_state is not None:
                return
            import winpty

            assert self.shell

            self._shell_state = winpty.PTY(256, 512)
            self._shell_state.spawn(
                self.shell, *([self.interactive_opt] if self.interactive_opt else [])
            )

            # Wait for first prompt by echoing a sentinel; the shell will
            # process it once the prompt is ready.
            sentinel = self._next_sentinel()
            self._write_shell(f"echo {sentinel}{os.linesep}")
            _wait_for(self._read_shell, sentinel=sentinel, timeout=20.0)

            for line in self.environment:
                self._write_shell(f"{line}{os.linesep}")
                sentinel = self._next_sentinel()
                self._write_shell(f"echo {sentinel}{os.linesep}")
                _wait_for(self._read_shell, sentinel=sentinel, timeout=15.0)

    else:

        def _read_shell(self) -> str:
            if self._shell_state is None:
                return ""
            master_fd = self._shell_state[0]
            rlist, _, _ = select.select([master_fd], [], [], 0)
            if not rlist:
                return ""
            try:
                data = os.read(master_fd, 1024 * 1024)
            except (BlockingIOError, OSError):
                return ""
            if not data:
                return ""
            return data.decode(errors="replace")

        def _write_shell(self, data: str) -> None:
            assert self._shell_state is not None
            os.write(self._shell_state[0], data.encode())

        def _ensure_shell(self) -> None:
            if self._shell_state is not None:
                return
            import fcntl
            import termios
            import pty

            master_fd, slave_fd = pty.openpty()
            os.set_blocking(slave_fd, False)
            os.set_blocking(master_fd, False)
            win_size = struct.pack("HHHH", 24, 80, 0, 0)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, win_size)

            shell = self.shell or detect_shell()[0]
            process = subprocess.Popen(
                [shell, *([self.interactive_opt] if self.interactive_opt else [])],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
            )
            self._shell_state = (master_fd, slave_fd, process)

            sentinel = self._next_sentinel()
            self._write_shell(f"echo {sentinel}{os.linesep}")
            _wait_for(self._read_shell, sentinel=sentinel, timeout=15.0)

            for line in self.environment:
                self._write_shell(f"{line}{os.linesep}")
                sentinel = self._next_sentinel()
                self._write_shell(f"echo {sentinel}{os.linesep}")
                _wait_for(self._read_shell, sentinel=sentinel, timeout=10.0)

    def get_completions(self, *cmds: str, scrub_output=True, position=0) -> str:
        # Ensure a clean shell for every call; previous test interactions
        # (typed but un-Entered text, completion menus, prediction overlays)
        # could otherwise contaminate the captured output.
        self._invalidate_shell()
        self._ensure_shell()
        try:
            self._write_shell(" ".join(cmds))
            if position > 0:
                self._write_shell("\x1b[C" * position)
            elif position < 0:
                self._write_shell("\x1b[D" * abs(position))
            self._write_shell(self.tabs)

            # TAB triggers an inline completion display -- no sentinel is
            # possible, so wait for the output to settle.  The quiet_period
            # must be long enough to bridge the Django-bootstrap gap between
            # the shell echoing our typed text and the completion subprocess
            # actually producing output (the registered completer shells out
            # to `django-admin shellcompletion complete`, which loads Django
            # -- typically 1-2s on a cold interpreter).
            output = _wait_for(self._read_shell, quiet_period=2.0, timeout=15.0)
        finally:
            self._invalidate_shell()

        return scrub(output) if scrub_output else output

    def run_app_completion(self):
        completions = self.get_completions(self.launch_script, "completion", " ")
        self.assertIn("django_typer", completions)
        self.assertIn("admin", completions)
        self.assertIn("auth", completions)
        self.assertIn("contenttypes", completions)
        self.assertIn("messages", completions)
        self.assertIn("sessions", completions)
        self.assertIn("staticfiles", completions)

    def run_bad_command_completion(self):
        completions = self.get_completions(
            self.launch_script, "completion_does_not_exist", " "
        )
        self.assertTrue("Exception" not in completions)
        self.assertTrue("traceback" not in completions)

    def run_command_completion(self):
        completions = self.get_completions(self.launch_script, "complet")
        self.assertIn("completion", completions)
        completions = self.get_completions(self.launch_script, " ")
        self.assertIn("changepassword", completions)
        self.assertIn("check", completions)
        self.assertIn("dumpdata", completions)
        self.assertIn("completion", completions)
        self.assertIn("collectstatic", completions)

    def run_rich_option_completion(self, rich_output_expected: bool):
        completions = self.get_completions(
            self.launch_script, "completion", "--cmd", scrub_output=False
        )
        self.assertIn("--cmd", completions)
        self.assertIn("--cmd-first", completions)
        self.assertIn("--cmd-dup", completions)
        if not rich_installed:
            if self.shell not in ["powershell", "pwsh"]:
                self.assertIn("[bold]", completions)
                self.assertIn("[/bold]", completions)
                self.assertIn("[reverse]", completions)
                self.assertIn("[/reverse]", completions)
                self.assertIn("[underline]", completions)
                self.assertIn("[/underline]", completions)
                self.assertIn("[yellow]", completions)
                self.assertIn("[/yellow]", completions)
            else:
                self.assertTrue(
                    "[bold]" in completions
                    or "[/bold]" in completions
                    or "[reverse]" in completions
                    or "[/reverse]" in completions
                    or "[underline]" in completions
                    or "[/underline]" in completions
                    or "[yellow]" in completions
                    or "[/yellow]" in completions
                )
        elif rich_output_expected:
            # \x1b[0m and \x1b[m are the same
            if self.shell not in ["powershell", "pwsh"]:
                # exempt powershell from this because it filters the codes anyway
                self.assertIn("\x1b[7mcommands\x1b[", completions)
                self.assertIn("\x1b[4;33mcommands\x1b[", completions)
                self.assertIn("\x1b[1mname\x1b[", completions)
        else:
            self.assertNotIn("\x1b[7mcommands\x1b[", completions)
            self.assertNotIn("\x1b[4;33mcommands\x1b[", completions)
            self.assertNotIn("\x1b[1mimport path\x1b[", completions)
            self.assertNotIn("\x1b[1mname\x1b[", completions)

    def test_shell_complete(self):
        with self.assertRaises(AssertionError):
            self.run_app_completion()
        self.install()
        self.run_app_completion()
        self.run_bad_command_completion()
        self.run_command_completion()
        self.remove()
        with self.assertRaises(AssertionError):
            self.run_app_completion()
        self.install()

    def test_fallback(self):
        self.remove()
        self.install(fallback="tests.fallback.custom_fallback")
        completions = self.get_completions(self.launch_script, " ")
        self.assertIn("custom_fallback", completions)

    @pytest.mark.rich
    @pytest.mark.no_rich
    def test_rich_output(self):
        self.install(force_color=True)
        self.run_rich_option_completion(rich_output_expected=True)

    @pytest.mark.rich
    @pytest.mark.skipif(not rich_installed, reason="Rich not installed")
    def test_no_rich_output(self):
        self.install(no_color=True)
        self.run_rich_option_completion(rich_output_expected=False)

    def test_settings_pass_through(self):
        # https://github.com/django-commons/django-typer/issues/68
        self.install()
        completions = self.get_completions(self.launch_script, "app_labels", " ")
        self.assertNotIn("django_typer", completions)
        completions = self.get_completions(
            self.launch_script,
            "app_labels",
            "--settings",
            "tests.settings.examples",
            " ",
        )
        self.assertIn("django_typer", completions)
        completions = self.get_completions(
            self.launch_script,
            "app_labels",
            "--settings=tests.settings.examples",
            " ",
        )
        self.assertIn("django_typer", completions)

    def test_pythonpath_pass_through(self):
        # https://github.com/django-commons/django-typer/issues/68
        self.install()
        completions = self.get_completions(
            self.launch_script, "python_path", "--options", " "
        )
        self.assertNotIn("working", completions)
        completions = self.get_completions(
            self.launch_script,
            "python_path",
            "--pythonpath",
            "tests/off_path",
            "--option",
            " ",
        )
        self.assertIn("working", completions)
        completions = self.get_completions(
            self.launch_script,
            "python_path",
            "--pythonpath=tests/off_path",
            "--option",
            " ",
        )
        self.assertIn("working", completions)

    def test_reentrant_install_uninstall(self):
        self.install()
        self.install()
        self.verify_install()

        completions = self.get_completions(self.launch_script, "complet")
        self.assertIn("completion", completions)

        self.remove()
        self.remove()
        self.verify_remove()

    def test_path_completion(self):
        self.install()
        self.verify_install()
        completions = self.get_completions(
            self.launch_script, "completion", "--path", "./src/django_typer/co"
        )
        self.assertIn("completers", completions)
        self.assertIn("config.py", completions)
        completions = self.get_completions(
            self.launch_script, "completion", "--dir", "./src/django_typer/"
        )
        self.assertNotIn("utils.py", completions)
        self.assertNotIn("config.py", completions)
        self.assertIn("templates", completions)
        self.assertIn("management", completions)
        self.remove()
        self.verify_remove()

    # todo - cursor positioning not working
    # def test_cursor_position(self):
    #     self.install()
    #     self.verify_install()
    #     cmd = [self.launch_script, "shellcompletion", "--set ", "install"]
    #     completions = self.get_completions(*cmd, position=-9)
    #     self.assertIn("--settings", completions)
    #     self.remove()
    #     self.verify_remove()


class _ScriptCompleteTestCase(_CompleteTestCase):
    manage_script: str = "manage.py"
    launch_script: str = "./manage.py"


class _InstalledScriptCompleteTestCase(_CompleteTestCase):
    """
    These shell completes use an installed script available on the path
    instead of a script directly invoked by path. The difference may
    seem trivial - but it is not given how most shells determine if completion
    logic should be invoked for a given command.
    """

    MANAGE_SCRIPT_TMPL = Path(__file__).parent / "django_manage.py"
    manage_script = "django-admin"
    launch_script = "django-admin"

    @classmethod
    def install_script(cls, script=None):
        if not script:
            script = cls.manage_script
        lines = []
        with open(cls.MANAGE_SCRIPT_TMPL, "r") as f:
            for line in f.readlines():
                if line.startswith("#!{{shebang}}"):
                    line = f"#!{sys.executable}\n"
                lines.append(line)
        exe = Path(sys.executable).parent / script
        with open(exe, "w") as f:
            for line in lines:
                f.write(line)

        # make the script executable
        os.chmod(exe, os.stat(exe).st_mode | 0o111)

        if platform.system() == "Windows":
            with open(exe.with_suffix(".cmd"), "w") as f:
                f.write(f'@echo off{os.linesep}"{sys.executable}" "%~dp0{exe.name}" %*')
            os.chmod(exe, os.stat(exe.with_suffix(".cmd")).st_mode | 0o111)

    @classmethod
    def remove_script(cls, script=None):
        if not script:
            script = cls.manage_script
        exe = Path(sys.executable).parent / script
        exe.unlink(missing_ok=True)
        exe.with_suffix(".cmd").unlink(missing_ok=True)

    def test_multi_install(self):
        parts = self.manage_script.split(".")
        manage2 = ".".join([parts[0] + "2", *parts[1:]])
        try:
            self.install_script(script=manage2)
            self.install()
            self.verify_install()
            self.install(script=manage2)
            self.verify_install(script=manage2)

            completions = self.get_completions(self.manage_script, "complet")
            self.assertIn("completion", completions)

            completions = self.get_completions(manage2, "complet")
            self.assertIn("completion", completions)

            self.remove()
            self.verify_remove()
            self.remove(script=manage2)
            self.verify_remove(script=manage2)
        finally:
            self.remove_script(script=manage2)

    def test_prompt_install(self, env={}, directory: t.Optional[Path] = None):
        import pexpect

        env = {
            **dict(os.environ),
            "DJANGO_SETTINGS_MODULE": "tests.settings.completion",
            "DJANGO_COLORS": "nocolor",
            **env,
        }

        rex = re.compile
        expected = [
            rex(
                r"Append\s+the\s+above\s+contents\s+to\s+(?P<file>.*)\?", re.DOTALL
            ),  # 0
            rex(
                r"Create\s+(?P<file>.*)\s+with\s+the\s+above\s+contents\?",
                re.DOTALL,
            ),  # 1
            rex(r"Aborted\s+shell\s+completion\s+installation."),  # 2
            rex(rf"Installed\s+autocompletion\s+for\s+{self.shell}"),  # 3
        ]

        install_command = [
            "shellcompletion",
            "--no-color",
            "--shell",
            self.shell,
            "install",
        ]
        self.remove()
        self.verify_remove(directory=directory)

        if platform.system() != "Windows":
            install = pexpect.spawn(self.manage_script, install_command, env=env)
            install.setwinsize(24, 800)
        else:
            from pexpect.popen_spawn import PopenSpawn

            install = PopenSpawn(
                " ".join([self.manage_script, *install_command]),
                env=env,
                encoding="utf-8",
            )

        def wait_for_output(child) -> t.Tuple[int, t.Optional[str]]:
            index = child.expect(expected)
            if index in [0, 1]:
                return index, child.match.group("file")
            return index, None

        # test an abort
        idx, _ = wait_for_output(install)
        self.assertLess(idx, 2)
        install.sendline("N")

        while True:
            idx, _ = wait_for_output(install)
            if idx < 2:
                install.sendline("N")
            else:
                self.assertEqual(idx, 2)
                break

        self.verify_remove(directory=directory)

        # test an install
        if platform.system() != "Windows":
            install = pexpect.spawn(self.manage_script, install_command, env=env)
            install.setwinsize(24, 800)
        else:
            from pexpect.popen_spawn import PopenSpawn

            install = PopenSpawn(
                " ".join([self.manage_script, *install_command]),
                env=env,
                encoding="utf-8",
            )

        while True:
            idx, _ = wait_for_output(install)
            if idx < 2:
                install.sendline("Y")
            else:
                self.assertEqual(idx, 3)
                break

        self.verify_install(directory=directory)

    # TODO
    # else:

    #     def test_prompt_install(self, env={}, directory: t.Optional[Path] = None):
    #         env = {
    #             **dict(os.environ),
    #             "DJANGO_SETTINGS_MODULE": "tests.settings.completion",
    #             "DJANGO_COLORS": "nocolor",
    #             **env,
    #         }

    #         rex = re.compile
    #         expected_patterns = [
    #             rex(r"Append the above contents to (?P<file>.*)\?"),  # 0
    #             rex(r"Create (?P<file>.*) with the above contents\?"),  # 1
    #             rex(r"Aborted shell completion installation."),  # 2
    #             rex(rf"Installed autocompletion for {self.shell}"),  # 3
    #         ]

    #         install_command = [
    #             self.manage_script,
    #             "shellcompletion",
    #             "--no-color",
    #             "--shell",
    #             self.shell,
    #             "install",
    #         ]
    #         self.remove()
    #         self.verify_remove(directory=directory)

    #         def run_with_response(responses: t.List[str]):
    #             process = subprocess.Popen(
    #                 install_command,
    #                 env=env,
    #                 cwd=directory,
    #                 stdin=subprocess.PIPE,
    #                 stdout=subprocess.PIPE,
    #                 stderr=subprocess.STDOUT,
    #                 text=True,
    #             )

    #             output = ""
    #             for response in responses:
    #                 while True:
    #                     line = process.stdout.readline()
    #                     if not line:
    #                         break
    #                     output += line

    #                     matched_index, matched_file = match_output(line)
    #                     if matched_index is not None:
    #                         process.stdin.write(response + "\n")
    #                         process.stdin.flush()
    #                         break

    #             process.wait()
    #             return output

    #         def match_output(line: str) -> t.Tuple[t.Optional[int], t.Optional[str]]:
    #             for i, pattern in enumerate(expected_patterns):
    #                 match = pattern.search(line)
    #                 if match:
    #                     return i, match.groupdict().get("file")
    #             return None, None

    #         # Test abort sequence
    #         abort_output = run_with_response(["N", "N"])
    #         self.assertIn("Aborted shell completion installation.", abort_output)
    #         self.verify_remove(directory=directory)

    #         # Test install sequence
    #         install_output = run_with_response(["Y", "Y"])
    #         self.assertIn(f"Installed autocompletion for {self.shell}", install_output)
    #         self.verify_install(directory=directory)
