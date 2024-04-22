import contextlib
import inspect
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Tuple

import django
import pexpect
import pytest
import typer
from django.apps import apps
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from django_typer import TyperCommand, get_command, group
from django_typer.tests.apps.polls.models import Question
from django_typer.tests.apps.test_app.models import ShellCompleteTester
from django_typer.tests.utils import read_django_parameters
from django_typer.utils import get_current_command

try:
    import rich

    rich_installed = True
except ImportError:
    rich_installed = False


def similarity(text1, text2):
    """
    Compute the cosine similarity between two texts.
    https://en.wikipedia.org/wiki/Cosine_similarity

    We use this to lazily evaluate the output of --help to our
    renderings.
    """
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([text1, text2])
    return cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]


manage_py = Path(__file__).parent.parent.parent / "manage.py"
TESTS_DIR = Path(__file__).parent


def get_named_arguments(function):
    sig = inspect.signature(function)
    return [
        name
        for name, param in sig.parameters.items()
        if param.default != inspect.Parameter.empty
    ]


def interact(command, *args, **kwargs):
    cwd = os.getcwd()
    try:
        os.chdir(manage_py.parent)
        return pexpect.spawn(
            " ".join([sys.executable, f"./{manage_py.name}", command, *args]),
            env=os.environ,
            **kwargs,
        )
    finally:
        os.chdir(cwd)


def run_command(command, *args, parse_json=True, **kwargs) -> Tuple[str, str]:
    # we want to use the same test database that was created for the test suite run
    cwd = os.getcwd()
    try:
        env = os.environ.copy()
        os.chdir(manage_py.parent)
        result = subprocess.run(
            [sys.executable, f"./{manage_py.name}", command, *args],
            capture_output=True,
            text=True,
            env=env,
            **kwargs,
        )

        # Check the return code to ensure the script ran successfully
        if result.returncode != 0:
            return result.stdout, result.stderr, result.returncode

        # Parse the output
        if result.stdout:
            if parse_json:
                try:
                    return json.loads(result.stdout), result.stderr, result.returncode
                except json.JSONDecodeError:
                    return result.stdout, result.stderr, result.returncode
            return result.stdout, result.stderr, result.returncode
        return result.stdout, result.stderr, result.returncode
    finally:
        os.chdir(cwd)


class BasicTests(TestCase):
    def test_common_options_function(self):
        from django_typer import _common_options

        self.assertIsNone(_common_options())

    def test_command_line(self):
        self.assertEqual(
            run_command("basic", "a1", "a2")[0],
            {"arg1": "a1", "arg2": "a2", "arg3": 0.5, "arg4": 1},
        )

        self.assertEqual(
            run_command("basic", "a1", "a2", "--arg3", "0.75", "--arg4", "2")[0],
            {"arg1": "a1", "arg2": "a2", "arg3": 0.75, "arg4": 2},
        )

    def test_cmd_name(self):
        self.assertEqual(get_command("shellcompletion")._name, "shellcompletion")

    def test_call_command(self):
        out = StringIO()
        returned_options = json.loads(call_command("basic", ["a1", "a2"], stdout=out))
        self.assertEqual(
            returned_options, {"arg1": "a1", "arg2": "a2", "arg3": 0.5, "arg4": 1}
        )

    def test_call_command_stdout(self):
        out = StringIO()
        call_command("basic", ["a1", "a2"], stdout=out)
        printed_options = json.loads(out.getvalue())
        self.assertEqual(
            printed_options, {"arg1": "a1", "arg2": "a2", "arg3": 0.5, "arg4": 1}
        )

    def test_get_version(self):
        self.assertEqual(
            str(run_command("basic", "--version")[0]).strip(), django.get_version()
        )

    def test_call_direct(self):
        basic = get_command("basic")
        self.assertEqual(
            json.loads(basic.handle("a1", "a2")),
            {"arg1": "a1", "arg2": "a2", "arg3": 0.5, "arg4": 1},
        )

        from django_typer.tests.apps.test_app.management.commands.basic import (
            Command as Basic,
        )

        self.assertEqual(
            json.loads(Basic()("a1", "a2", arg3=0.75, arg4=2)),
            {"arg1": "a1", "arg2": "a2", "arg3": 0.75, "arg4": 2},
        )

    def test_parser(self):
        basic_cmd = get_command("basic")
        parser = basic_cmd.create_parser("./manage.py", "basic")
        with self.assertRaises(NotImplementedError):
            parser.add_argument()

    def test_command_context(self):
        basic = get_command("basic")
        multi = get_command("multi")
        self.assertIsNone(get_current_command())
        with basic:
            self.assertEqual(basic, get_current_command())
            with basic:
                self.assertEqual(basic, get_current_command())
                with multi:
                    self.assertEqual(multi, get_current_command())
                self.assertEqual(basic, get_current_command())
            self.assertEqual(basic, get_current_command())
        self.assertIsNone(get_current_command())

    def test_renaming(self):
        self.assertEqual(run_command("rename", "default")[0].strip(), "handle")
        self.assertEqual(run_command("rename", "renamed")[0].strip(), "subcommand1")
        self.assertEqual(run_command("rename", "renamed2")[0].strip(), "subcommand2")

        self.assertEqual(call_command("rename", "default"), "handle")
        self.assertEqual(call_command("rename", "renamed"), "subcommand1")
        self.assertEqual(call_command("rename", "renamed2"), "subcommand2")

        self.assertEqual(get_command("rename")(), "handle")
        self.assertEqual(get_command("rename").subcommand1(), "subcommand1")
        self.assertEqual(get_command("rename").subcommand2(), "subcommand2")


class CommandDefinitionTests(TestCase):
    def test_group_callback_throws(self):
        class CBTestCommand(TyperCommand):
            @group()
            def grp():
                pass

            grp.group()

            def grp2():
                pass

        with self.assertRaises(NotImplementedError):

            class CommandBad(TyperCommand):
                @group()
                def grp():
                    pass

                @grp.callback()
                def bad_callback():
                    pass

        with self.assertRaises(NotImplementedError):

            class CommandBad(CBTestCommand):
                @CBTestCommand.grp.callback()
                def bad_callback():
                    pass


class InterfaceTests(TestCase):
    """
    Make sure the django_typer decorator interfaces match the
    typer decorator interfaces. We don't simply pass variadic arguments
    to the typer decorator because we want the IDE to offer auto complete
    suggestions. This is a "developer experience" concession

    Include some other interface tests designed to test compatibility between
    the overrides and what the base class expects
    """

    def test_command_interface_matches(self):
        from django_typer import command

        command_params = set(get_named_arguments(command))
        typer_params = set(get_named_arguments(typer.Typer.command))

        self.assertFalse(command_params.symmetric_difference(typer_params))

    def test_initialize_interface_matches(self):
        from django_typer import initialize

        initialize_params = set(get_named_arguments(initialize))
        typer_params = set(get_named_arguments(typer.Typer.callback))

        self.assertFalse(initialize_params.symmetric_difference(typer_params))

    def test_typer_command_interface_matches(self):
        from django_typer import TyperCommandMeta

        typer_command_params = set(get_named_arguments(TyperCommandMeta.__new__))
        typer_params = set(get_named_arguments(typer.Typer.__init__))
        typer_params.remove("name")
        typer_params.remove("add_completion")
        self.assertFalse(typer_command_params.symmetric_difference(typer_params))

    def test_group_interface_matches(self):
        from django_typer import GroupFunction

        typer_command_params = set(get_named_arguments(GroupFunction.group))
        typer_params = set(get_named_arguments(typer.Typer.add_typer))
        typer_params.remove("callback")
        self.assertFalse(typer_command_params.symmetric_difference(typer_params))

    def test_group_command_interface_matches(self):
        from django_typer import GroupFunction

        typer_command_params = set(get_named_arguments(GroupFunction.command))
        typer_params = set(get_named_arguments(typer.Typer.command))
        self.assertFalse(typer_command_params.symmetric_difference(typer_params))

    def test_action_nargs(self):
        # unclear if nargs is even necessary - no other test seems to exercise it, leaving in for
        # base class compat reasons
        self.assertEqual(
            get_command("basic")
            .create_parser("./manage.py", "basic")
            ._actions[0]
            .nargs,
            1,
        )
        self.assertEqual(
            get_command("completion")
            .create_parser("./manage.py", "completion")
            ._actions[0]
            .nargs,
            -1,
        )
        multi_parser = get_command("multi").create_parser("./manage.py", "multi")
        self.assertEqual(multi_parser._actions[7].param.name, "files")
        self.assertEqual(multi_parser._actions[7].nargs, -1)
        self.assertEqual(multi_parser._actions[8].param.name, "flag1")
        self.assertEqual(multi_parser._actions[8].nargs, 0)


