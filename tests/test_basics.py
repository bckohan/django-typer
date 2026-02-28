import json
from io import StringIO
import pytest

import django
from django.core.management import call_command
from django.test import TestCase

from django_typer.management import TyperCommand, get_command
from tests.utils import run_command, rich_installed
from django_typer.utils import get_current_command


def test_env():
    # a noop test to run the pytest configuration hooks that verify the CI environment
    pass


class BasicTests(TestCase):
    def test_common_options_function(self):
        from django_typer.management import _common_options

        self.assertIsNone(_common_options())

    def test_command_line(self):
        stdout, stderr, retcode = run_command("basic", "a1", "a2")
        self.assertEqual(retcode, 0, msg=stderr)
        self.assertEqual(
            stdout,
            {"arg1": "a1", "arg2": "a2", "arg3": 0.5, "arg4": 1},
        )

        stdout, stderr, retcode = run_command(
            "basic", "a1", "a2", "--arg3", "0.75", "--arg4", "2"
        )
        self.assertEqual(retcode, 0, msg=stderr)
        self.assertEqual(
            stdout,
            {"arg1": "a1", "arg2": "a2", "arg3": 0.75, "arg4": 2},
        )

    def test_cmd_name(self):
        self.assertEqual(
            get_command("shellcompletion", TyperCommand)._name, "shellcompletion"
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
            str(run_command("basic", "--version")[0]).strip(), django.get_version()
        )

    def test_call_direct(self):
        basic = get_command("basic")
        self.assertEqual(
            json.loads(basic.handle("a1", "a2")),
            {"arg1": "a1", "arg2": "a2", "arg3": 0.5, "arg4": 1},
        )

        from tests.apps.test_app.management.commands.basic import (
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
        basic = get_command("basic", TyperCommand)
        multi = get_command("multi", TyperCommand)
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
        from tests.apps.test_app.management.commands.rename import (
            Command as Rename,
        )

        stdout, stderr, retcode = run_command("rename", "default")
        self.assertEqual(retcode, 0, msg=stderr)
        self.assertEqual(stdout.strip(), "handle")

        stdout, stderr, retcode = run_command("rename", "renamed")
        self.assertEqual(retcode, 0, msg=stderr)
        self.assertEqual(stdout.strip(), "subcommand1")

        stdout, stderr, retcode = run_command("rename", "renamed2")
        self.assertEqual(retcode, 0, msg=stderr)
        self.assertEqual(stdout.strip(), "subcommand2")

        self.assertEqual(call_command("rename", "default"), "handle")
        self.assertEqual(call_command("rename", "renamed"), "subcommand1")
        self.assertEqual(call_command("rename", "renamed2"), "subcommand2")

        self.assertEqual(get_command("rename", TyperCommand)(), "handle")
        self.assertEqual(get_command("rename", Rename).subcommand1(), "subcommand1")
        self.assertEqual(get_command("rename", Rename).subcommand2(), "subcommand2")

    def test_get_command_make_callable(self):
        args = (1, 2, 3)
        kwargs = {"named": "test!"}
        self.assertEqual(
            get_command("base")(*args, **kwargs), f"base({args}, {kwargs})"
        )

    @pytest.mark.rich
    @pytest.mark.no_rich
    def test_cmd_help_order(self):
        buffer = StringIO()
        cmd = get_command("order", TyperCommand, stdout=buffer, no_color=True)

        cmd.print_help("./manage.py", "order")
        hlp = buffer.getvalue()

        if rich_installed:
            self.assertTrue(
                hlp.index("│ order")
                < hlp.index("│ b")
                < hlp.index("│ a")
                < hlp.index("│ d")
                < hlp.index("│ c")
            )
        else:
            cmd_idx = hlp.index("Commands")
            self.assertTrue(
                hlp.index(" order", cmd_idx)
                < hlp.index(" b", cmd_idx)
                < hlp.index(" a", cmd_idx)
                < hlp.index(" d", cmd_idx)
                < hlp.index(" c", cmd_idx)
            )

        buffer.seek(0)
        buffer.truncate()

        cmd.print_help("./manage.py", "order", "d")
        hlp = buffer.getvalue()

        if rich_installed:
            self.assertTrue(hlp.index("│ g") < hlp.index("│ e") < hlp.index("│ f"))
        else:
            cmd_idx = hlp.index("Commands")
            self.assertTrue(
                hlp.index(" g", cmd_idx)
                < hlp.index(" e", cmd_idx)
                < hlp.index(" f", cmd_idx)
            )

        cmd2 = get_command("order2", TyperCommand, stdout=buffer, no_color=True)

        buffer.seek(0)
        buffer.truncate()

        cmd2.print_help("./manage.py", "order2")
        hlp = buffer.getvalue()

        if rich_installed:
            self.assertTrue(
                hlp.index("│ order2")
                < hlp.index("│ b")
                < hlp.index("│ a ")
                < hlp.index("│ d")
                < hlp.index("│ c")
                < hlp.index("│ bb")
                < hlp.index("│ aa")
            )
        else:
            cmd_idx = hlp.index("Commands")
            self.assertTrue(
                hlp.index(" order2", cmd_idx)
                < hlp.index(" b", cmd_idx)
                < hlp.index(" a", cmd_idx)
                < hlp.index(" d", cmd_idx)
                < hlp.index(" c", cmd_idx)
                < hlp.index(" bb", cmd_idx)
                < hlp.index(" aa", cmd_idx)
            )

        buffer.seek(0)
        buffer.truncate()

        cmd2.print_help("./manage.py", "order2", "d")
        hlp = buffer.getvalue()

        if rich_installed:
            self.assertTrue(
                hlp.index("│ g")
                < hlp.index("│ e")
                < hlp.index("│ f")
                < hlp.index("│ i")
                < hlp.index("│ h")
                < hlp.index("│ x")
            )
        else:
            cmd_idx = hlp.index("Commands")
            self.assertTrue(
                hlp.index(" g", cmd_idx)
                < hlp.index(" e", cmd_idx)
                < hlp.index(" f", cmd_idx)
                < hlp.index(" i", cmd_idx)
                < hlp.index(" h", cmd_idx)
                < hlp.index(" x", cmd_idx)
            )

        buffer.seek(0)
        buffer.truncate()

        cmd2.print_help("./manage.py", "order2", "d", "x")
        hlp = buffer.getvalue()

        if rich_installed:
            self.assertTrue(hlp.index("│ z") < hlp.index("│ y"))
        else:
            cmd_idx = hlp.index("Commands")
            self.assertTrue(hlp.index(" z", cmd_idx) < hlp.index(" y", cmd_idx))

    def test_cmd_metavar(self):
        """
        Test that metavar inheritance and overrides work as expected.
        """
        from tests.apps.test_app.management.commands.metavar import (
            Command as MetavarCommand,
        )

        buffer = StringIO()
        for cmd_name in [
            "metavar",
            "metavar2",
        ]:
            cmd = get_command(cmd_name, MetavarCommand, stdout=buffer, no_color=True)

            cmd.print_help("./manage.py", cmd_name)
            self.assertIn("[CLASS OPTS]", buffer.getvalue())

            buffer.seek(0)
            buffer.truncate()

            cmd.print_help("./manage.py", cmd_name, "cmd")
            self.assertIn("<CMD OPTS>", buffer.getvalue())

            buffer.seek(0)
            buffer.truncate()

            cmd.print_help("./manage.py", cmd_name, "grp")
            self.assertIn("(GRP OPTS)", buffer.getvalue())

            buffer.seek(0)
            buffer.truncate()

            cmd.print_help("./manage.py", cmd_name, "grp", "grp-cmd")
            self.assertIn("<<GRP CMD OPTS>>", buffer.getvalue())

            buffer.seek(0)
            buffer.truncate()

            cmd.print_help("./manage.py", cmd_name, "grp", "subgrp")
            self.assertIn("(GRP OPTS)", buffer.getvalue())

            buffer.seek(0)
            buffer.truncate()

            cmd.print_help("./manage.py", cmd_name, "grp", "subgrp", "subgrp-cmd")
            self.assertIn("(GRP OPTS)", buffer.getvalue())

            buffer.seek(0)
            buffer.truncate()

            cmd.print_help("./manage.py", cmd_name, "grp", "subgrp", "subgrp-cmd2")
            self.assertIn("(SUBGRP CMD2 OPTS)", buffer.getvalue())

        metavar_init1 = get_command(
            "metavar_init", TyperCommand, stdout=buffer, no_color=True
        )
        metavar_init1.print_help("./manage.py", "metavar_init")
        self.assertIn("[OPTIONS]", buffer.getvalue())
        buffer.seek(0)
        buffer.truncate()
        metavar_init2 = get_command(
            "metavar_init2", TyperCommand, stdout=buffer, no_color=True
        )
        metavar_init2.print_help("./manage.py", "metavar_init2")
        self.assertIn("{INIT OPTS}", buffer.getvalue())
        buffer.seek(0)
        buffer.truncate()
        metavar_init3 = get_command(
            "metavar_init3", TyperCommand, stdout=buffer, no_color=True
        )
        metavar_init3.print_help("./manage.py", "metavar_init3")
        self.assertIn("[CLASS OPTS]", buffer.getvalue())

        metavar3 = get_command("metavar3", MetavarCommand, stdout=buffer, no_color=True)
        metavar3.print_help("./manage.py", "metavar3")
        self.assertIn("{INIT OVERRIDE}", buffer.getvalue())

        buffer.seek(0)
        buffer.truncate()

        metavar3.print_help("./manage.py", "metavar3", "cmd")
        self.assertIn("(CMD OVERRIDE)", buffer.getvalue())

        buffer.seek(0)
        buffer.truncate()

        metavar3.print_help("./manage.py", "metavar3", "grp")
        self.assertIn("[GRP OVERRIDE]", buffer.getvalue())
        buffer.seek(0)
        buffer.truncate()

        metavar4 = get_command("metavar4", MetavarCommand, stdout=buffer, no_color=True)
        metavar4.print_help("./manage.py", "metavar4")
        self.assertIn("{SUBCLASS OPTS}", buffer.getvalue())
