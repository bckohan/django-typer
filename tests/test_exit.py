"""
How typer.Exit, typer.Abort, KeyboardInterrupt and sys.exit leave a command.

From the command line the process ends with the corresponding status and nothing
extra is printed. From Python a non-zero Exit and an Abort become a CommandError
carrying the status as ``returncode``, and Exit(0) is simply success.
See https://github.com/django-commons/django-typer/issues/318
"""

from contextlib import redirect_stdout
from io import StringIO

import typer
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from django_typer.management import get_command
from tests.utils import run_command


class ExitPolicyTests(TestCase):
    def test_exit_status_from_the_command_line(self):
        for code in (0, 3):
            stdout, stderr, retcode = run_command(
                "exit_codes", "--no-color", "exit", "--code", str(code)
            )
            self.assertEqual(retcode, code, stderr)
            self.assertEqual(stdout.strip(), "")  # the code is not output
            self.assertEqual(stderr.strip(), "")

        stdout, stderr, retcode = run_command(
            "exit_codes_chain", "--no-color", "a", "b", "--code", "2"
        )
        self.assertEqual(retcode, 2, stderr)
        self.assertEqual(stdout.strip(), "a ran")

        stdout, stderr, retcode = run_command(
            "exit_codes_handle", "--no-color", "--code", "5"
        )
        self.assertEqual(retcode, 5, stderr)
        self.assertEqual(stdout.strip(), "")

    def test_exit_from_call_command(self):
        self.assertIsNone(call_command("exit_codes", "exit"))
        self.assertIsNone(call_command("exit_codes", "exit", "--code", "0"))
        self.assertIsNone(call_command("exit_codes_handle", code=0))

        with self.assertRaises(CommandError) as raised:
            call_command("exit_codes", "exit", "--code", "3")
        self.assertEqual(raised.exception.returncode, 3)
        self.assertIn("exited with code 3", str(raised.exception))
        self.assertIsInstance(raised.exception.__cause__, typer.Exit)

        with self.assertRaises(CommandError) as raised:
            call_command("exit_codes_chain", "a", "b", "--code", "2")
        self.assertEqual(raised.exception.returncode, 2)

        with self.assertRaises(CommandError) as raised:
            call_command("exit_codes_handle", code=5)
        self.assertEqual(raised.exception.returncode, 5)

    def test_direct_calls_are_plain_python_calls(self):
        # calling command functions directly bypasses django-typer's policy:
        # whatever the function raises propagates unchanged
        cmd = get_command("exit_codes_handle")
        with self.assertRaises(typer.Exit) as raised:
            cmd(code=0)
        self.assertEqual(raised.exception.exit_code, 0)
        with self.assertRaises(typer.Exit) as raised:
            cmd(code=4)
        self.assertEqual(raised.exception.exit_code, 4)

        cmd = get_command("exit_codes")
        self.assertEqual(cmd.ok(), "done")
        with self.assertRaises(typer.Exit):
            cmd.exit(code=4)
        with self.assertRaises(typer.Abort):
            cmd.abort()
        with self.assertRaises(typer.Exit):
            get_command("exit_codes", "exit")(code=6)
        with self.assertRaises(CommandError) as raised:
            cmd.error(code=2)
        self.assertEqual(raised.exception.returncode, 2)

    def test_exit_policy_survives_another_thread_finishing(self):
        # execute() tracks "django-typer is driving this command" per thread, so
        # a shared instance finishing in one thread must not turn the policy off
        # for a run still in progress in another
        import threading

        from tests.apps.test_app.management.commands import exit_codes

        cmd = get_command("exit_codes")
        exit_codes.started.clear()
        exit_codes.release.clear()
        outcome: dict[str, BaseException | str] = {}

        def run_slow():
            try:
                outcome["result"] = call_command(cmd, "wait-then-exit", "--code", "3")
            except BaseException as err:  # noqa: BLE001
                outcome["error"] = err

        slow = threading.Thread(target=run_slow)
        slow.start()
        try:
            self.assertTrue(exit_codes.started.wait(timeout=10))
            # a full execution on the same instance in this thread
            self.assertEqual(call_command(cmd, "ok"), "done")
        finally:
            exit_codes.release.set()
            slow.join(timeout=10)

        self.assertFalse(slow.is_alive(), "the command did not finish")
        self.assertNotIn("result", outcome)
        self.assertIsInstance(outcome["error"], CommandError)
        self.assertEqual(outcome["error"].returncode, 3)

    def test_writing_to_a_closed_pipe(self):
        # `./manage.py cmd | head`: the reader goes away mid-write. From the
        # command line that is not a fault - exit 1 with nothing on stderr.
        import errno
        import os
        import subprocess
        import sys

        env = {**os.environ, "PYTHONPATH": os.getcwd()}
        proc = subprocess.Popen(
            # the output is generated by the command - a 300KB argv would exceed the
            # per-argument limit on Linux and the command line limit on Windows
            [sys.executable, "manage.py", "exit_codes", "--no-color", "spew"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        assert proc.stdout is not None
        proc.stdout.read(5)
        proc.stdout.close()  # the reader has had enough
        _, stderr = proc.communicate(timeout=30)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(stderr.decode().strip(), "")

        # a Python caller with a broken pipe gets the error like any other
        class ClosedPipe(StringIO):
            def write(self, s):
                raise BrokenPipeError(errno.EPIPE, "Broken pipe")

        with self.assertRaises(BrokenPipeError):
            call_command("exit_codes", "say", "hello", stdout=ClosedPipe())

    def test_abort(self):
        stdout, stderr, retcode = run_command("exit_codes", "--no-color", "abort")
        self.assertEqual(retcode, 1)
        self.assertEqual(stdout.strip(), "")
        self.assertEqual(stderr.strip(), "Aborted!")

        with self.assertRaises(CommandError) as raised:
            call_command("exit_codes", "abort")
        self.assertEqual(raised.exception.returncode, 1)
        self.assertEqual(str(raised.exception), "Aborted!")
        self.assertIsInstance(raised.exception.__cause__, typer.Abort)

    def test_end_of_input_at_a_prompt_aborts(self):
        self.assertEqual(run_command("exit_codes", "--no-color", "eof")[2], 1)
        with self.assertRaises(CommandError) as raised:
            call_command("exit_codes", "eof")
        self.assertEqual(str(raised.exception), "Aborted!")

    def test_keyboard_interrupt(self):
        stdout, stderr, retcode = run_command("exit_codes", "--no-color", "interrupt")
        self.assertEqual(retcode, 130)
        self.assertNotIn("Traceback", stderr)
        # a Python caller gets the interrupt itself, not a CommandError
        with self.assertRaises(KeyboardInterrupt):
            call_command("exit_codes", "interrupt")

    def test_sys_exit_is_unchanged(self):
        self.assertEqual(run_command("exit_codes", "sysexit", "--code", "4")[2], 4)
        with self.assertRaises(SystemExit):
            call_command("exit_codes", "sysexit", "--code", "4")

    def test_help_still_ends_the_process(self):
        stdout, stderr, retcode = run_command("exit_codes", "--no-color", "--help")
        self.assertEqual(retcode, 0)
        self.assertIn("Usage:", stdout)
        with self.assertRaises(SystemExit):
            call_command("exit_codes", "--help")


class ExitMatrixTests(TestCase):
    """
    One check per cell of the table in the "Exit Codes, Errors and Aborts" how-to
    section. Each row is one way a command can end, each column one invocation
    context. Keep this in step with doc/source/howto.rst.
    """

    # (row label, subcommand args, command line, call_command, direct call)
    #   command line: (exit status, stdout check, stderr check) - a check is a
    #       string that must be contained, "" for nothing printed, or None to skip
    #   call_command / direct: ("returns", value) or ("raises", type, returncode,
    #       message fragment) - None means not applicable
    MATRIX = [
        (
            "returns a value",
            ["ok"],
            (0, "", ""),
            ("returns", "done"),
            ("returns", "done"),
        ),
        (
            "raises CommandError(msg, returncode=n)",
            ["error", "--code", "2"],
            (2, "", "CommandError: something went wrong"),
            ("raises", CommandError, 2, "something went wrong"),
            ("raises", CommandError, 2, "something went wrong"),
        ),
        (
            "raises typer.Exit(0)",
            ["exit", "--code", "0"],
            (0, "", ""),
            ("returns", None),
            ("raises", typer.Exit, 0, None),
        ),
        (
            "raises typer.Exit(n)",
            ["exit", "--code", "3"],
            (3, "", ""),
            ("raises", CommandError, 3, "exited with code 3"),
            ("raises", typer.Exit, 3, None),
        ),
        (
            "raises typer.Abort()",
            ["abort"],
            (1, "", "Aborted!"),
            ("raises", CommandError, 1, "Aborted!"),
            ("raises", typer.Abort, None, None),
        ),
        (
            "calls sys.exit(n)",
            ["sysexit", "--code", "4"],
            (4, "", ""),
            ("raises", SystemExit, 4, None),
            ("raises", SystemExit, 4, None),
        ),
        (
            "is interrupted",
            ["interrupt"],
            (130, "", ""),
            ("raises", KeyboardInterrupt, None, None),
            ("raises", KeyboardInterrupt, None, None),
        ),
        (
            "raises any other exception",
            ["boom"],
            (1, "", "RuntimeError: unexpected failure"),
            ("raises", RuntimeError, None, "unexpected failure"),
            ("raises", RuntimeError, None, "unexpected failure"),
        ),
        (
            "is given bad arguments",
            ["exit", "--code", "notanint"],
            (1, "Usage:", "is not a valid"),
            ("raises", CommandError, 1, "is not a valid"),
            None,
        ),
    ]

    def check_outcome(self, expected, invoke):
        if expected[0] == "returns":
            self.assertEqual(invoke(), expected[1])
            return
        _, exc_type, returncode, fragment = expected
        with self.assertRaises(exc_type) as raised:
            invoke()
        exc = raised.exception
        if returncode is not None:
            status = exc.code if isinstance(exc, SystemExit) else None
            if isinstance(exc, CommandError):
                status = exc.returncode
            elif isinstance(exc, typer.Exit):
                status = exc.exit_code
            self.assertEqual(status, returncode)
        if fragment is not None:
            self.assertIn(fragment, str(exc))

    def test_command_line_column(self):
        for label, args, (status, out, err), _, _ in self.MATRIX:
            with self.subTest(row=label):
                # the documented behavior is the default, not the test suite's setting
                stdout, stderr, retcode = run_command(
                    "exit_codes", "--settings", "tests.settings.no_print_result", *args
                )
                self.assertEqual(retcode, status, stderr)
                for expected, actual in ((out, stdout), (err, stderr)):
                    if expected == "":
                        self.assertEqual(actual.strip(), "")
                    elif expected is not None:
                        self.assertIn(expected, actual)
                if label == "raises any other exception":
                    self.assertIn("Traceback", stderr)
                else:
                    self.assertNotIn("Traceback", stderr)

    def test_call_command_column(self):
        for label, args, _, expected, _ in self.MATRIX:
            with self.subTest(row=label):
                self.check_outcome(expected, lambda: call_command("exit_codes", *args))

    def test_direct_call_column(self):
        cmd = get_command("exit_codes")
        for label, args, _, _, expected in self.MATRIX:
            if expected is None:
                continue  # not applicable - nothing is parsed on a direct call
            with self.subTest(row=label):
                name, *rest = args
                kwargs = {"code": int(rest[1])} if rest else {}
                self.check_outcome(expected, lambda: getattr(cmd, name)(**kwargs))


class PrintResultDefaultTests(TestCase):
    """The 4.x default: returned values are not printed unless asked for."""

    def test_default_is_off(self):
        stdout, stderr, retcode = run_command(
            "exit_codes", "--settings", "tests.settings.no_print_result", "ok"
        )
        self.assertEqual((retcode, stdout.strip(), stderr.strip()), (0, "", ""))
        output = StringIO()
        with override_settings(DT_PRINT_RESULT=False), redirect_stdout(output):
            self.assertEqual(call_command("exit_codes", "ok"), "done")
        self.assertEqual(output.getvalue().strip(), "")

    def test_setting_turns_it_on(self):
        # tests.settings.base sets DT_PRINT_RESULT = True
        stdout, stderr, retcode = run_command("exit_codes", "--no-color", "ok")
        self.assertEqual((retcode, stdout.strip()), (0, "done"))
        output = StringIO()
        with override_settings(DT_PRINT_RESULT=True), redirect_stdout(output):
            self.assertEqual(call_command("exit_codes", "ok"), "done")
        self.assertEqual(output.getvalue().strip(), "done")

    def test_environment_variable_turns_it_on(self):
        import os

        base = {**os.environ, "PYTHONPATH": os.getcwd()}
        cases = (
            ("1", "done"),
            ("true", "done"),
            ("YES", "done"),
            ("0", ""),
            ("false", ""),
            ("", ""),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                stdout, stderr, retcode = run_command(
                    "exit_codes",
                    "--settings",
                    "tests.settings.no_print_result",
                    "ok",
                    env={**base, "DT_PRINT_RESULT": value},
                )
                self.assertEqual((retcode, stdout.strip()), (0, expected), stderr)

    def test_field_wins_over_setting(self):
        # print_result = True on the command beats a project default of off
        output = StringIO()
        with (
            override_settings(
                INSTALLED_APPS=["tests.apps.howto"], DT_PRINT_RESULT=False
            ),
            redirect_stdout(output),
        ):
            self.assertEqual(call_command("print_result"), "This will be printed")
        self.assertEqual(output.getvalue().strip(), "This will be printed")

        # ... and print_result = False beats a project default of on
        cmd = get_command("exit_codes")
        cmd.print_result = False
        output = StringIO()
        with override_settings(DT_PRINT_RESULT=True), redirect_stdout(output):
            self.assertEqual(call_command(cmd, "ok"), "done")
        self.assertEqual(output.getvalue().strip(), "")

    def test_stdout_option_respects_the_default(self):
        # call_command(stdout=...) makes Django swap in its own wrapper - result
        # printing must still follow the setting there
        with override_settings(DT_PRINT_RESULT=False):
            buffer = StringIO()
            self.assertEqual(call_command("exit_codes", "ok", stdout=buffer), "done")
            self.assertEqual(buffer.getvalue(), "")
            buffer = StringIO()
            call_command("exit_codes", "say", "hello", stdout=buffer)
            self.assertEqual(buffer.getvalue().strip(), "hello")
        with override_settings(DT_PRINT_RESULT=True):
            buffer = StringIO()
            self.assertEqual(call_command("exit_codes", "ok", stdout=buffer), "done")
            self.assertEqual(buffer.getvalue().strip(), "done")

    def test_reused_instance_keeps_writing(self):
        # with printing off, a run must not leave stdout disabled for the next run
        cmd = get_command("exit_codes")
        output = StringIO()
        with override_settings(DT_PRINT_RESULT=False), redirect_stdout(output):
            cmd = get_command("exit_codes")
            self.assertEqual(call_command(cmd, "ok"), "done")
            call_command(cmd, "say", "still here")
            cmd.say("and here")
        self.assertEqual(output.getvalue().split(), ["still", "here", "and", "here"])

    def test_disable_flag_is_per_thread(self):
        import threading

        from django_typer.management import OutputWrapper

        out = StringIO()
        wrapper = OutputWrapper(out)
        wrapper.disable = True
        self.assertTrue(wrapper.disable)
        seen: dict[str, bool] = {}

        def other_thread():
            seen["disabled"] = wrapper.disable
            wrapper.write("from the other thread")

        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join()
        self.assertFalse(seen["disabled"])
        self.assertIn("from the other thread", out.getvalue())
        wrapper.write("dropped")
        self.assertNotIn("dropped", out.getvalue())