class MultiTests(TestCase):
    def test_command_line(self):
        self.assertEqual(
            run_command("multi", "cmd1", "/path/one", "/path/two")[0],
            {"files": ["/path/one", "/path/two"], "flag1": False},
        )

        self.assertEqual(
            run_command("multi", "cmd1", "/path/four", "/path/three", "--flag1")[0],
            {"files": ["/path/four", "/path/three"], "flag1": True},
        )

        self.assertEqual(
            run_command("multi", "sum", "1.2", "3.5", " -12.3")[0],
            sum([1.2, 3.5, -12.3]),
        )

        self.assertEqual(run_command("multi", "cmd3")[0], {})

    def test_call_command(self):
        ret = json.loads(call_command("multi", ["cmd1", "/path/one", "/path/two"]))
        self.assertEqual(ret, {"files": ["/path/one", "/path/two"], "flag1": False})

        ret = json.loads(
            call_command("multi", ["cmd1", "/path/four", "/path/three", "--flag1"])
        )
        self.assertEqual(ret, {"files": ["/path/four", "/path/three"], "flag1": True})

        ret = json.loads(call_command("multi", ["sum", "1.2", "3.5", " -12.3"]))
        self.assertEqual(ret, sum([1.2, 3.5, -12.3]))

        ret = json.loads(call_command("multi", ["cmd3"]))
        self.assertEqual(ret, {})

    def test_call_command_stdout(self):
        out = StringIO()
        call_command("multi", ["cmd1", "/path/one", "/path/two"], stdout=out)
        self.assertEqual(
            json.loads(out.getvalue()),
            {"files": ["/path/one", "/path/two"], "flag1": False},
        )

        out = StringIO()
        call_command(
            "multi", ["cmd1", "/path/four", "/path/three", "--flag1"], stdout=out
        )
        self.assertEqual(
            json.loads(out.getvalue()),
            {"files": ["/path/four", "/path/three"], "flag1": True},
        )

        out = StringIO()
        call_command("multi", ["sum", "1.2", "3.5", " -12.3"], stdout=out)
        self.assertEqual(json.loads(out.getvalue()), sum([1.2, 3.5, -12.3]))

        out = StringIO()
        call_command("multi", ["cmd3"], stdout=out)
        self.assertEqual(json.loads(out.getvalue()), {})

    def test_get_version(self):
        self.assertEqual(
            str(run_command("multi", "--version")[0]).strip(), django.get_version()
        )
        self.assertEqual(
            str(run_command("multi", "--version", "cmd1")[0]).strip(),
            django.get_version(),
        )
        self.assertEqual(
            str(run_command("multi", "--version", "sum")[0]).strip(),
            django.get_version(),
        )
        self.assertEqual(
            str(run_command("multi", "--version", "cmd3")[0]).strip(),
            django.get_version(),
        )

    def test_call_direct(self):
        multi = get_command("multi")

        self.assertEqual(
            json.loads(multi.cmd1(["/path/one", "/path/two"])),
            {"files": ["/path/one", "/path/two"], "flag1": False},
        )

        self.assertEqual(
            json.loads(multi.cmd1(["/path/four", "/path/three"], flag1=True)),
            {"files": ["/path/four", "/path/three"], "flag1": True},
        )

        self.assertEqual(float(multi.sum([1.2, 3.5, -12.3])), sum([1.2, 3.5, -12.3]))

        self.assertEqual(json.loads(multi.cmd3()), {})


class TestGetCommand(TestCase):
    def test_get_command(self):
        from django_typer.tests.apps.test_app.management.commands.basic import (
            Command as Basic,
        )

        basic = get_command("basic")
        assert basic.__class__ == Basic

        from django_typer.tests.apps.test_app.management.commands.multi import (
            Command as Multi,
        )

        multi = get_command("multi")
        assert multi.__class__ == Multi
        cmd1 = get_command("multi", "cmd1")
        assert cmd1.__func__ is multi.cmd1.__func__
        sum = get_command("multi", "sum")
        assert sum.__func__ is multi.sum.__func__
        cmd3 = get_command("multi", "cmd3")
        assert cmd3.__func__ is multi.cmd3.__func__

        from django_typer.tests.apps.test_app.management.commands.callback1 import (
            Command as Callback1,
        )

        callback1 = get_command("callback1")
        assert callback1.__class__ == Callback1

        # callbacks are not commands
        with self.assertRaises(LookupError):
            get_command("callback1", "init")


class CallbackTests(TestCase):
    cmd_name = "callback1"

    def test_helps(self, top_level_only=False):
        buffer = StringIO()
        cmd = get_command(self.cmd_name, stdout=buffer, no_color=True)
        help_output_top = run_command(self.cmd_name, "--no-color", "--help")[0]
        cmd.print_help("./manage.py", self.cmd_name)
        self.assertEqual(help_output_top.strip(), buffer.getvalue().strip())
        self.assertIn(f"Usage: ./manage.py {self.cmd_name} [OPTIONS]", help_output_top)

        if not top_level_only:
            buffer.truncate(0)
            buffer.seek(0)
            callback_help = run_command(
                self.cmd_name, "--no-color", "5", self.cmd_name, "--help"
            )[0]
            cmd.print_help("./manage.py", self.cmd_name, self.cmd_name)
            self.assertEqual(callback_help.strip(), buffer.getvalue().strip())
            self.assertIn(
                f"Usage: ./manage.py {self.cmd_name} P1 {self.cmd_name} [OPTIONS] ARG1 ARG2",
                callback_help,
            )

    def test_command_line(self):
        self.assertEqual(
            run_command(self.cmd_name, "5", self.cmd_name, "a1", "a2")[0],
            {
                "p1": 5,
                "flag1": False,
                "flag2": True,
                "arg1": "a1",
                "arg2": "a2",
                "arg3": 0.5,
                "arg4": 1,
            },
        )

        self.assertEqual(
            run_command(
                self.cmd_name,
                "--flag1",
                "--no-flag2",
                "6",
                self.cmd_name,
                "a1",
                "a2",
                "--arg3",
                "0.75",
                "--arg4",
                "2",
            )[0],
            {
                "p1": 6,
                "flag1": True,
                "flag2": False,
                "arg1": "a1",
                "arg2": "a2",
                "arg3": 0.75,
                "arg4": 2,
            },
        )

    def test_call_command(self, should_raise=True):
        ret = json.loads(
            call_command(
                self.cmd_name,
                *["5", self.cmd_name, "a1", "a2"],
                **{"p1": 5, "arg1": "a1", "arg2": "a2"},
            )
        )
        self.assertEqual(
            ret,
            {
                "p1": 5,
                "flag1": False,
                "flag2": True,
                "arg1": "a1",
                "arg2": "a2",
                "arg3": 0.5,
                "arg4": 1,
            },
        )

        ret = json.loads(
            call_command(
                self.cmd_name,
                *[
                    "--flag1",
                    "--no-flag2",
                    "6",
                    self.cmd_name,
                    "a1",
                    "a2",
                    "--arg3",
                    "0.75",
                    "--arg4",
                    "2",
                ],
            )
        )
        self.assertEqual(
            ret,
            {
                "p1": 6,
                "flag1": True,
                "flag2": False,
                "arg1": "a1",
                "arg2": "a2",
                "arg3": 0.75,
                "arg4": 2,
            },
        )

        # show that order matters args vs options
        interspersed = [
            lambda: call_command(
                self.cmd_name,
                *[
                    "6",
                    "--flag1",
                    "--no-flag2",
                    self.cmd_name,
                    "n1",
                    "n2",
                    "--arg3",
                    "0.2",
                    "--arg4",
                    "9",
                ],
            ),
            lambda: call_command(
                self.cmd_name,
                *[
                    "--no-flag2",
                    "6",
                    "--flag1",
                    self.cmd_name,
                    "--arg4",
                    "9",
                    "n1",
                    "n2",
                    "--arg3",
                    "0.2",
                ],
            ),
        ]
        expected = {
            "p1": 6,
            "flag1": True,
            "flag2": False,
            "arg1": "n1",
            "arg2": "n2",
            "arg3": 0.2,
            "arg4": 9,
        }
        if should_raise:
            for call_cmd in interspersed:
                if should_raise:
                    with self.assertRaises(BaseException):
                        call_cmd()
                else:
                    self.assertEqual(json.loads(call_cmd()), expected)

    def test_call_command_stdout(self):
        out = StringIO()
        call_command(
            self.cmd_name,
            [
                "--flag1",
                "--no-flag2",
                "6",
                self.cmd_name,
                "a1",
                "a2",
                "--arg3",
                "0.75",
                "--arg4",
                "2",
            ],
            stdout=out,
        )

        self.assertEqual(
            json.loads(out.getvalue()),
            {
                "p1": 6,
                "flag1": True,
                "flag2": False,
                "arg1": "a1",
                "arg2": "a2",
                "arg3": 0.75,
                "arg4": 2,
            },
        )

    def test_get_version(self):
        self.assertEqual(
            str(run_command(self.cmd_name, "--version")[0]).strip(),
            django.get_version(),
        )
        self.assertEqual(
            str(run_command(self.cmd_name, "--version", "6", self.cmd_name)[0]).strip(),
            django.get_version(),
        )

    def test_call_direct(self):
        cmd = get_command(self.cmd_name)

        self.assertEqual(
            json.loads(cmd(arg1="a1", arg2="a2", arg3=0.2)),
            {"arg1": "a1", "arg2": "a2", "arg3": 0.2, "arg4": 1},
        )


class Callback2Tests(CallbackTests):
    cmd_name = "callback2"

    def test_call_command(self):
        super().test_call_command(should_raise=False)

    def test_helps(self, top_level_only=False):
        # we only run the top level help comparison because when
        # interspersed args are allowed its impossible to get the
        # subcommand to print its help
        super().test_helps(top_level_only=True)


class UsageErrorTests(TestCase):
    def test_missing_parameter(self):
        result = run_command("missing")
        self.assertTrue("Test missing parameter." in result[0])
        self.assertTrue("arg1 must be given." in result[1])

        result = run_command("error")
        self.assertTrue("Test usage error behavior." in result[0])
        self.assertTrue("Missing parameter: arg1" in result[1])

        with self.assertRaises(CommandError):
            call_command("missing")

        with self.assertRaises(CommandError):
            call_command("error")

    def test_bad_param(self):
        result = run_command("error", "a")
        self.assertTrue("Test usage error behavior." in result[0])
        self.assertTrue("'a' is not a valid integer." in result[1])

        with self.assertRaises(CommandError):
            call_command("error", "a")

    def test_no_option(self):
        result = run_command("error", "--flg1")
        self.assertTrue("Test usage error behavior." in result[0])
        self.assertTrue("No such option: --flg1" in result[1])

        with self.assertRaises(CommandError):
            call_command("error", "--flg1")

    def test_bad_option(self):
        result = run_command("error", "--opt1", "d")
        self.assertTrue("Test usage error behavior." in result[0])
        self.assertTrue("'d' is not a valid integer." in result[1])

        with self.assertRaises(CommandError):
            call_command("error", "--opt1", "d")


