import sys
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from django_typer.management import get_command
from tests.utils import read_django_parameters, run_command


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
            run_command(cmd, "--settings", "tests.settings.settings2", *args)
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
                cmd,
                "--settings",
                "tests.settings.settings_fail_check",
                *args,
            )
            self.assertTrue("SystemCheckError" in result[1])
            self.assertTrue("test_app.E001" in result[1])

            result = run_command(
                cmd,
                "--skip-checks",
                "--settings",
                "tests.settings.settings_fail_check",
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
        from tests.apps.test_app.management.commands.override import (
            VersionEnum,
        )

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
        from tests.apps.test_app.management.commands.override import (
            VersionEnum,
        )

        call_command("override", "path/to/settings", 1, version="1.1")
        self.assertDictEqual(
            call_command("override", "path/to/settings", 1, version="1.1"),
            {
                "settings": Path("path/to/settings"),
                "version": VersionEnum.VERSION1_1,
                "optional_arg": 1,
            },
        )

    def test_no_suppression(self):
        self.assertEqual(run_command("dj_params_none_suppressed")[2], 0)
        call_command("dj_params_none_suppressed")

    def test_all_suppressed(self):
        self.assertEqual(run_command("dj_params_all_suppressed")[2], 0)
        call_command("dj_params_all_suppressed")

    def test_all_suppressed_init(self):
        self.assertEqual(run_command("dj_params_all_suppressed_init", "cmd")[2], 0)
        call_command("dj_params_all_suppressed_init", "cmd")

    def test_some_suppressed(self):
        stdout, _, retcode = run_command("dj_params_some_suppressed")
        self.assertEqual(retcode, 0)
        self.assertEqual(stdout.strip(), "traceback=True")

        self.assertEqual(call_command("dj_params_some_suppressed"), "traceback=True")

        stdout, _, retcode = run_command("dj_params_some_suppressed", "--no-traceback")
        self.assertEqual(retcode, 0)
        self.assertEqual(stdout.strip(), "traceback=False")

        self.assertEqual(
            call_command("dj_params_some_suppressed", "--no-traceback"),
            "traceback=False",
        )
        self.assertEqual(
            call_command("dj_params_some_suppressed", traceback=False),
            "traceback=False",
        )

    def test_some_suppressed_init(self, command_name="dj_params_some_suppressed_init"):
        stdout, _, retcode = run_command(command_name)
        self.assertEqual(retcode, 0)
        self.assertTrue("traceback=True" in stdout.strip())

        stdout, _, retcode = run_command(command_name, "cmd")
        self.assertEqual(retcode, 0)
        self.assertTrue("traceback=True" in stdout.strip())

        self.assertTrue("traceback=True" in call_command(command_name))
        self.assertTrue("traceback=True" in call_command(command_name, "cmd"))

        stdout, _, retcode = run_command(command_name, "--no-traceback")
        self.assertEqual(retcode, 0)
        self.assertTrue("traceback=False" in stdout.strip())

        self.assertTrue(
            "traceback=False" in call_command(command_name, "--no-traceback")
        )
        self.assertTrue(
            "traceback=False" in call_command(command_name, traceback=False), "False"
        )

        stdout, _, retcode = run_command(command_name, "--no-traceback", "cmd")
        self.assertEqual(retcode, 0)
        self.assertTrue("traceback=False" in stdout.strip())

        self.assertTrue(
            "traceback=False" in call_command(command_name, "--no-traceback", "cmd")
        )
        self.assertTrue(
            "traceback=False" in call_command(command_name, "cmd", traceback=False)
        )

    def test_some_suppressed_inherit(self):
        self.test_some_suppressed_init("dj_params_inherit")

    def test_some_suppressed_subgroups(self):
        self.test_some_suppressed_init("dj_params_subgroups")
        stdout, _, retcode = run_command(
            "dj_params_subgroups", "--no-traceback", "subgroup", "--no-skip-checks"
        )
        self.assertEqual(retcode, 0)
        self.assertTrue("traceback=False, skipchecks=False" in stdout.strip())

        self.assertTrue(
            "traceback=True, skipchecks=True"
            in call_command(
                "dj_params_subgroups", "--traceback", "subgroup", "--skip-checks"
            )
        )
        self.assertTrue(
            "traceback=False, skipchecks=True"
            in call_command(
                "dj_params_subgroups", "subgroup", traceback=False, skip_checks=True
            )
        )


class TestParsedArgsDefaultOptions(TestCase):
    """
    Django reads settings and pythonpath off the parsed arguments - paths must be
    strings, any other overriding type is left alone.
    """

    def test_only_paths_are_stringified(self):
        from django_typer.management import _ParsedArgs

        parsed = _ParsedArgs(args=[], settings=Path("a/b"), pythonpath=Path("c"))
        self.assertEqual(parsed.settings, str(Path("a/b")))
        self.assertEqual(parsed.pythonpath, "c")
        self.assertEqual(vars(parsed)["settings"], Path("a/b"))

        parsed = _ParsedArgs(args=[], settings=False, pythonpath=[])
        self.assertIs(parsed.settings, False)
        self.assertEqual(parsed.pythonpath, [])

        parsed = _ParsedArgs(args=[])
        self.assertIsNone(parsed.settings)
        self.assertIsNone(parsed.pythonpath)
        parsed.settings = "x"
        parsed.pythonpath = Path("y")
        self.assertEqual((parsed.settings, parsed.pythonpath), ("x", "y"))
