import inspect
import json
import os
import re
import subprocess
import sys
from io import StringIO
from pathlib import Path

import django
import typer
from django.core.management import call_command
from django.test import TestCase, override_settings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from django_typer import get_command
from django_typer.tests.utils import read_django_parameters


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


def run_command(command, *args, parse_json=True):
    cwd = os.getcwd()
    try:
        os.chdir(manage_py.parent)
        result = subprocess.run(
            [sys.executable, f"./{manage_py.name}", command, *args],
            capture_output=True,
            text=True,
        )

        # Check the return code to ensure the script ran successfully
        if result.returncode != 0:
            return result.stderr or result.stdout or ""

        # Parse the output
        if result.stdout:
            if parse_json:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return result.stdout or result.stderr or ""
            return result.stdout
        return result.stderr or ""
    finally:
        os.chdir(cwd)


class BasicTests(TestCase):
    def test_command_line(self):
        self.assertEqual(
            run_command("basic", "a1", "a2"),
            {"arg1": "a1", "arg2": "a2", "arg3": 0.5, "arg4": 1},
        )

        self.assertEqual(
            run_command("basic", "a1", "a2", "--arg3", "0.75", "--arg4", "2"),
            {"arg1": "a1", "arg2": "a2", "arg3": 0.75, "arg4": 2},
        )

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
            str(run_command("basic", "--version")).strip(), django.get_version()
        )

    def test_call_direct(self):
        basic = get_command("basic")
        self.assertEqual(
            json.loads(basic.handle("a1", "a2")),
            {"arg1": "a1", "arg2": "a2", "arg3": 0.5, "arg4": 1},
        )

        from django_typer.tests.test_app.management.commands.basic import (
            Command as Basic,
        )

        self.assertEqual(
            json.loads(Basic()("a1", "a2", arg3=0.75, arg4=2)),
            {"arg1": "a1", "arg2": "a2", "arg3": 0.75, "arg4": 2},
        )


class InterfaceTests(TestCase):
    """
    Make sure the django_typer decorator interfaces match the
    typer decorator interfaces. We don't simply pass variadic arguments
    to the typer decorator because we want the IDE to offer auto complete
    suggestions. This is a "developer experience" concession
    """

    def test_command_interface_matches(self):
        from django_typer import command

        command_params = set(get_named_arguments(command))
        typer_params = set(get_named_arguments(typer.Typer.command))

        self.assertFalse(command_params.symmetric_difference(typer_params))

    def test_callback_interface_matches(self):
        from django_typer import initialize

        initialize_params = set(get_named_arguments(initialize))
        typer_params = set(get_named_arguments(typer.Typer.callback))

        self.assertFalse(initialize_params.symmetric_difference(typer_params))