class TestDjangoParameters(TestCase):
    commands = [
        ("dj_params1", []),
        ("dj_params2", ["cmd1"]),
        ("dj_params2", ["cmd2"]),
        ("dj_params3", ["cmd1"]),
        ("dj_params3", ["cmd2"]),
        ("dj_params4", []),
    ]

    def test_settings(self):
        for cmd, args in self.commands:
            run_command(cmd, "--settings", "django_typer.tests.settings.settings2", *args)
            self.assertEqual(read_django_parameters().get("settings", None), 2)

    def test_color_params(self):
        for cmd, args in self.commands:
            run_command(cmd, "--no-color", *args)
            params = read_django_parameters()
            self.assertEqual(params.get("no_color", False), True)
            self.assertEqual(params.get("no_color_attr", False), True)
            run_command(cmd, "--force-color", *args)
            params = read_django_parameters()
            self.assertEqual(params.get("no_color", True), False)
            self.assertEqual(params.get("no_color_attr", True), False)

            result = run_command(cmd, "--force-color", "--no-color", *args)
            self.assertTrue(
                "The --no-color and --force-color options can't be used together."
                in result[1]
            )

            call_command(cmd, args, no_color=True)
            params = read_django_parameters()
            self.assertEqual(params.get("no_color", False), True)
            self.assertEqual(params.get("no_color_attr", False), True)
            call_command(cmd, args, force_color=True)
            params = read_django_parameters()
            self.assertEqual(params.get("no_color", True), False)
            self.assertEqual(params.get("no_color_attr", True), False)
            with self.assertRaises(BaseException):
                call_command(cmd, args, force_color=True, no_color=True)

    def test_ctor_params(self):
        # check non-tty streams output expected constructor values and coloring
        stdout = StringIO()
        stderr = StringIO()
        cmd = get_command(
            "ctor", stdout=stdout, stderr=stderr, no_color=None, force_color=None
        )
        cmd()
        out_str = stdout.getvalue()
        err_str = stderr.getvalue()
        self.assertEqual(out_str, "out\nno_color=None\nforce_color=None\n")
        self.assertEqual(err_str, "err\nno_color=None\nforce_color=None\n")
        cmd.print_help("./manage.py", "ctor")

        # check no-color
        stdout = StringIO()
        stderr = StringIO()
        stdout.isatty = lambda: True
        stderr.isatty = lambda: True
        cmd = get_command(
            "ctor", stdout=stdout, stderr=stderr, no_color=True, force_color=False
        )
        cmd()
        self.assertEqual(stdout.getvalue(), "out\nno_color=True\nforce_color=False\n")
        self.assertEqual(stderr.getvalue(), "err\nno_color=True\nforce_color=False\n")
        cmd.print_help("./manage.py", "ctor")
        self.assertTrue("\x1b" not in stdout.getvalue())
        self.assertTrue("\x1b" not in stderr.getvalue())
        stdout.truncate(0)
        stderr.truncate(0)

        stdout.getvalue()
        stderr.getvalue()
        cmd.execute(skip_checks=False, no_color=None, force_color=None)
        out_str = stdout.getvalue()
        err_str = stderr.getvalue()
        self.assertTrue(out_str.endswith("out\nno_color=True\nforce_color=False\n"))
        self.assertTrue(err_str.endswith("err\nno_color=True\nforce_color=False\n"))

    def test_pythonpath(self):
        added = str(Path(__file__).parent.absolute())
        self.assertTrue(added not in sys.path)
        for cmd, args in self.commands:
            run_command(cmd, "--pythonpath", added, *args)
            self.assertTrue(added in read_django_parameters().get("python_path", []))

    def test_skip_checks(self):
        for cmd, args in self.commands:
            result = run_command(
                cmd, "--settings", "django_typer.tests.settings.settings_fail_check", *args
            )
            self.assertTrue("SystemCheckError" in result[1])
            self.assertTrue("test_app.E001" in result[1])

            result = run_command(
                cmd,
                "--skip-checks",
                "--settings",
                "django_typer.tests.settings.settings_fail_check",
                *args,
            )
            self.assertFalse("SystemCheckError" in result[1])
            self.assertFalse("test_app.E001" in result[1])

    @override_settings(DJANGO_TYPER_FAIL_CHECK=True)
    def test_skip_checks_call(self):
        for cmd, args in self.commands:
            from django.core.management.base import SystemCheckError

            with self.assertRaises(SystemCheckError):
                call_command(cmd, *args, skip_checks=False)

            # when you call_command and don't supply skip_checks, it will default to True!
            call_command(cmd, *args, skip_checks=True)
            call_command(cmd, *args)

    def test_traceback(self):
        # traceback does not come into play with call_command
        for cmd, args in self.commands:
            result = run_command(cmd, *args, "--throw")[1]
            if cmd != "dj_params4":
                self.assertFalse("Traceback" in result)
            else:
                self.assertTrue("Traceback" in result)

            if cmd != "dj_params4":
                result_tb = run_command(cmd, "--traceback", *args, "--throw")[1]
                self.assertTrue("Traceback" in result_tb)
            else:
                result_tb = run_command(cmd, "--no-traceback", *args, "--throw")[1]
                self.assertFalse("Traceback" in result_tb)

    def test_verbosity(self):
        run_command("dj_params3", "cmd1")
        self.assertEqual(read_django_parameters().get("verbosity", None), 1)

        call_command("dj_params3", ["cmd1"])
        self.assertEqual(read_django_parameters().get("verbosity", None), 1)

        run_command("dj_params3", "--verbosity", "2", "cmd1")
        self.assertEqual(read_django_parameters().get("verbosity", None), 2)

        call_command("dj_params3", ["cmd1"], verbosity=2)
        self.assertEqual(read_django_parameters().get("verbosity", None), 2)

        run_command("dj_params3", "--verbosity", "0", "cmd2")
        self.assertEqual(read_django_parameters().get("verbosity", None), 0)

        call_command("dj_params3", ["cmd2"], verbosity=0)
        self.assertEqual(read_django_parameters().get("verbosity", None), 0)

        run_command("dj_params4")
        self.assertEqual(read_django_parameters().get("verbosity", None), 1)

        call_command("dj_params4")
        self.assertEqual(read_django_parameters().get("verbosity", None), 1)

        run_command("dj_params4", "--verbosity", "2")
        self.assertEqual(read_django_parameters().get("verbosity", None), 2)

        call_command("dj_params4", [], verbosity=2)
        self.assertEqual(read_django_parameters().get("verbosity", None), 2)

        run_command("dj_params4", "--verbosity", "0")
        self.assertEqual(read_django_parameters().get("verbosity", None), 0)

        call_command("dj_params4", [], verbosity=0)
        self.assertEqual(read_django_parameters().get("verbosity", None), 0)


class TestHelpPrecedence(TestCase):
    def test_help_precedence1(self):
        buffer = StringIO()
        cmd = get_command("help_precedence1", no_color=True, stdout=buffer)
        cmd.print_help("./manage.py", "help_precedence1")
        self.assertTrue(
            re.search(
                r"help_precedence1\s+Test minimal TyperCommand subclass - command method",
                buffer.getvalue(),
            )
        )
        self.assertIn(
            "Test minimal TyperCommand subclass - typer param", buffer.getvalue()
        )

    def test_help_precedence2(self):
        buffer = StringIO()
        cmd = get_command("help_precedence2", stdout=buffer, no_color=True)
        cmd.print_help("./manage.py", "help_precedence2")
        self.assertIn(
            "Test minimal TyperCommand subclass - class member", buffer.getvalue()
        )
        self.assertTrue(
            re.search(
                r"help_precedence2\s+Test minimal TyperCommand subclass - command method",
                buffer.getvalue(),
            )
        )

    def test_help_precedence3(self):
        buffer = StringIO()
        cmd = get_command("help_precedence3", stdout=buffer, no_color=True)
        cmd.print_help("./manage.py", "help_precedence3")
        self.assertTrue(
            re.search(
                r"help_precedence3\s+Test minimal TyperCommand subclass - command method",
                buffer.getvalue(),
            )
        )
        self.assertIn(
            "Test minimal TyperCommand subclass - callback method", buffer.getvalue()
        )

    def test_help_precedence4(self):
        buffer = StringIO()
        cmd = get_command("help_precedence4", stdout=buffer, no_color=True)
        cmd.print_help("./manage.py", "help_precedence4")
        self.assertIn(
            "Test minimal TyperCommand subclass - callback docstring", buffer.getvalue()
        )
        self.assertTrue(
            re.search(
                r"help_precedence4\s+Test minimal TyperCommand subclass - command method",
                buffer.getvalue(),
            )
        )

    def test_help_precedence5(self):
        buffer = StringIO()
        cmd = get_command("help_precedence5", stdout=buffer, no_color=True)
        cmd.print_help("./manage.py", "help_precedence5")
        self.assertIn(
            "Test minimal TyperCommand subclass - command method", buffer.getvalue()
        )

    def test_help_precedence6(self):
        buffer = StringIO()
        cmd = get_command("help_precedence6", stdout=buffer, no_color=True)
        cmd.print_help("./manage.py", "help_precedence6")
        self.assertIn(
            "Test minimal TyperCommand subclass - docstring", buffer.getvalue()
        )

    def test_help_precedence7(self):
        buffer = StringIO()
        cmd = get_command("help_precedence7", stdout=buffer, no_color=True)
        cmd.print_help("./manage.py", "help_precedence7")
        self.assertIn(
            "Test minimal TyperCommand subclass - class member", buffer.getvalue()
        )

    def test_help_precedence8(self):
        buffer = StringIO()
        cmd = get_command("help_precedence8", stdout=buffer, no_color=True)
        cmd.print_help("./manage.py", "help_precedence8")
        self.assertIn(
            "Test minimal TyperCommand subclass - typer param", buffer.getvalue()
        )


