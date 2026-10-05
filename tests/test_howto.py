from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings
from contextlib import redirect_stdout

from django_typer.management import TyperCommand, get_command
from tests.utils import rich_installed, run_command, similarity


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestDefaultCmdHowto(TestCase):
    cmd = "default_cmd"

    def test_howto_default_cmd(self):
        from tests.apps.howto.management.commands.default_cmd import (
            Command,
        )

        command = get_command(self.cmd, Command)
        self.assertEqual(command(), "handle")
        self.assertEqual(command.subcommand2(), "subcommand2")
        self.assertEqual(command.subcommand3(), "subcommand3")

        with self.assertRaises(Exception):
            command.handle()

        self.assertEqual(command.subcommand1(), "handle")


class TestDefaultCmdTyperHowto(TestDefaultCmdHowto):
    cmd = "default_cmd_typer"


@pytest.mark.rich
@pytest.mark.skipif(not rich_installed, reason="This test requires rich help output")
@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestGroupsHowto(TestCase):
    cmd = "groups"

    root_help = """

     Usage: ./howto.py groups [OPTIONS] COMMAND [ARGS]...                           

    ╭─ Options ────────────────────────────────────────────────────────────────────╮
    │ --help          Show this message and exit.                                  │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    ╭─ Django ─────────────────────────────────────────────────────────────────────╮
    │ --version                    Show program's version number and exit.         │
    │ --settings           <str>   The Python path to a settings module, e.g.      │
    │                              "myproject.settings.main". If this isn't        │
    │                              provided, the DJANGO_SETTINGS_MODULE            │
    │                              environment variable will be used.              │
    │ --pythonpath         <path>  A directory to add to the Python path, e.g.     │
    │                              "/home/djangoprojects/myproject".               │
    │ --traceback                  Raise on CommandError exceptions                │
    │ --show-locals                Print local variables in tracebacks.            │
    │ --no-color                   Don't colorize the command output.              │
    │ --force-color                Force colorization of the command output.       │
    │ --skip-checks                Skip system checks.                             │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    ╭─ Commands ───────────────────────────────────────────────────────────────────╮
    │ group1                                                                       │
    │ group2                                                                       │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    """

    group1_help = """

     Usage: ./howto.py groups group1 [OPTIONS] COMMAND [ARGS]...                    

    ╭─ Options ────────────────────────────────────────────────────────────────────╮
    │ --common-option    --no-common-option      [default: no-common-option]       │
    │ --help                                     Show this message and exit.       │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    ╭─ Commands ───────────────────────────────────────────────────────────────────╮
    │ grp1-subcommand1                                                             │
    │ grp1-subcommand2                                                             │
    │ subgroup1                                                                    │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    """

    subgroup1_help = """

     Usage: ./howto.py groups group1 subgroup1 [OPTIONS] COMMAND [ARGS]...          

    ╭─ Options ────────────────────────────────────────────────────────────────────╮
    │ --help          Show this message and exit.                                  │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    ╭─ Commands ───────────────────────────────────────────────────────────────────╮
    │ subgrp-command                                                               │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    """

    def test_howto_groups(self):
        stdout = StringIO()

        groups = get_command(self.cmd, TyperCommand, stdout=stdout, no_color=True)

        groups.print_help("./howto.py", "groups")
        self.assertGreaterEqual(
            similarity(stdout.getvalue().strip(), self.root_help.strip()), 0.99
        )
        stdout.truncate(0)
        stdout.seek(0)

        groups.print_help("./howto.py", "groups", "group1")
        self.assertGreaterEqual(
            similarity(stdout.getvalue().strip(), self.group1_help.strip()), 0.99
        )

        stdout.truncate(0)
        stdout.seek(0)

        groups.print_help("./howto.py", "groups", "group1", "subgroup1")
        self.assertGreaterEqual(
            similarity(stdout.getvalue().strip(), self.subgroup1_help.strip()), 0.99
        )

        groups.group1()
        groups.group1.subgroup1()
        groups.group1.subgroup1.subgrp_command()
        groups.group1.grp1_subcommand1()
        groups.group2()

        # also since names are unique this works:
        groups.grp1_subcommand1()
        groups.subgrp_command()


