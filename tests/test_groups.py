import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from django_typer.management import get_command
from tests.utils import TESTS_DIR, manage_py, run_command, similarity, rich_installed


class TestGroups(TestCase):
    """
    A collection of tests that test complex grouping commands and also that
    command inheritance behaves as expected.
    """

    def test_group_call(self):
        with self.assertRaises(NotImplementedError):
            get_command("groups")()

    @pytest.mark.skip()
    def test_get_help_from_incongruent_path(self):
        """
        The directory change screws up the code coverage - it makes the omitted
        directories get included because their relative paths dont resolve in the
        coverage output for this test. VERY ANNOYING - not sure how to fix?

        https://github.com/django-commons/django-typer/issues/44
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
                            ).read_text(encoding="utf-8"),
                        ),
                        0.99,  # width inconsistences drive this number < 1
                    )
                    return
        finally:
            os.chdir(cwd)

    @pytest.mark.rich
    @pytest.mark.no_rich
    @override_settings(
        INSTALLED_APPS=[
            "tests.apps.test_app",
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
            helps_dir = "helps" if rich_installed else "helps_no_rich"
            self.assertGreater(
                sim := similarity(
                    hlp,
                    (
                        TESTS_DIR / "apps" / app / helps_dir / f"{cmds[-1]}.txt"
                    ).read_text(encoding="utf-8"),
                ),
                0.99,  # width inconsistences drive this number < 1
            )
            print(f"{app}: {' '.join(cmds)} = {sim:.2f}")

            cmd = get_command(cmds[0], stdout=buffer, force_color=True)
            cmd.print_help("./manage.py", *cmds)
            hlp = buffer.getvalue()
            if rich_installed:
                self.assertTrue("\x1b" in hlp)

    @pytest.mark.rich
    @pytest.mark.no_rich
    @override_settings(
        INSTALLED_APPS=[
            "tests.apps.test_app2",
            "tests.apps.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_helps_override(self):
        print("test_helps_override")
        self.test_helps.__wrapped__(self, app="test_app2")

    @override_settings(
        INSTALLED_APPS=[
            "tests.apps.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_command_line(self, settings=None):
        from tests.apps.test_app.management.commands.groups import (
            Command as Groups,
        )

        override = settings is not None
        settings = ("--settings", settings) if settings else []

        stdout, stderr, retcode = run_command("groups", *settings, "echo", "hey!")
        self.assertEqual(retcode, 0, msg=stderr)
        self.assertEqual(stdout.strip(), "hey!")

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

        self.assertEqual(get_command("groups", Groups).echo("hey!").strip(), "hey!")

        self.assertEqual(
            get_command("groups", Groups).echo(message="hey!").strip(), "hey!"
        )

        result = run_command("groups", "--no-color", *settings, "echo", "hey!", "5")
        if override:
            self.assertEqual(result[0].strip(), ("hey! " * 5).strip())
            self.assertEqual(
                get_command("groups", Groups).echo("hey!", 5).strip(),
                ("hey! " * 5).strip(),
            )
            self.assertEqual(
                get_command("groups", Groups).echo(message="hey!", echoes=5).strip(),
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
            self.assertIn("manage.py groups echo [OPTIONS] {message}", result[0])
            self.assertIn("Got unexpected extra argument(s) (5)", result[1])
            with self.assertRaises(TypeError):
                call_command("groups", "echo", "hey!", echoes=5)
            with self.assertRaises(TypeError):
                get_command("groups", Groups).echo(message="hey!", echoes=5)

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

        grp_cmd = get_command("groups", Groups)
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

        self.assertEqual(
            get_command("groups", Groups).divide(1.2, 3.5, [-12.3]), "-0.03"
        )
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

        grp_cmd = get_command("groups", Groups)
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
                "manage.py groups string {string} case upper [OPTIONS]",
                result[0],
            )
            self.assertIn("Got unexpected extra argument(s) (4 9)", result[1].strip())
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
            self.assertEqual(result[0].strip(), "emmatc")
            self.assertEqual(
                call_command("groups", "string", " emmatc  ", "strip"), "emmatc"
            )
            grp_cmd.string(" emmatc  ")
            self.assertEqual(grp_cmd.strip(), "emmatc")
        else:
            self.assertIn(
                "manage.py groups string [OPTIONS] {string} COMMAND [ARGS]",
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
            "tests.apps.test_app2",
            "tests.apps.test_app",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )
    def test_command_line_override(self):
        self.test_command_line.__wrapped__(self, settings="tests.settings.override")

    def test_no_subgroup_leaks(self):
        with self.assertRaises(CommandError):
            call_command("groups", "case", "--help")


class TestCallCommandArgs(TestCase):
    @override_settings(
        INSTALLED_APPS=[
            "tests.apps.completion",
            "tests.apps.test_app2",
            "tests.apps.test_app",
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

        test_app = apps.get_app_config("test_app")
        test_app2 = apps.get_app_config("test_app2")

        out = StringIO()
        call_command(
            "completion",
            ["test_app", "test_app2"],
            stdout=out,
        )
        printed_options = json.loads(out.getvalue())
        self.assertEqual(
            printed_options,
            ["test_app", "test_app2"],
        )

        out = StringIO()
        printed_options = json.loads(get_command("completion")([test_app, test_app2]))
        self.assertEqual(
            printed_options,
            ["test_app", "test_app2"],
        )