class MultiTests(TestCase):
    def test_command_line(self):
        self.assertEqual(
            run_command("multi", "cmd1", "/path/one", "/path/two"),
            {"files": ["/path/one", "/path/two"], "flag1": False},
        )

        self.assertEqual(
            run_command("multi", "cmd1", "/path/four", "/path/three", "--flag1"),
            {"files": ["/path/four", "/path/three"], "flag1": True},
        )

        self.assertEqual(
            run_command("multi", "sum", "1.2", "3.5", " -12.3"), sum([1.2, 3.5, -12.3])
        )

        self.assertEqual(run_command("multi", "cmd3"), {})

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
            str(run_command("multi", "--version")).strip(), django.get_version()
        )
        self.assertEqual(
            str(run_command("multi", "--version", "cmd1")).strip(), django.get_version()
        )
        self.assertEqual(
            str(run_command("multi", "--version", "sum")).strip(), django.get_version()
        )
        self.assertEqual(
            str(run_command("multi", "--version", "cmd3")).strip(), django.get_version()
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
        from django_typer.tests.test_app.management.commands.basic import (
            Command as Basic,
        )

        basic = get_command("basic")
        assert basic.__class__ == Basic

        from django_typer.tests.test_app.management.commands.multi import (
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

        from django_typer.tests.test_app.management.commands.callback1 import (
            Command as Callback1,
        )

        callback1 = get_command("callback1")
        assert callback1.__class__ == Callback1

        # callbacks are not commands
        with self.assertRaises(ValueError):
            get_command("callback1", "init")


class CallbackTests(TestCase):
    cmd_name = "callback1"

    def test_helps(self, top_level_only=False):
        buffer = StringIO()
        cmd = get_command(self.cmd_name, stdout=buffer)

        help_output_top = run_command(self.cmd_name, "--help")
        cmd.print_help("./manage.py", self.cmd_name)
        self.assertEqual(help_output_top.strip(), buffer.getvalue().strip())
        self.assertIn(f"Usage: ./manage.py {self.cmd_name} [OPTIONS]", help_output_top)

        if not top_level_only:
            buffer.truncate(0)
            buffer.seek(0)
            callback_help = run_command(self.cmd_name, "5", self.cmd_name, "--help")
            cmd.print_help("./manage.py", self.cmd_name, self.cmd_name)
            self.assertEqual(callback_help.strip(), buffer.getvalue().strip())
            self.assertIn(
                f"Usage: ./manage.py {self.cmd_name} P1 {self.cmd_name} [OPTIONS] ARG1 ARG2",
                callback_help,
            )

    def test_command_line(self):
        self.assertEqual(
            run_command(self.cmd_name, "5", self.cmd_name, "a1", "a2"),
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
            ),
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
            str(run_command(self.cmd_name, "--version")).strip(), django.get_version()
        )
        self.assertEqual(
            str(run_command(self.cmd_name, "--version", "6", self.cmd_name)).strip(),
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
            run_command(cmd, "--settings", "django_typer.tests.settings2", *args)
            self.assertEqual(read_django_parameters().get("settings", None), 2)

    def test_color_params(self):
        for cmd, args in self.commands:
            run_command(cmd, "--no-color", *args)
            self.assertEqual(read_django_parameters().get("no_color", False), True)
            run_command(cmd, "--force-color", *args)
            self.assertEqual(read_django_parameters().get("no_color", True), False)

            result = run_command(cmd, "--force-color", "--no-color", *args)
            self.assertTrue("CommandError" in result)
            self.assertTrue("--no-color" in result)
            self.assertTrue("--force-color" in result)

            call_command(cmd, args, no_color=True)
            self.assertEqual(read_django_parameters().get("no_color", False), True)
            call_command(cmd, args, force_color=True)
            self.assertEqual(read_django_parameters().get("no_color", True), False)
            with self.assertRaises(BaseException):
                call_command(cmd, args, force_color=True, no_color=True)

    def test_pythonpath(self):
        added = str(Path(__file__).parent.absolute())
        self.assertTrue(added not in sys.path)
        for cmd, args in self.commands:
            run_command(cmd, "--pythonpath", added, *args)
            self.assertTrue(added in read_django_parameters().get("python_path", []))

    def test_skip_checks(self):
        for cmd, args in self.commands:
            result = run_command(
                cmd, "--settings", "django_typer.tests.settings_fail_check", *args
            )
            self.assertTrue("SystemCheckError" in result)
            self.assertTrue("test_app.E001" in result)

            result = run_command(
                cmd,
                "--skip-checks",
                "--settings",
                "django_typer.tests.settings_fail_check",
                *args,
            )
            self.assertFalse("SystemCheckError" in result)
            self.assertFalse("test_app.E001" in result)

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
            result = run_command(cmd, *args, "--throw")
            if cmd != "dj_params4":
                self.assertFalse("Traceback" in result)
            else:
                self.assertTrue("Traceback" in result)

            if cmd != "dj_params4":
                result_tb = run_command(cmd, "--traceback", *args, "--throw")
                self.assertTrue("Traceback" in result_tb)
            else:
                result_tb = run_command(cmd, "--no-traceback", *args, "--throw")
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
        cmd = get_command("help_precedence1", stdout=buffer)
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
        cmd = get_command("help_precedence2", stdout=buffer)
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
        cmd = get_command("help_precedence3", stdout=buffer)
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
        cmd = get_command("help_precedence4", stdout=buffer)
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
        cmd = get_command("help_precedence5", stdout=buffer)
        cmd.print_help("./manage.py", "help_precedence5")
        self.assertIn(
            "Test minimal TyperCommand subclass - command method", buffer.getvalue()
        )

    def test_help_precedence6(self):
        buffer = StringIO()
        cmd = get_command("help_precedence6", stdout=buffer)
        cmd.print_help("./manage.py", "help_precedence6")
        self.assertIn(
            "Test minimal TyperCommand subclass - docstring", buffer.getvalue()
        )


class TestGroups(TestCase):
    """
    A collection of tests that test complex grouping commands and also that
    command inheritance behaves as expected.
    """
    @override_settings(
        INSTALLED_APPS=[
            "django_typer.tests.test_app",
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
        ]:
            if app == "test_app" and cmds[-1] == "strip":
                continue

            buffer = StringIO()
            cmd = get_command(cmds[0], stdout=buffer)
            cmd.print_help("./manage.py", *cmds)
            hlp = buffer.getvalue()
            self.assertGreater(
                sim := similarity(
                    hlp, (TESTS_DIR / app / "helps" / f"{cmds[-1]}.txt").read_text()
                ),
                0.95,  # width inconsistences drive this number < 1
            )
            print(f'{app}: {" ".join(cmds)} = {sim:.2f}')

    @override_settings(
        INSTALLED_APPS=[
            "django_typer.tests.test_app2",
            "django_typer.tests.test_app",
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
            "django_typer.tests.test_app",
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
            run_command("groups", *settings, "echo", "hey!").strip(),
            call_command("groups", "echo", 'hey!').strip(),
            "hey!"
        )
        self.assertEqual(
            get_command("groups", "echo")("hey!").strip(),
            get_command("groups", "echo")(message="hey!").strip(),
            "hey!"
        )

        result = run_command("groups", *settings, "echo", "hey!", "5")
        if override:
            self.assertEqual(result.strip(), ("hey! " * 5).strip())
        else:
            self.assertIn("UsageError", result)

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
            ).strip(),
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
            ).strip(),
            "-0.03",
        )

        self.assertEqual(
            run_command(
                "groups", *settings, "string", "ANNAmontes", "case", "lower"
            ).strip(),
            "annamontes",
        )

        self.assertEqual(
            run_command(
                "groups", *settings, "string", "annaMONTES", "case", "upper"
            ).strip(),
            "ANNAMONTES",
        )

        self.assertEqual(
            run_command(
                "groups", *settings, "string", "ANNAMONTES", "case", "lower", "4", "9"
            ).strip(),
            "ANNAmonteS",
        )

        result = run_command(
            "groups", *settings, "string", "annamontes", "case", "upper", "4", "9"
        ).strip()
        if override:
            self.assertIn("UsageError", result)
        else:
            self.assertEqual(result, "annaMONTEs")

        result = run_command(
            "groups", *settings, "string", " emmatc  ", "strip", parse_json=False
        )
        if override:
            self.assertEqual(result, "emmatc\n")
        else:
            self.assertIn("UsageError", result)

        self.assertEqual(
            run_command(
                "groups", *settings, "string", "c,a,i,t,l,y,n", "split", "--sep", ","
            ).strip(),
            "c a i t l y n",
        )

    @override_settings(
        INSTALLED_APPS=[
            "django_typer.tests.test_app2",
            "django_typer.tests.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_command_line_override(self):
        self.test_command_line.__wrapped__(self, settings="django_typer.tests.override")