class TestGroupsTyperHowto(TestGroupsHowto):
    cmd = "groups_typer"


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestInitializerHowto(TestCase):
    cmd = "initializer"

    def test_howto_initializer(self):
        from tests.apps.howto.management.commands.initializer import (
            Command,
        )

        command = get_command("initializer", Command)
        command.init(common_option=True)
        self.assertTrue(command.subcommand1())
        command.init(False)
        self.assertFalse(command.subcommand2())


class TestInitializerTyperHowto(TestInitializerHowto):
    cmd = "initializer_typer"


@pytest.mark.rich
@pytest.mark.skipif(not rich_installed, reason="This test requires rich help output")
@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestDefaultOptionsHowto(TestCase):
    cmd = "default_options"

    cmd_help = """

     Usage: ./howto.py default_options [OPTIONS]                                    

    ╭─ Options ────────────────────────────────────────────────────────────────────╮
    │ --help          Show this message and exit.                                  │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    ╭─ Django ─────────────────────────────────────────────────────────────────────╮
    │ --verbosity          <int range> [0<=x<=3]  Verbosity level; 0=minimal       │
    │                                             output, 1=normal output,         │
    │                                             2=verbose output, 3=very verbose │
    │                                             output                           │
    │                                             [default: 1]                     │
    │ --version                                   Show program's version number    │
    │                                             and exit.                        │
    │ --pythonpath         <path>                 A directory to add to the Python │
    │                                             path, e.g.                       │
    │                                             "/home/djangoprojects/myproject… │
    │ --traceback                                 Raise on CommandError exceptions │
    │ --show-locals                               Print local variables in         │
    │                                             tracebacks.                      │
    │ --no-color                                  Don't colorize the command       │
    │                                             output.                          │
    │ --force-color                               Force colorization of the        │
    │                                             command output.                  │
    │ --skip-checks                               Skip system checks.              │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    """

    def test_howto_default_options(self):
        stdout = StringIO()

        groups = get_command(self.cmd, TyperCommand, stdout=stdout, no_color=True)

        groups.print_help("./howto.py", "default_options")
        self.assertGreaterEqual(
            similarity(stdout.getvalue().strip(), self.cmd_help.strip()), 0.99
        )


class TestDefaultOptionsTyperHowto(TestDefaultOptionsHowto):
    cmd = "default_options_typer"


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestConfigureHowto(TestCase):
    cmd = "configure"

    def test_howto_configure(self):
        stdout = StringIO()
        call_command(
            get_command(self.cmd, stdout=stdout, no_color=True), "cmd1", "cmd2"
        )
        self.assertEqual(stdout.getvalue().strip().splitlines()[0:2], ["cmd1", "cmd2"])


class TestConfigureTyperHowto(TestConfigureHowto):
    cmd = "configure_typer"


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestInheritHowto(TestCase):
    cmd1 = "upstream"
    cmd2 = "downstream"

    def test_howto_inherit(self):
        from tests.apps.howto.management.commands import (
            downstream,
            upstream,
        )

        upstream = get_command(
            self.cmd1, upstream.Command, stdout=StringIO(), no_color=True
        )
        downstream = get_command(
            self.cmd2, downstream.Command, stdout=StringIO(), no_color=True
        )
        self.assertEqual(upstream.init(), "upstream:init")
        self.assertEqual(downstream.init(), "downstream:init")

        self.assertEqual(upstream.sub1(), "upstream:sub1")
        self.assertEqual(downstream.sub1(), "downstream:sub1")

        self.assertEqual(upstream.sub2(), "upstream:sub2")
        self.assertEqual(downstream.sub2(), "upstream:sub2")

        self.assertEqual(upstream.grp1(), "upstream:grp1")
        self.assertEqual(downstream.grp1(), "upstream:grp1")

        self.assertEqual(upstream.grp1_cmd1(), "upstream:grp1_cmd1")
        self.assertEqual(downstream.grp1_cmd1(), "upstream:grp1_cmd1")
        self.assertEqual(upstream.grp1.grp1_cmd1(), "upstream:grp1_cmd1")
        self.assertEqual(downstream.grp1.grp1_cmd1(), "upstream:grp1_cmd1")

        self.assertEqual(downstream.sub3(), "downstream:sub3")
        self.assertEqual(downstream.grp1_cmd2(), "downstream:grp1_cmd2")
        self.assertEqual(downstream.grp1.grp1_cmd2(), "downstream:grp1_cmd2")

        with self.assertRaises(AttributeError):
            upstream.sub3()

        with self.assertRaises(AttributeError):
            upstream.grp1_cmd2()

        with self.assertRaises(AttributeError):
            upstream.grp1.grp1_cmd2()