class TestOverloaded(TestCase):
    """
    Tests that overloaded group/command names work as expected.
    """

    def test_overloaded_direct(self):
        overloaded = get_command("overloaded")
        overloaded.test(1, flag=True)
        self.assertEqual(
            json.loads(overloaded.samename(5, flag=False)),
            {
                "samename": {"precision": 5, "flag": False},
                "test": {"precision": 1, "flag": True},
            },
        )

        overloaded.test(5, flag=False)
        self.assertEqual(
            json.loads(overloaded.samename(1, flag=True)),
            {
                "samename": {"precision": 1, "flag": True},
                "test": {"precision": 5, "flag": False},
            },
        )

        overloaded.test(1, flag=True)
        self.assertEqual(
            json.loads(overloaded.diffname(5, flag2=False)),
            {
                "diffname": {"precision2": 5, "flag2": False},
                "test": {"precision": 1, "flag": True},
            },
        )

        overloaded.test(5, flag=False)
        self.assertEqual(
            json.loads(overloaded.diffname(1, flag2=True)),
            {
                "diffname": {"precision2": 1, "flag2": True},
                "test": {"precision": 5, "flag": False},
            },
        )

    def test_overloaded_cli(self):
        result = run_command(
            "overloaded", "test", "--flag", "1", "samename", "5", "--no-flag"
        )[0]
        self.assertEqual(
            result,
            {
                "samename": {"precision": 5, "flag": False},
                "test": {"precision": 1, "flag": True},
            },
        )

        result = run_command(
            "overloaded", "test", "--no-flag", "5", "samename", "1", "--flag"
        )[0]
        self.assertEqual(
            result,
            {
                "samename": {"precision": 1, "flag": True},
                "test": {"precision": 5, "flag": False},
            },
        )
        result = run_command(
            "overloaded", "test", "--flag", "1", "diffname", "5", "--no-flag"
        )[0]
        self.assertEqual(
            result,
            {
                "diffname": {"precision2": 5, "flag2": False},
                "test": {"precision": 1, "flag": True},
            },
        )

        result = run_command(
            "overloaded", "test", "--no-flag", "5", "diffname", "1", "--flag"
        )[0]
        self.assertEqual(
            result,
            {
                "diffname": {"precision2": 1, "flag2": True},
                "test": {"precision": 5, "flag": False},
            },
        )

    def test_overloaded_call_command(self):
        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded",
                    ["test", "--flag", "1", "samename", "5", "--no-flag"],
                )
            ),
            {
                "samename": {"precision": 5, "flag": False},
                "test": {"precision": 1, "flag": True},
            },
        )
        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded",
                    ["test", "--no-flag", "5", "samename", "1", "--flag"],
                )
            ),
            {
                "samename": {"precision": 1, "flag": True},
                "test": {"precision": 5, "flag": False},
            },
        )
        self.assertEqual(
            json.loads(
                call_command("overloaded", ["test", "5", "samename", "1"], flag=True)
            ),
            {
                "samename": {"precision": 1, "flag": True},
                "test": {"precision": 5, "flag": True},
            },
        )

        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded",
                    ["test", "--no-flag", "5", "diffname", "1", "--flag"],
                )
            ),
            {
                "diffname": {"precision2": 1, "flag2": True},
                "test": {"precision": 5, "flag": False},
            },
        )
        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded",
                    ["test", "--flag", "1", "diffname", "5", "--no-flag"],
                )
            ),
            {
                "diffname": {"precision2": 5, "flag2": False},
                "test": {"precision": 1, "flag": True},
            },
        )
        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded", ["test", "5", "diffname", "1"], flag=True, flag2=False
                )
            ),
            {
                "diffname": {"precision2": 1, "flag2": False},
                "test": {"precision": 5, "flag": True},
            },
        )


class TestReturnValues(TestCase):
    """
    Tests that overloaded group/command names work as expected.
    """

    def test_return_direct(self):
        return_cmd = get_command("return")
        self.assertEqual(return_cmd(), {"key": "value"})

    def test_return_cli(self):
        self.assertEqual(run_command("return")[0].strip(), str({"key": "value"}))

    def test_return_call(self):
        self.assertEqual(call_command("return"), {"key": "value"})


class TestGroups(TestCase):
    """
    A collection of tests that test complex grouping commands and also that
    command inheritance behaves as expected.
    """

    rich_installed: bool

    def setUp(self):
        try:
            import rich  # noqa

            self.rich_installed = True
        except ImportError:
            self.rich_installed = False

    def test_group_call(self):
        with self.assertRaises(NotImplementedError):
            get_command("groups")()

    @pytest.mark.skip()
    def test_get_help_from_incongruent_path(self):
        """
        The directory change screws up the code coverage - it makes the omitted
        directories get included because their relative paths dont resolve in the
        coverage output for this test. VERY ANNOYING - not sure how to fix?

        https://github.com/bckohan/django-typer/issues/44
        """
        # change dir to the first dir that is not a parent
        cwd = Path(os.getcwd())
        try:
            for directory in os.listdir("/"):
                top_dir = Path(f"/{directory}")
                try:
                    cwd.relative_to(top_dir)
                except ValueError:
                    # change cwd to the first directory that is not a parent and try
                    # to invoke help from there
                    os.chdir(top_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            manage_py.absolute(),
                            "groups",
                            "--no-color",
                            "--help",
                        ],
                        capture_output=True,
                        text=True,
                        env=os.environ,
                    )
                    self.assertGreater(
                        sim := similarity(
                            result.stdout,
                            (
                                TESTS_DIR / "apps" / "test_app" / "helps" / "groups.txt"
                            ).read_text(),
                        ),
                        0.96,  # width inconsistences drive this number < 1
                    )
                    return
        finally:
            os.chdir(cwd)

    @override_settings(
        INSTALLED_APPS=[
            "django_typer.tests.apps.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_helps(self, app="test_app"):
        for cmds in [
            ("groups",),
            ("groups", "echo"),
            ("groups", "math"),
            ("groups", "math", "divide"),
            ("groups", "math", "multiply"),
            ("groups", "string"),
            ("groups", "string", "case"),
            ("groups", "string", "case", "lower"),
            ("groups", "string", "case", "upper"),
            ("groups", "string", "strip"),
            ("groups", "string", "split"),
            ("groups", "setting"),
            ("groups", "setting", "print"),
        ]:
            if app == "test_app" and cmds[-1] in ["strip", "setting", "print"]:
                with self.assertRaises(LookupError):
                    cmd = get_command(cmds[0], stdout=buffer, no_color=True)
                    self.assertTrue(cmd.no_color)
                    cmd.print_help("./manage.py", *cmds)
                continue

            buffer = StringIO()
            cmd = get_command(cmds[0], stdout=buffer, no_color=True)
            cmd.print_help("./manage.py", *cmds)
            hlp = buffer.getvalue()
            helps_dir = "helps" if self.rich_installed else "helps_no_rich"
            self.assertGreater(
                sim := similarity(
                    hlp, (TESTS_DIR / "apps" / app / helps_dir / f"{cmds[-1]}.txt").read_text()
                ),
                0.96,  # width inconsistences drive this number < 1
            )
            print(f'{app}: {" ".join(cmds)} = {sim:.2f}')

            cmd = get_command(cmds[0], stdout=buffer, force_color=True)
            cmd.print_help("./manage.py", *cmds)
            hlp = buffer.getvalue()
            if self.rich_installed:
                self.assertTrue("\x1b" in hlp)

    @override_settings(
        INSTALLED_APPS=[
            "django_typer.tests.apps.test_app2",
            "django_typer.tests.apps.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_helps_override(self):
        self.test_helps.__wrapped__(self, app="test_app2")

    @override_settings(
        INSTALLED_APPS=[
            "django_typer.tests.apps.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_command_line(self, settings=None):
        override = settings is not None
        settings = ("--settings", settings) if settings else []

        self.assertEqual(
            run_command("groups", *settings, "echo", "hey!")[0].strip(),
            "hey!",
        )

        self.assertEqual(
            call_command("groups", "echo", "hey!").strip(),
            "hey!",
        )
        self.assertEqual(
            get_command("groups", "echo")("hey!").strip(),
            "hey!",
        )
        self.assertEqual(
            get_command("groups", "echo")(message="hey!").strip(),
            "hey!",
        )

        self.assertEqual(get_command("groups").echo("hey!").strip(), "hey!")

        self.assertEqual(get_command("groups").echo(message="hey!").strip(), "hey!")

        result = run_command("groups", "--no-color", *settings, "echo", "hey!", "5")
        if override:
            self.assertEqual(result[0].strip(), ("hey! " * 5).strip())
            self.assertEqual(
                get_command("groups").echo("hey!", 5).strip(), ("hey! " * 5).strip()
            )
            self.assertEqual(
                get_command("groups").echo(message="hey!", echoes=5).strip(),
                ("hey! " * 5).strip(),
            )
            self.assertEqual(
                call_command("groups", "echo", "hey!", "5").strip(),
                ("hey! " * 5).strip(),
            )
            self.assertEqual(
                call_command("groups", "echo", "hey!", echoes=5).strip(),
                ("hey! " * 5).strip(),
            )
        else:
            self.assertIn("Usage: ./manage.py groups echo [OPTIONS] MESSAGE", result[0])
            self.assertIn("Got unexpected extra argument (5)", result[1])
            with self.assertRaises(TypeError):
                call_command("groups", "echo", "hey!", echoes=5)
            with self.assertRaises(TypeError):
                get_command("groups").echo(message="hey!", echoes=5)

        self.assertEqual(
            run_command(
                "groups",
                *settings,
                "math",
                "--precision",
                "5",
                "multiply",
                "1.2",
                "3.5",
                " -12.3",
                parse_json=False,
            )[0].strip(),
            "-51.66000",
        )

        grp_cmd = get_command("groups")
        grp_cmd.math(precision=5)
        self.assertEqual(grp_cmd.multiply(1.2, 3.5, [-12.3]), "-51.66000")

        self.assertEqual(
            call_command(
                "groups", "math", "multiply", "1.2", "3.5", " -12.3", precision=5
            ),
            "-51.66000",
        )

        self.assertEqual(
            call_command(
                "groups", "math", "--precision=5", "multiply", "1.2", "3.5", " -12.3"
            ),
            "-51.66000",
        )

        self.assertEqual(
            run_command(
                "groups",
                *settings,
                "math",
                "divide",
                "1.2",
                "3.5",
                " -12.3",
                parse_json=False,
            )[0].strip(),
            "-0.03",
        )

        self.assertEqual(
            call_command(
                "groups",
                "math",
                "divide",
                "1.2",
                "3.5",
                " -12.3",
            ),
            "-0.03",
        )

        self.assertEqual(get_command("groups").divide(1.2, 3.5, [-12.3]), "-0.03")
        self.assertEqual(
            get_command("groups", "math", "divide")(1.2, 3.5, [-12.3]), "-0.03"
        )

        self.assertEqual(
            run_command("groups", *settings, "string", "ANNAmontes", "case", "lower")[
                0
            ].strip(),
            "annamontes",
        )

        self.assertEqual(
            call_command("groups", "string", "ANNAmontes", "case", "lower"),
            "annamontes",
        )

        grp_cmd = get_command("groups")
        grp_cmd.string("ANNAmontes")
        self.assertEqual(grp_cmd.lower(), "annamontes")

        self.assertEqual(
            run_command("groups", *settings, "string", "annaMONTES", "case", "upper")[
                0
            ].strip(),
            "ANNAMONTES",
        )

        grp_cmd.string("annaMONTES")
        self.assertEqual(grp_cmd.upper(), "ANNAMONTES")

        self.assertEqual(
            run_command(
                "groups",
                *settings,
                "string",
                "ANNAMONTES",
                "case",
                "lower",
                "--begin",
                "4",
                "--end",
                "9",
            )[0].strip(),
            "ANNAmonteS",
        )

        self.assertEqual(
            call_command(
                "groups",
                "string",
                "ANNAMONTES",
                "case",
                "lower",
                "--begin",
                "4",
                "--end",
                "9",
            ).strip(),
            "ANNAmonteS",
        )

        self.assertEqual(
            call_command(
                "groups", "string", "ANNAMONTES", "case", "lower", begin=4, end=9
            ).strip(),
            "ANNAmonteS",
        )

        grp_cmd.string("ANNAMONTES")
        self.assertEqual(grp_cmd.lower(begin=4, end=9), "ANNAmonteS")
        grp_cmd.string("ANNAMONTES")
        self.assertEqual(grp_cmd.lower(4, 9), "ANNAmonteS")

        result = run_command(
            "groups",
            "--no-color",
            *settings,
            "string",
            "annamontes",
            "case",
            "upper",
            "4",
            "9",
        )
        if override:
            self.assertIn(
                "Usage: ./manage.py groups string STRING case upper [OPTIONS]",
                result[0],
            )
            self.assertIn("Got unexpected extra arguments (4 9)", result[1].strip())
            grp_cmd.string("annamontes")
            with self.assertRaises(TypeError):
                self.assertEqual(grp_cmd.upper(4, 9), "annaMONTEs")

            with self.assertRaises(CommandError):
                self.assertEqual(
                    call_command(
                        "groups", "string", "annamontes", "case", "upper", "4", "9"
                    ).strip(),
                    "annaMONTEs",
                )
        else:
            result = result[0].strip()
            self.assertEqual(result, "annaMONTEs")
            grp_cmd.string("annamontes")
            self.assertEqual(grp_cmd.upper(4, 9), "annaMONTEs")
            self.assertEqual(
                call_command(
                    "groups", "string", "annamontes", "case", "upper", "4", "9"
                ).strip(),
                "annaMONTEs",
            )

        result = run_command(
            "groups",
            "--no-color",
            *settings,
            "string",
            " emmatc  ",
            "strip",
            parse_json=False,
        )
        if override:
            self.assertEqual(result[0], "emmatc\n")
            self.assertEqual(
                call_command("groups", "string", " emmatc  ", "strip"), "emmatc"
            )
            grp_cmd.string(" emmatc  ")
            self.assertEqual(grp_cmd.strip(), "emmatc")
        else:
            self.assertIn(
                "Usage: ./manage.py groups string [OPTIONS] STRING COMMAND [ARGS]",
                result[0],
            )
            self.assertIn("No such command 'strip'.", result[1])
            with self.assertRaises(CommandError):
                self.assertEqual(
                    call_command("groups", "string", " emmatc  ", "strip"), "emmatc"
                )
            with self.assertRaises(AttributeError):
                grp_cmd.string(" emmatc  ")
                self.assertEqual(grp_cmd.strip(), "emmatc")

        self.assertEqual(
            run_command(
                "groups", *settings, "string", "c,a,i,t,l,y,n", "split", "--sep", ","
            )[0].strip(),
            "c a i t l y n",
        )
        self.assertEqual(
            call_command(
                "groups", "string", "c,a,i,t,l,y,n", "split", "--sep", ","
            ).strip(),
            "c a i t l y n",
        )
        self.assertEqual(
            call_command("groups", "string", "c,a,i,t,l,y,n", "split", sep=",").strip(),
            "c a i t l y n",
        )
        grp_cmd.string("c,a,i,t,l,y,n")
        self.assertEqual(grp_cmd.split(sep=","), "c a i t l y n")
        grp_cmd.string("c,a,i,t,l,y,n")
        self.assertEqual(grp_cmd.split(","), "c a i t l y n")

    @override_settings(
        INSTALLED_APPS=[
            "django_typer.tests.apps.test_app2",
            "django_typer.tests.apps.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_command_line_override(self):
        self.test_command_line.__wrapped__(self, settings="django_typer.tests.settings.override")


class TestCallCommandArgs(TestCase):
    @override_settings(
        INSTALLED_APPS=[
            "django_typer.tests.apps.test_app2",
            "django_typer.tests.apps.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_completion_args(self):
        # call_command converts all args to strings - todo - fix this? or accept it? fixing it
        # would require a monkey patch. I think accepting it and trying to allow Arguments to
        # be passed in as named parameters would be a good compromise. Users can always invoke
        # the typer commands directly using () or the functions directly.

        # if autocompletion ends up requiring a monkey patch, consider fixing it

        # turns out call_command will also turn options values into strings you've flagged them as required
        # and they're passed in as named parameters

        test_app = apps.get_app_config("django_typer_tests_apps_test_app")
        test_app2 = apps.get_app_config("django_typer_tests_apps_test_app2")

        out = StringIO()
        call_command(
            "completion",
            ["django_typer_tests_apps_test_app", "django_typer_tests_apps_test_app2"],
            stdout=out,
        )
        printed_options = json.loads(out.getvalue())
        self.assertEqual(
            printed_options,
            ["django_typer_tests_apps_test_app", "django_typer_tests_apps_test_app2"],
        )

        out = StringIO()
        printed_options = json.loads(get_command("completion")([test_app, test_app2]))
        self.assertEqual(
            printed_options,
            ["django_typer_tests_apps_test_app", "django_typer_tests_apps_test_app2"],
        )


@pytest.mark.skipif(not rich_installed, reason="rich not installed")
class TestTracebackConfig(TestCase):
    rich_installed = True

    uninstall = False

    def test_default_traceback(self):
        result = run_command("test_command1", "--no-color", "delete", "me", "--throw")[
            1
        ]
        self.assertIn("Traceback (most recent call last)", result)
        self.assertIn("Exception: This is a test exception", result)
        if self.rich_installed:
            self.assertIn("────────", result)
            # locals should be present
            self.assertIn("name = 'me'", result)
            self.assertIn("throw = True", result)
            # by default we get only the last frame
            self.assertEqual(len(re.findall(r"\.py:\d+", result) or []), 1)
        else:
            self.assertNotIn("────────", result)

    def test_tb_command_overrides(self):
        result = run_command(
            "test_tb_overrides", "--no-color", "delete", "me", "--throw"
        )[1]
        self.assertIn("Traceback (most recent call last)", result)
        self.assertIn("Exception: This is a test exception", result)
        if self.rich_installed:
            self.assertIn("────────", result)
            # locals should be present
            self.assertNotIn("name = 'me'", result)
            self.assertNotIn("throw = True", result)
            # should get a stack trace with files and line numbers
            self.assertGreater(len(re.findall(r"\.py:\d+", result) or []), 0)
        else:
            self.assertNotIn("────────", result)

    def test_turn_traceback_off_false(self):
        result = run_command(
            "test_command1",
            "--settings",
            "django_typer.tests.settings.settings_tb_false",
            "delete",
            "me",
            "--throw",
        )[1]
        self.assertNotIn("────────", result)
        self.assertIn("Traceback (most recent call last)", result)
        self.assertIn("Exception: This is a test exception", result)

    def test_turn_traceback_off_none(self):
        result = run_command(
            "test_command1",
            "--settings",
            "django_typer.tests.settings.settings_tb_none",
            "delete",
            "me",
            "--throw",
        )[1]
        self.assertNotIn("────────", result)
        self.assertIn("Traceback (most recent call last)", result)
        self.assertIn("Exception: This is a test exception", result)

    def test_traceback_no_locals_short_false(self):
        result = run_command(
            "test_command1",
            "--no-color",
            "--settings",
            "django_typer.tests.settings.settings_tb_change_defaults",
            "delete",
            "me",
            "--throw",
        )[1]
        self.assertIn("Traceback (most recent call last)", result)
        self.assertIn("Exception: This is a test exception", result)
        # locals should not be present
        self.assertNotIn("name = 'me'", result)
        self.assertNotIn("throw = True", result)
        if self.rich_installed:
            self.assertIn("────────", result)
            self.assertGreater(len(re.findall(r"\.py:\d+", result) or []), 0)
        else:
            self.assertNotIn("────────", result)

        self.assertNotIn("\x1b", result)

    def test_rich_install(self):
        if self.rich_installed:
            result = run_command(
                "test_command1",
                "--settings",
                "django_typer.tests.settings.settings_throw_init_exception",
                "--no-color",
                "delete",
                "me",
            )[1]
            self.assertIn("Traceback (most recent call last)", result)
            self.assertIn("Exception: Test ready exception", result)
            self.assertIn("────────", result)
            self.assertIn("── locals ──", result)
            self.assertNotIn("\x1b", result)

    @override_settings(DJ_RICH_TRACEBACK_CONFIG={"no_install": True})
    def test_tb_no_install(self):
        if self.rich_installed:
            result = run_command(
                "test_command1",
                "--settings",
                "django_typer.tests.settings.settings_tb_no_install",
                "delete",
                "me",
            )[1]
            self.assertIn("Traceback (most recent call last)", result)
            self.assertIn("Exception: Test ready exception", result)
            self.assertNotIn("────────", result)
            self.assertNotIn("── locals ──", result)

    def test_colored_traceback(self):
        result = run_command(
            "test_command1", "--force-color", "delete", "Brian", "--throw"
        )[1]
        if self.rich_installed:
            self.assertIn("\x1b", result)

        result = run_command(
            "test_command1", "--no-color", "delete", "Brian", "--throw"
        )[1]
        self.assertNotIn("\x1b", result)

        result = run_command("test_command1", "delete", "Brian", "--throw")[1]
        self.assertNotIn("\x1b", result)


@pytest.mark.skipif(rich_installed, reason="rich installed")
class TestTracebackConfigNoRich(TestTracebackConfig):
    rich_installed = False


class TestSettingsSystemCheck(TestCase):
    def test_warning_thrown(self):
        result = run_command(
            "noop", "--settings", "django_typer.tests.settings.settings_tb_bad_config"
        )[1]
        if rich_installed:
            self.assertIn(
                "django_typer.tests.settings.settings_tb_bad_config: (django_typer.W001) DT_RICH_TRACEBACK_CONFIG",
                result,
            )
            self.assertIn(
                "HINT: Unexpected parameters encountered: unexpected_setting.", result
            )
        else:
            self.assertNotIn(
                "django_typer.tests.settings.settings_tb_bad_config: (django_typer.W001) DT_RICH_TRACEBACK_CONFIG",
                result,
            )


def test_get_current_command_returns_none():
    from django_typer.utils import get_current_command

    assert get_current_command() is None


class TestChaining(TestCase):
    def test_command_chaining(self):
        result = run_command(
            "chain", "command1", "--option=one", "command2", "--option=two"
        )[0]
        self.assertEqual(result, "command1\ncommand2\n['one', 'two']\n")

        result = run_command(
            "chain", "command2", "--option=two", "command1", "--option=one"
        )[0]
        self.assertEqual(result, "command2\ncommand1\n['two', 'one']\n")

        stdout = StringIO()
        with contextlib.redirect_stdout(stdout):
            result = call_command(
                "chain", "command2", "--option=two", "command1", "--option=one"
            )
        self.assertEqual(stdout.getvalue(), "command2\ncommand1\n['two', 'one']\n")
        self.assertEqual(result, ["two", "one"])

        chain = get_command("chain")
        self.assertEqual(chain.command1(option="one"), "one")
        self.assertEqual(chain.command2(option="two"), "two")


SHELLS = [
    (None, False),
    ("zsh", True),
    ("bash", False),
    ("pwsh", True),
]


class TestPollExample(SimpleTestCase):
    q1 = None
    q2 = None
    q3 = None

    databases = ["default"]

    def setUp(self):
        self.q1 = Question.objects.create(
            question_text="Is Putin a war criminal?",
            pub_date=timezone.now(),
        )
        self.q2 = Question.objects.create(
            question_text="Is Bibi a war criminal?",
            pub_date=timezone.now(),
        )
        self.q3 = Question.objects.create(
            question_text="Is Xi a Pooh Bear?",
            pub_date=timezone.now(),
        )
        super().setUp()

    def tearDown(self):
        Question.objects.all().delete()
        super().tearDown()

    def test_poll_complete(self):
        # result = run_command("shellcompletion", "complete", "./manage.py closepoll ")

        for shell, has_help in SHELLS:
            result1 = StringIO()
            with contextlib.redirect_stdout(result1):
                call_command(
                    "shellcompletion", "complete", shell=shell, cmd_str="closepoll "
                )
            result2 = StringIO()
            with contextlib.redirect_stdout(result2):
                call_command(
                    "shellcompletion",
                    "complete",
                    shell=shell,
                    cmd_str="./manage.py closepoll ",
                )

            result = result1.getvalue()
            self.assertEqual(result, result2.getvalue())
            for q in [self.q1, self.q2, self.q3]:
                self.assertTrue(str(q.id) in result)
                if has_help:
                    self.assertTrue(q.question_text in result)

    def test_tutorial1(self):
        result = run_command("closepoll_t1", str(self.q2.id))
        self.assertFalse(result[1])
        self.assertTrue("Successfully closed poll" in result[0])

    def test_tutorial2(self):
        result = run_command("closepoll_t2", str(self.q2.id))
        self.assertFalse(result[1])
        self.assertTrue("Successfully closed poll" in result[0])

    def test_tutorial_parser(self):
        result = run_command("closepoll_t3", str(self.q1.id))
        self.assertFalse(result[1])

    def test_tutorial_parser_cmd(self):
        log = StringIO()
        call_command("closepoll_t3", str(self.q1.id), stdout=log)
        cmd = get_command("closepoll_t3", stdout=log)
        cmd([self.q1])
        cmd(polls=[self.q1])
        # these don't work, maybe revisit in future?
        # cmd([str(self.q1.id)])
        # cmd([self.q1.id])
        self.assertEqual(log.getvalue().count("Successfully"), 3)

    def test_tutorial_modelobjparser_cmd(self):
        log = StringIO()
        call_command("closepoll_t6", str(self.q1.id), stdout=log)
        cmd = get_command("closepoll_t6", stdout=log)
        cmd([self.q1])
        cmd(polls=[self.q1])
        self.assertEqual(log.getvalue().count("Successfully"), 3)

    def test_poll_ex(self):
        result = run_command("closepoll", str(self.q2.id))
        self.assertFalse(result[1])
        self.assertTrue("Successfully closed poll" in result[0])


class TestShellCompletersAndParsers(TestCase):
    def setUp(self):
        super().setUp()
        self.q1 = Question.objects.create(
            question_text="Is Putin a war criminal?",
            pub_date=timezone.now(),
        )
        for field, values in {
            "char_field": ["jon", "john", "jack", "jason"],
            "text_field": [
                "sockeye",
                "chinook",
                "steelhead",
                "coho",
                "atlantic",
                "pink",
                "chum",
            ],
            "float_field": [1.1, 1.12, 2.2, 2.3, 2.4, 3.0, 4.0],
            "decimal_field": [
                Decimal("1.5"),
                Decimal("1.50"),
                Decimal("1.51"),
                Decimal("1.52"),
                Decimal("1.2"),
                Decimal("1.6"),
            ],
            "uuid_field": [
                "12345678-1234-5678-1234-567812345678",
                "12345678-1234-5678-1234-567812345679",
                "12345678-5678-5678-1234-567812345670",
                "12345678-5678-5678-1234-567812345671",
                "12345678-5678-5678-1234-A67812345671",
                "12345678-5678-5678-f234-A67812345671",
            ],
        }.items():
            for value in values:
                ShellCompleteTester.objects.create(**{field: value})

    def tearDown(self) -> None:
        ShellCompleteTester.objects.all().delete()
        return super().tearDown()

    def test_model_object_parser_metavar(self):
        result = run_command("poll_as_option", "--help", "--no-color")
        found = False
        for line in result[0].splitlines():
            if "--polls" in line:
                self.assertTrue("POLL" in line)
                found = True
        self.assertTrue(found)

    def test_model_object_parser_idempotency(self):
        from django_typer.parsers import ModelObjectParser
        from django_typer.tests.apps.polls.models import Question

        parser = ModelObjectParser(Question)
        self.assertEqual(parser.convert(self.q1, None, None), self.q1)

    def test_app_label_parser_idempotency(self):
        from django_typer.parsers import parse_app_label

        poll_app = apps.get_app_config("django_typer_tests_apps_polls")
        self.assertEqual(parse_app_label(poll_app), poll_app)

    def test_app_label_parser_completers(self):
        from django.apps import apps

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "completion django_typer.tests."
            )
        result = result.getvalue()
        self.assertTrue("django_typer.tests.apps.polls" in result)
        self.assertTrue("django_typer.tests.apps.test_app" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "completion django_typer_tests")
        result = result.getvalue()
        self.assertTrue("django_typer_tests_apps_polls" in result)
        self.assertTrue("django_typer_tests_apps_test_app" in result)

        self.assertEqual(
            json.loads(call_command("completion", "django_typer_tests_apps_polls")),
            ["django_typer_tests_apps_polls"],
        )
        self.assertEqual(
            json.loads(call_command("completion", "django_typer.tests.apps.polls")),
            ["django_typer_tests_apps_polls"],
        )

        with self.assertRaises(CommandError):
            call_command("completion", "django_typer_tests.polls")

        poll_app = apps.get_app_config("django_typer_tests_apps_polls")
        test_app = apps.get_app_config("django_typer_tests_apps_test_app")
        cmd = get_command("completion")
        self.assertEqual(
            json.loads(cmd([poll_app])),
            ["django_typer_tests_apps_polls"],
        )

        self.assertEqual(
            json.loads(cmd(django_apps=[poll_app])), ["django_typer_tests_apps_polls"]
        )

        self.assertEqual(
            json.loads(cmd(django_apps=[poll_app], option=test_app)),
            {
                "django_apps": ["django_typer_tests_apps_polls"],
                "option": "django_typer_tests_apps_test_app",
            },
        )

        self.assertEqual(
            json.loads(
                call_command("completion", "django_typer_tests_apps_polls", option=test_app)
            ),
            {
                "django_apps": ["django_typer_tests_apps_polls"],
                "option": "django_typer_tests_apps_test_app",
            },
        )

        self.assertEqual(
            json.loads(
                call_command(
                    "completion",
                    "django_typer_tests_apps_polls",
                    "--option=django_typer_tests_apps_test_app",
                )
            ),
            {
                "django_apps": ["django_typer_tests_apps_polls"],
                "option": "django_typer_tests_apps_test_app",
            },
        )

    def test_char_field(self):
        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --char ja")
        result = result.getvalue()
        self.assertTrue("jack" in result)
        self.assertTrue("jason" in result)
        self.assertFalse("jon" in result)
        self.assertFalse("john" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --ichar Ja")
        result = result.getvalue()
        self.assertTrue("Jack" in result)
        self.assertTrue("Jason" in result)
        self.assertFalse("Jon" in result)
        self.assertFalse("John" in result)

        self.assertEqual(
            json.loads(call_command("model_fields", "test", "--char", "jack")),
            {
                "char": {
                    str(ShellCompleteTester.objects.get(char_field="jack").pk): "jack"
                }
            },
        )

        self.assertEqual(
            json.loads(call_command("model_fields", "test", "--ichar", "john")),
            {
                "ichar": {
                    str(ShellCompleteTester.objects.get(char_field="john").pk): "john"
                }
            },
        )

        with self.assertRaises(CommandError):
            call_command("model_fields", "test", "--char", "jane")

        with self.assertRaises(RuntimeError):
            call_command("model_fields", "test", "--ichar", "jane")

    def test_text_field(self):
        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --text ")
        result = result.getvalue()
        self.assertTrue("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertTrue("steelhead" in result)
        self.assertTrue("coho" in result)
        self.assertTrue("atlantic" in result)
        self.assertTrue("pink" in result)
        self.assertTrue("chum" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --text ch")
        result = result.getvalue()
        self.assertFalse("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertFalse("steelhead" in result)
        self.assertFalse("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertFalse("pink" in result)
        self.assertTrue("chum" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --itext S")
        result = result.getvalue()
        self.assertTrue("Sockeye" in result)
        self.assertFalse("chinook" in result)
        self.assertTrue("Steelhead" in result)
        self.assertFalse("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertFalse("pink" in result)
        self.assertFalse("chum" in result)

        # distinct completions by default
        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion",
                "complete",
                "model_fields test --text atlantic --text sockeye --text steelhead --text ",
            )
        result = result.getvalue()
        self.assertFalse("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertFalse("steelhead" in result)
        self.assertTrue("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertTrue("pink" in result)
        self.assertTrue("chum" in result)

        # check distinct flag set to False
        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion",
                "complete",
                "model_fields test --itext atlantic --itext sockeye --itext steelhead --itext ",
            )
        result = result.getvalue()
        self.assertTrue("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertTrue("steelhead" in result)
        self.assertTrue("coho" in result)
        self.assertTrue("atlantic" in result)
        self.assertTrue("pink" in result)
        self.assertTrue("chum" in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--text",
                    "atlantic",
                    "--text",
                    "sockeye",
                    "--text",
                    "steelhead",
                )
            ),
            {
                "text": [
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="atlantic").pk
                        ): "atlantic"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="sockeye").pk
                        ): "sockeye"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="steelhead").pk
                        ): "steelhead"
                    },
                ]
            },
        )
        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--itext",
                    "ATlanTIC",
                    "--itext",
                    "SOCKeye",
                    "--itext",
                    "STEELHEAD",
                )
            ),
            {
                "itext": [
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="atlantic").pk
                        ): "atlantic"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="sockeye").pk
                        ): "sockeye"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="steelhead").pk
                        ): "steelhead"
                    },
                ]
            },
        )

    def test_uuid_field(self):
        from uuid import UUID

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --uuid ")
        result = result.getvalue()
        self.assertTrue("12345678-1234-5678-1234-567812345678" in result)
        self.assertTrue("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345670" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345671" in result)
        self.assertTrue("12345678-5678-5678-1234-a67812345671" in result)
        self.assertTrue("12345678-5678-5678-f234-a67812345671" in result)
        self.assertFalse("None" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --uuid 12345678"
            )
        result = result.getvalue()
        self.assertTrue("12345678-1234-5678-1234-567812345678" in result)
        self.assertTrue("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345670" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345671" in result)
        self.assertTrue("12345678-5678-5678-1234-a67812345671" in result)
        self.assertTrue("12345678-5678-5678-f234-a67812345671" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --uuid 12345678-"
            )
        result = result.getvalue()
        self.assertTrue("12345678-1234-5678-1234-567812345678" in result)
        self.assertTrue("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345670" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345671" in result)
        self.assertTrue("12345678-5678-5678-1234-a67812345671" in result)
        self.assertTrue("12345678-5678-5678-f234-a67812345671" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --uuid 12345678-5"
            )
        result = result.getvalue()
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345670" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345671" in result)
        self.assertTrue("12345678-5678-5678-1234-a67812345671" in result)
        self.assertTrue("12345678-5678-5678-f234-a67812345671" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --uuid 123456785"
            )
        result = result.getvalue()
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("123456785678-5678-1234-567812345670" in result)
        self.assertTrue("123456785678-5678-1234-567812345671" in result)
        self.assertTrue("123456785678-5678-1234-a67812345671" in result)
        self.assertTrue("123456785678-5678-f234-a67812345671" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion",
                "complete",
                "model_fields test --uuid 123456&78-^56785678-",
            )
        result = result.getvalue()
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("123456&78-^56785678-1234-567812345670" in result)
        self.assertTrue("123456&78-^56785678-1234-567812345671" in result)
        self.assertTrue("123456&78-^56785678-1234-a67812345671" in result)
        self.assertTrue("123456&78-^56785678-f234-a67812345671" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion",
                "complete",
                "model_fields test --uuid 123456&78-^56785678F",
            )
        result = result.getvalue()
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertFalse("123456&78-^567856781234-567812345670" in result)
        self.assertFalse("123456&78-^567856781234-567812345671" in result)
        self.assertFalse("123456&78-^567856781234-a67812345671" in result)
        self.assertTrue("123456&78-^56785678F234-a67812345671" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion",
                "complete",
                "model_fields test --uuid 123456&78-^56785678f",
            )
        result = result.getvalue()
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertFalse("123456&78-^567856781234-567812345670" in result)
        self.assertFalse("123456&78-^567856781234-567812345671" in result)
        self.assertFalse("123456&78-^567856781234-a67812345671" in result)
        self.assertTrue("123456&78-^56785678f234-a67812345671" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion",
                "complete",
                "model_fields test --uuid 123456&78-^56785678f234---A",
            )
        result = result.getvalue()
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertFalse("123456&78-^567856781234-567812345670" in result)
        self.assertFalse("123456&78-^567856781234-567812345671" in result)
        self.assertFalse("123456&78-^567856781234-a67812345671" in result)
        self.assertTrue("123456&78-^56785678f234---A67812345671" in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--uuid",
                    "123456&78-^56785678f234---A67812345671",
                )
            ),
            {
                "uuid": {
                    str(
                        ShellCompleteTester.objects.get(
                            uuid_field=UUID("12345678-5678-5678-f234-a67812345671")
                        ).pk
                    ): "12345678-5678-5678-f234-a67812345671"
                }
            },
        )

        with self.assertRaises(CommandError):
            call_command(
                "model_fields", "test", "--uuid", "G2345678-5678-5678-f234-a67812345671"
            )

        with self.assertRaises(CommandError):
            call_command(
                "model_fields", "test", "--uuid", "12345678-5678-5678-f234-a67812345675"
            )

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion",
                "complete",
                "model_fields test --uuid 12345678-5678-5678-f234-a678123456755",
            )
        result = result.getvalue()
        self.assertFalse("12345678" in result)

    def test_id_field(self):
        result = StringIO()

        ids = ShellCompleteTester.objects.values_list("id", flat=True)

        starts = {}
        for id in ids:
            starts.setdefault(str(id)[0], []).append(str(id))
        start_chars = set(starts.keys())

        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --id ", shell="zsh"
            )

        result = result.getvalue()
        for id in ids:
            self.assertTrue(f'"{id}"' in result)

        for start_char in start_chars:
            expected = starts[start_char]
            unexpected = [str(id) for id in ids if str(id) not in expected]
            result = StringIO()
            with contextlib.redirect_stdout(result):
                call_command(
                    "shellcompletion",
                    "complete",
                    "--shell",
                    "zsh",
                    f"model_fields test --id {start_char}",
                )

            result = result.getvalue()
            for id in expected:
                self.assertTrue(f'"{id}"' in result)
            for id in unexpected:
                self.assertFalse(f'"{id}"' in result)

        for id in ids:
            self.assertEqual(
                json.loads(call_command("model_fields", "test", "--id", str(id))),
                {"id": id},
            )

        # test the limit option
        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion",
                "complete",
                "--shell",
                "zsh",
                "model_fields test --id-limit ",
            )
        result = result.getvalue()
        for id in ids[0:5]:
            self.assertTrue(f'"{id}"' in result)
        for id in ids[5:]:
            self.assertFalse(f'"{id}"' in result)

    def test_float_field(self):
        values = [1.1, 1.12, 2.2, 2.3, 2.4, 3.0, 4.0]
        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --float ")
        result = result.getvalue()
        for value in values:
            self.assertTrue(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --float 1")
        result = result.getvalue()
        for value in [1.1, 1.12]:
            self.assertTrue(str(value) in result)
        for value in set([1.1, 1.12]) - set(values):
            self.assertFalse(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --float 1.1")
        result = result.getvalue()
        for value in [1.1, 1.12]:
            self.assertTrue(str(value) in result)
        for value in set([1.1, 1.12]) - set(values):
            self.assertFalse(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --float 1.12"
            )
        result = result.getvalue()
        for value in [1.12]:
            self.assertTrue(str(value) in result)
        for value in set([1.12]) - set(values):
            self.assertFalse(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --float 2")
        result = result.getvalue()
        for value in [2.2, 2.3, 2.4]:
            self.assertTrue(str(value) in result)
        for value in set([2.2, 2.3, 2.4]) - set(values):
            self.assertFalse(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --float 2.")
        result = result.getvalue()
        for value in [2.2, 2.3, 2.4]:
            self.assertTrue(str(value) in result)
        for value in set([2.2, 2.3, 2.4]) - set(values):
            self.assertFalse(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --float 2.3")
        result = result.getvalue()
        for value in [2.3]:
            self.assertTrue(str(value) in result)
        for value in set([2.3]) - set(values):
            self.assertFalse(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --float 3")
        result = result.getvalue()
        for value in [3.0]:
            self.assertTrue(str(value) in result)
        for value in set([3.0]) - set(values):
            self.assertFalse(str(value) in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--float",
                    "2.3",
                )
            ),
            {
                "float": {
                    str(ShellCompleteTester.objects.get(float_field=2.3).pk): "2.3"
                }
            },
        )

    def test_decimal_field(self):
        values = [
            Decimal("1.5"),
            Decimal("1.50"),
            Decimal("1.51"),
            Decimal("1.52"),
            Decimal("1.2"),
            Decimal("1.6"),
        ]
        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test --decimal ")
        result = result.getvalue()
        for value in values:
            self.assertTrue(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --decimal 1."
            )
        result = result.getvalue()
        for value in values:
            self.assertTrue(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --decimal 1."
            )
        result = result.getvalue()
        for value in values:
            self.assertTrue(str(value) in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command(
                "shellcompletion", "complete", "model_fields test --decimal 1.5"
            )
        result = result.getvalue()
        for value in set(values) - {Decimal("1.2"), Decimal("1.6")}:
            self.assertTrue(str(value) in result)
        for value in {Decimal("1.2"), Decimal("1.6")}:
            self.assertFalse(str(value) in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--decimal",
                    "1.6",
                )
            ),
            {
                "decimal": {
                    str(
                        ShellCompleteTester.objects.get(decimal_field=Decimal("1.6")).pk
                    ): "1.60"
                }
            },
        )

    def test_option_complete(self):
        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "model_fields test ")
        result = result.getvalue()
        self.assertTrue("--char" in result)
        self.assertTrue("--ichar" in result)
        self.assertTrue("--text" in result)
        self.assertTrue("--itext" in result)
        self.assertTrue("--id" in result)
        self.assertTrue("--id-limit" in result)
        self.assertTrue("--float" in result)
        self.assertTrue("--decimal" in result)
        self.assertTrue("--help" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "noarg cmd ", shell="zsh")
        result = result.getvalue()
        self.assertTrue(result)
        self.assertFalse("--" in result)

        result = StringIO()
        with contextlib.redirect_stdout(result):
            call_command("shellcompletion", "complete", "noarg cmd -", shell="zsh")
        result = result.getvalue()
        self.assertTrue(result)
        self.assertFalse("--" in result)

        # test what happens if we try to complete a non existing command
        with self.assertRaises(CommandError):
            call_command("shellcompletion", "complete", "noargs cmd ", shell="zsh")

    def test_unsupported_field(self):
        from django_typer.completers import ModelObjectCompleter

        with self.assertRaises(ValueError):
            ModelObjectCompleter(ShellCompleteTester, "binary_field")

    def test_shellcompletion_no_detection(self):
        from django_typer.management.commands import shellcompletion

        def raise_error():
            raise RuntimeError()

        shellcompletion.detect_shell = raise_error
        cmd = get_command("shellcompletion")
        with self.assertRaises(CommandError):
            cmd.shell = None

    def test_shellcompletion_complete_cmd(self):
        # test that we can leave preceeding script off the complete argument
        result = run_command(
            "shellcompletion", "complete", "./manage.py completion dj"
        )[0]
        self.assertTrue("django_typer" in result)
        result2 = run_command("shellcompletion", "complete", "completion dj")[0]
        self.assertTrue("django_typer" in result2)
        self.assertEqual(result, result2)

    def test_custom_fallback(self):
        result = run_command(
            "shellcompletion",
            "complete",
            "--fallback",
            "django_typer.tests.fallback.custom_fallback",
            "shell ",
        )[0]
        self.assertTrue("custom_fallback" in result)

        result = run_command(
            "shellcompletion",
            "complete",
            "--fallback",
            "django_typer.tests.fallback.custom_fallback_cmd_str",
            "shell ",
        )[0]
        self.assertTrue("shell " in result)


class TracebackTests(TestCase):
    """
    Tests that show CommandErrors and UsageErrors do not result in tracebacks unless --traceback is set.

    Also make sure that sys.exit is not called when not run from the terminal
    (i.e. in get_command invocation or call_command).
    """

    def test_usage_error_no_tb(self):
        stdout, stderr, retcode = run_command("tb", "--no-color", "wrong")
        self.assertTrue("Usage: ./manage.py tb [OPTIONS] COMMAND [ARGS]" in stdout)
        self.assertTrue("No such command" in stderr)
        self.assertTrue(retcode > 0)

        stdout, stderr, retcode = run_command("tb", "--no-color", "error", "wrong")
        self.assertTrue("Usage: ./manage.py tb error [OPTIONS]" in stdout)
        self.assertTrue("Got unexpected extra argument" in stderr)
        self.assertTrue(retcode > 0)

        with self.assertRaises(CommandError):
            call_command("tb", "wrong")

        with self.assertRaises(CommandError):
            call_command("tb", "error", "wrong")

    def test_usage_error_with_tb_if_requested(self):
        stdout, stderr, retcode = run_command(
            "tb", "--no-color", "--traceback", "wrong"
        )
        self.assertFalse(stdout.strip())
        self.assertTrue("Traceback" in stderr)
        if rich_installed:
            self.assertTrue("───── locals ─────" in stderr)
        else:
            self.assertFalse("───── locals ─────" in stderr)
        self.assertTrue("No such command 'wrong'" in stderr)
        self.assertTrue(retcode > 0)

        stdout, stderr, retcode = run_command(
            "tb", "--no-color", "--traceback", "error", "wrong"
        )
        self.assertFalse(stdout.strip())
        self.assertTrue("Traceback" in stderr)
        if rich_installed:
            self.assertTrue("───── locals ─────" in stderr)
        else:
            self.assertFalse("───── locals ─────" in stderr)
        self.assertFalse(stdout.strip())
        self.assertTrue("Got unexpected extra argument" in stderr)
        self.assertTrue(retcode > 0)

        with self.assertRaises(CommandError):
            call_command("tb", "--traceback", "wrong")

        with self.assertRaises(CommandError):
            call_command("tb", "--traceback", "error", "wrong")

    def test_click_exception_retcodes_honored(self):
        self.assertEqual(run_command("vanilla")[2], 0)
        self.assertEqual(run_command("vanilla", "--exit-code=2")[2], 2)

        self.assertEqual(run_command("tb", "exit")[2], 0)
        self.assertEqual(run_command("tb", "exit", "--code=2")[2], 2)

    def test_exit_on_call(self):
        with self.assertRaises(SystemExit):
            call_command("vanilla", "--help")

        with self.assertRaises(SystemExit):
            call_command("vanilla", "--exit-code", "0")

        with self.assertRaises(SystemExit):
            call_command("vanilla", "--exit-code", "1")

        with self.assertRaises(SystemExit):
            call_command("tb", "--help")

        with self.assertRaises(SystemExit):
            call_command("tb", "exit")

        with self.assertRaises(SystemExit):
            call_command("tb", "exit", "--code=1")


class TestHandleAsInit(TestCase):
    def test_handle_as_init_run(self):
        stdout, stderr, retcode = run_command("handle_as_init")
        self.assertTrue("handle" in stdout)
        self.assertFalse(stderr.strip())
        self.assertEqual(retcode, 0)

        stdout, stderr, retcode = run_command("handle_as_init", "subcommand")
        self.assertTrue("subcommand" in stdout)
        self.assertFalse(stderr.strip())
        self.assertEqual(retcode, 0)

    def test_handle_as_init_call(self):
        self.assertEqual(call_command("handle_as_init").strip(), "handle")
        self.assertEqual(
            call_command("handle_as_init", "subcommand").strip(), "subcommand"
        )

    def test_handle_as_init_direct(self):
        self.assertEqual(get_command("handle_as_init")(), "handle")
        self.assertEqual(get_command("handle_as_init", "subcommand")(), "subcommand")
        self.assertEqual(get_command("handle_as_init").subcommand(), "subcommand")


class TestPromptOptions(TestCase):
    def test_run_with_option_prompt(self):
        cmd = interact("prompt", "--no-color", "cmd1", "bckohan")
        cmd.expect("Password: ")
        cmd.sendline("test_password")

        result = cmd.read().decode("utf-8").strip().splitlines()[0]
        self.assertEqual(result, "bckohan test_password")

        cmd = interact("prompt", "--no-color", "cmd2", "bckohan")
        result = cmd.read().decode("utf-8").strip().splitlines()[0]
        self.assertEqual(result, "bckohan None")

        cmd = interact("prompt", "--no-color", "cmd2", "bckohan", "-p")
        cmd.expect("Password: ")
        cmd.sendline("test_password2")
        result = cmd.read().decode("utf-8").strip().splitlines()[0]
        self.assertEqual(result, "bckohan test_password2")

        cmd = interact("prompt", "--no-color", "cmd3", "bckohan")
        result = cmd.read().decode("utf-8").strip().splitlines()[0]
        self.assertEqual(result, "bckohan default")

        cmd = interact("prompt", "--no-color", "cmd3", "bckohan", "-p")
        cmd.expect(r"Password \[default\]: ")
        cmd.sendline("test_password3")
        result = cmd.read().decode("utf-8").strip().splitlines()[0]
        self.assertEqual(result, "bckohan test_password3")

        cmd = interact("prompt", "--no-color", "group1", "cmd4", "bckohan")
        cmd.expect(r"Flag: ")
        cmd.sendline("test_flag")
        cmd.expect(r"Password: ")
        cmd.sendline("test_password4")
        result = cmd.read().decode("utf-8").strip().splitlines()[0]
        self.assertEqual(result, "test_flag bckohan test_password4")

    def test_call_with_option_prompt(self):
        self.assertEqual(
            call_command(
                "prompt", "--no-color", "cmd1", "bckohan", password="test_password"
            ),
            "bckohan test_password",
        )

        self.assertEqual(
            call_command("prompt", "--no-color", "cmd2", "bckohan"), "bckohan None"
        )

        self.assertEqual(
            call_command(
                "prompt", "--no-color", "cmd2", "bckohan", "-p", "test_password2"
            ),
            "bckohan test_password2",
        )

        self.assertEqual(
            call_command("prompt", "--no-color", "cmd3", "bckohan"), "bckohan default"
        )

        self.assertEqual(
            call_command(
                "prompt", "--no-color", "cmd3", "bckohan", password="test_password3"
            ),
            "bckohan test_password3",
        )

        self.assertEqual(
            call_command(
                "prompt",
                "--no-color",
                "group1",
                "-f",
                "test_flag",
                "cmd4",
                "bckohan",
                password="test_password4",
            ),
            "test_flag bckohan test_password4",
        )

    def test_call_group_with_prompt_value(self):
        """
        This is a bug!
        """
        self.assertEqual(
            call_command(
                "prompt",
                "--no-color",
                "group1",
                "cmd4",
                "bckohan",
                flag="test_flag",
                password="test_password4",
            ),
            "test_flag bckohan test_password4",
        )


class TestDefaultParamOverrides(TestCase):
    """
    Tests that overloaded group/command names work as expected.
    """

    def test_override_direct(self):
        override = get_command("override")
        self.assertDictEqual(
            override("path/to/settings", version="1.1"),
            {"settings": "path/to/settings", "version": "1.1"},
        )

    def test_override_cli(self):
        from django_typer.tests.apps.test_app.management.commands.override import VersionEnum

        result = run_command("override", "path/to/settings", "--version", "1.1")[0]
        self.assertEqual(
            result.strip(),
            str(
                {
                    "settings": Path("path/to/settings"),
                    "version": VersionEnum.VERSION1_1,
                }
            ).strip(),
        )

    def test_override_call_command(self):
        from django_typer.tests.apps.test_app.management.commands.override import VersionEnum

        call_command("override", "path/to/settings", 1, version="1.1")
        self.assertDictEqual(
            call_command("override", "path/to/settings", 1, version="1.1"),
            {
                "settings": Path("path/to/settings"),
                "version": VersionEnum.VERSION1_1,
                "optional_arg": 1,
            },
        )