class TestInheritTyperHowto(TestInheritHowto):
    cmd1 = "upstream_typer"
    cmd2 = "downstream_typer"


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestPluginHowto(TestCase):
    cmd = "upstream2"

    def test_howto_plugin(self):
        from tests.apps.howto.management.commands import upstream2

        upstream = get_command(
            self.cmd, upstream2.Command, stdout=StringIO(), no_color=True
        )
        self.assertEqual(upstream.init(), "plugin:init")
        self.assertEqual(upstream.sub1(), "plugin:sub1")
        self.assertEqual(upstream.sub2(), "upstream:sub2")
        self.assertEqual(upstream.grp1(), "upstream:grp1")
        self.assertEqual(upstream.grp1_cmd1(), "upstream:grp1_cmd1")
        self.assertEqual(upstream.sub3(), "plugin:sub3")
        self.assertEqual(upstream.grp1_cmd2(), "plugin:grp1_cmd2")
        self.assertEqual(upstream.grp1.grp1_cmd2(), "plugin:grp1_cmd2")


class TestPluginTyperHowto(TestPluginHowto):
    cmd = "upstream2_typer"


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestPrintingHowto(TestCase):
    cmd = "printing"

    def test_howto_printing(self):
        from tests.apps.howto.management.commands.printing import (
            Command,
        )

        stdout = StringIO()
        get_command(self.cmd, Command, stdout=stdout, no_color=True)()
        self.assertEqual(
            stdout.getvalue().strip().splitlines(),
            ["echo does not support styling", "but secho does!"],
        )

        stdout = StringIO()
        get_command(self.cmd, Command, stdout=stdout, force_color=True)()
        self.assertEqual(
            stdout.getvalue().strip().splitlines(),
            ["echo does not support styling", "\x1b[32mbut secho does!\x1b[0m"],
        )


class TestPrintingTyperHowto(TestPrintingHowto):
    cmd = "printing_typer"


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestOrderHowTo(TestCase):
    cmd = "order"

    from tests.apps.howto.management.commands.order import AlphabetizeCommands

    grp_cls = AlphabetizeCommands

    @pytest.mark.rich
    @pytest.mark.no_rich
    def test_howto_order(self):
        from tests.apps.howto.management.commands.order import Command as OrderCommand

        buffer = StringIO()
        order_cmd = get_command(self.cmd, OrderCommand, stdout=buffer, no_color=True)

        self.assertTrue(issubclass(order_cmd.typer_app.info.cls, self.grp_cls))
        self.assertTrue(issubclass(order_cmd.d.info.cls, self.grp_cls))

        order_cmd.print_help("./manage.py", self.cmd)
        hlp = buffer.getvalue()

        if rich_installed:
            self.assertTrue(
                hlp.index("│ a")
                < hlp.index("│ b")
                < hlp.index("│ c")
                < hlp.index("│ d")
            )
        else:
            cmd_idx = hlp.index("Commands")
            self.assertTrue(
                hlp.index(" a", cmd_idx)
                < hlp.index(" b", cmd_idx)
                < hlp.index(" c", cmd_idx)
                < hlp.index(" d", cmd_idx)
            )

        buffer.seek(0)
        buffer.truncate()

        order_cmd.print_help("./manage.py", self.cmd, "d")
        hlp = buffer.getvalue()

        if rich_installed:
            self.assertTrue(hlp.index("│ e") < hlp.index("│ f"))
        else:
            cmd_idx = hlp.index("Commands")
            self.assertTrue(hlp.index(" e", cmd_idx) < hlp.index(" f", cmd_idx))


class TestPrintingTyperHowto(TestOrderHowTo):
    cmd = "order_typer"

    from tests.apps.howto.management.commands.order_typer import AlphabetizeCommands

    grp_cls = AlphabetizeCommands


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestFinalizerHowto(TestCase):
    command = "finalize"

    def test_howto_finalizer_run(self):
        self.assertEqual(
            run_command(
                self.command,
                "--settings",
                "tests.settings.howto",
                "cmd1",
                "cmd1",
                "cmd2",
            )[0].strip(),
            "result1, result1, result2",
        )

    def test_howto_finalizer_call(self):
        self.assertEqual(
            call_command(self.command, "cmd1", "cmd1", "cmd2"),
            "result1, result1, result2",
        )

    def test_howto_finalizer_obj(self):
        from tests.apps.howto.management.commands.finalize import Command

        command = get_command(self.command, Command)
        self.assertEqual(
            command.to_csv([command.cmd1(), command.cmd1(), command.cmd2()]),
            "result1, result1, result2",
        )


class TestFinalizerTyperHowto(TestFinalizerHowto):
    command = "finalize_typer"

    def test_howto_finalizer_obj(self):
        from tests.apps.howto.management.commands.finalize_typer import Command, to_csv

        command = get_command(self.command, Command)
        self.assertEqual(
            to_csv([command.cmd1(), command.cmd1(), command.cmd2()]),
            "result1, result1, result2",
        )


class TestFinalizerTyperExtHowto(TestFinalizerHowto):
    command = "finalize_typer_ext"


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestFinalizerGroupHowto(TestCase):
    command = "finalize_group"

    def test_howto_finalizer_run(self):
        self.assertEqual(
            run_command(
                self.command,
                "--settings",
                "tests.settings.howto",
                "cmd1",
                "cmd1",
                "cmd2",
                "grp",
                "cmd4",
                "cmd3",
            )[0].strip(),
            "result1, result1, result2, RESULT4, RESULT3",
        )

    def test_howto_finalizer_call(self):
        self.assertEqual(
            call_command(self.command, "cmd1", "cmd1", "cmd2", "grp", "cmd4", "cmd3"),
            "result1, result1, result2, RESULT4, RESULT3",
        )

    def test_howto_finalizer_obj(self):
        from tests.apps.howto.management.commands.finalize_group import Command

        command = get_command(self.command, Command)
        self.assertEqual(
            command.to_csv(
                [
                    command.cmd1(),
                    command.cmd1(),
                    command.cmd2(),
                    command.grp.to_upper_csv([command.grp.cmd4(), command.grp.cmd3()]),
                ]
            ),
            "result1, result1, result2, RESULT4, RESULT3",
        )


class TestFinalizerGroupTyperHowto(TestFinalizerGroupHowto):
    command = "finalize_group_typer"

    def test_howto_finalizer_obj(self):
        from tests.apps.howto.management.commands.finalize_group_typer import (
            Command,
            to_csv,
            to_upper_csv,
        )

        command = get_command(self.command, Command)
        self.assertEqual(
            to_csv(
                [
                    command.cmd1(),
                    command.cmd1(),
                    command.cmd2(),
                    to_upper_csv([command.cmd4(), command.cmd3()]),
                ]
            ),
            "result1, result1, result2, RESULT4, RESULT3",
        )


class TestFinalizerGroupTyperExtHowto(TestFinalizerGroupHowto):
    command = "finalize_group_typer_ext"


@override_settings(INSTALLED_APPS=["tests.apps.howto"])
class TestPrintResultHowTo(TestCase):
    command = "print_result"

    def test_howto_print_result_run(self):
        self.assertEqual(
            run_command(self.command, "--settings", "tests.settings.howto")[0].strip(),
            "This will be printed",
        )

    def test_howto_print_result_call(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(call_command(self.command), "This will be printed")
        self.assertEqual(output.getvalue().strip(), "This will be printed")

    def test_howto_print_result_obj(self):
        # calling the function directly never prints
        output = StringIO()
        with redirect_stdout(output):
            command = get_command(self.command)
            self.assertEqual(command.handle(), "This will be printed")
        self.assertEqual(output.getvalue().strip(), "")


class TestPrintResultTyperHowTo(TestPrintResultHowTo):
    command = "print_result_typer"


@override_settings(
    INSTALLED_APPS=[
        "tests.apps.howto",
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]
)
class TestAtomicHowTo(TestCase):
    command = "atomic"

    def test_howto_atomic(self):
        from django.contrib.auth.models import Group

        call_command(self.command, "create", "a", "create", "b", "rename", "a", "c")
        self.assertEqual(
            sorted(Group.objects.values_list("name", flat=True)), ["b", "c"]
        )

        # the failing subcommand rolls back the ones that ran before it
        with self.assertRaises(Group.DoesNotExist):
            call_command(self.command, "create", "d", "delete", "nope")
        self.assertEqual(
            sorted(Group.objects.values_list("name", flat=True)), ["b", "c"]
        )


class TestAtomicTyperHowTo(TestAtomicHowTo):
    command = "atomic_typer"
