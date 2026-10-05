"""
Tests for the typer-native style interface.
"""

import typing as t
from io import StringIO

import pytest
from django import __version__ as DJANGO_VERSION
from django.core.management import call_command
from django.test import TestCase

from django_typer.management import get_command
from tests.utils import rich_installed, run_command, similarity

native_help_rich = """
                                                                                
 Usage: ./manage.py native [OPTIONS] {name}                                     
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    name      <str>  [required]                                             │
╰──────────────────────────────────────────────────────────────────────────────╯
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
"""

native_help_no_rich = """
Usage: ./manage.py native [OPTIONS] {name}

Arguments:
  name  [required]

Options:
  --version            Show program's version number and exit.
  --settings <str>     The Python path to a settings module, e.g.
                       "myproject.settings.main". If this isn't provided, the
                       DJANGO_SETTINGS_MODULE environment variable will be
                       used.
  --pythonpath <path>  A directory to add to the Python path, e.g.
                       "/home/djangoprojects/myproject".
  --traceback          Raise on CommandError exceptions
  --no-color           Don't colorize the command output.
  --force-color        Force colorization of the command output.
  --skip-checks        Skip system checks.
  --help               Show this message and exit.
"""

native_groups_help_rich = """
                                                                                
 Usage: ./manage.py native_groups [OPTIONS] COMMAND [ARGS]...                   
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Django ─────────────────────────────────────────────────────────────────────╮
│ --verbosity          <int range> [0<=x<=3]  Verbosity level; 0=minimal       │
│                                             output, 1=normal output,         │
│                                             2=verbose output, 3=very verbose │
│                                             output                           │
│                                             [default: 0]                     │
│ --version                                   Show program's version number    │
│                                             and exit.                        │
│ --settings           <str>                  The Python path to a settings    │
│                                             module, e.g.                     │
│                                             "myproject.settings.main". If    │
│                                             this isn't provided, the         │
│                                             DJANGO_SETTINGS_MODULE           │
│                                             environment variable will be     │
│                                             used.                            │
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
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ main                                                                         │
│ grp1                                                                         │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_groups_main_help_rich = """
                                                                                
 Usage: ./manage.py native_groups main [OPTIONS] {name}                         
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    name      <str>  [required]                                             │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_groups_grp1_help_rich = """
                                                                                
 Usage: ./manage.py native_groups grp1 [OPTIONS] COMMAND [ARGS]...              
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --flag    --no-flag      [default: no-flag]                                  │
│ --help                   Show this message and exit.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ cmd2                                                                         │
│ cmd1                                                                         │
│ subgrp                                                                       │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_groups_grp1_subgrp_help_rich = """
                                                                                
 Usage: ./manage.py native_groups grp1 subgrp [OPTIONS] {msg} COMMAND [ARGS]... 
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    msg      <str>  [required]                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_groups_grp1_cmd1_help_rich = """
                                                                                
 Usage: ./manage.py native_groups grp1 cmd1 [OPTIONS] {count}                   
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    count      <int>  [required]                                            │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_groups_grp1_cmd2_help_rich = """
                                                                                
 Usage: ./manage.py native_groups grp1 cmd2 [OPTIONS] {fraction}                
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    fraction      <float>  [required]                                       │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
"""


class TestNative(TestCase):
    """
    Tests that native-typer style interface works as expected.
    """

    command = "native"
    native_help_rich = native_help_rich
    native_help_no_rich = native_help_no_rich

    settings = []

    def test_native_direct(self):
        native = get_command(self.command)
        self.assertEqual(native.main("Brian"), {"name": "Brian"})

    def test_native_cli(self):
        stdout, stderr, retcode = run_command(self.command, *self.settings, "Brian")
        self.assertEqual(retcode, 0, stderr)
        self.assertEqual(stdout.strip(), str({"name": "Brian"}))
        self.assertEqual(
            str(run_command(self.command, *self.settings, "--version")[0]).strip(),
            DJANGO_VERSION,
        )

    @pytest.mark.rich
    @pytest.mark.skipif(not rich_installed, reason="rich is not installed")
    def test_native_help_rich(self):
        stdout = StringIO()
        native = get_command(self.command, no_color=True, stdout=stdout)
        native.print_help("./manage.py", self.command)
        sim = similarity(
            self.native_help_rich.replace(" native ", f" {self.command} "),
            stdout.getvalue(),
        )
        print(f"{self.command} --help similiarity: {sim}")
        self.assertGreater(sim, 0.99)

    @pytest.mark.no_rich
    @pytest.mark.skipif(rich_installed, reason="rich is installed")
    def test_native_help_no_rich(self):
        stdout = StringIO()
        native = get_command(self.command, no_color=True, stdout=stdout)
        native.print_help("./manage.py", self.command)
        sim = similarity(
            self.native_help_no_rich.replace(" native ", f" {self.command} "),
            stdout.getvalue(),
        )
        print(f"{self.command} --help similiarity: {sim}")
        self.assertGreater(sim, 0.99)

    def test_native_call_command(self):
        self.assertEqual(call_command(self.command, "Brian"), {"name": "Brian"})


class TestNativeWithSelf(TestNative):
    command = "native_self"


class TestNativeGroups(TestCase):
    command = "native_groups"

    settings = []

    commands = [
        ("{command}", native_groups_help_rich),
        ("{command} main", native_groups_main_help_rich),
        ("{command} grp1", native_groups_grp1_help_rich),
        ("{command} grp1 subgrp", native_groups_grp1_subgrp_help_rich),
        ("{command} grp1 cmd1", native_groups_grp1_cmd1_help_rich),
        ("{command} grp1 cmd2", native_groups_grp1_cmd2_help_rich),
    ]

    @pytest.mark.rich
    @pytest.mark.skipif(not rich_installed, reason="rich is not installed")
    def test_native_groups_helps(self):
        for cmd_pth, expected_help in self.commands:
            cmd_pth = cmd_pth.format(command=self.command)
            expected_help = expected_help.replace(
                " native_groups ", f" {self.command} "
            )
            stdout = StringIO()
            native_groups = get_command(self.command, no_color=True, stdout=stdout)
            native_groups.print_help("./manage.py", *(cmd_pth.split()))
            sim = similarity(expected_help, stdout.getvalue())
            print(f"print_help({cmd_pth}) --help similiarity: {sim}")
            self.assertGreater(sim, 0.99)

            parts = cmd_pth.split()
            sim = similarity(
                expected_help,
                run_command(
                    *[parts[0], *self.settings, "--no-color", *parts[1:]], "--help"
                )[0].strip(),
            )
            print(
                f"run_command({cmd_pth}) {' '.join(self.settings)} --help similiarity: {sim}"
            )
            self.assertGreater(sim, 0.99)

    def test_native_groups_direct(self):
        native_groups: t.Any = get_command(self.command)
        native_groups.init(verbosity=3)
        self.assertEqual(native_groups.main("Brian"), {"verbosity": 3, "name": "Brian"})

        with self.assertRaises(TypeError):
            native_groups.init(verbosity=3, fog=False)

        native_groups.init_grp1(flag=True)

        self.assertEqual(
            native_groups.cmd1(5), {"verbosity": 3, "flag": True, "count": 5}
        )
        native_groups.cmd1(5)

        native_groups.init_grp1()
        self.assertEqual(
            native_groups.cmd2(3.5), {"verbosity": 3, "flag": False, "fraction": 3.5}
        )

    def test_native_groups_direct_run_subgrp(self, flag=False):
        native_groups: t.Any = get_command(self.command)
        native_groups.init(verbosity=3)
        native_groups.init_grp1(flag=flag)
        self.assertEqual(
            native_groups.run_subgrp("hello!"),
            {"verbosity": 3, "flag": flag, "msg": "hello!"},
        )
        self.assertEqual(
            native_groups.subgrp("hello!"),
            {"verbosity": 3, "flag": flag, "msg": "hello!"},
        )

    def test_native_groups_run(self):
        self.assertEqual(
            run_command(
                self.command, *self.settings, "--verbosity", "3", "main", "Brian"
            )[0].strip(),
            str({"verbosity": 3, "name": "Brian"}),
        )

        self.assertEqual(
            run_command(
                self.command,
                *self.settings,
                "--verbosity",
                "2",
                "grp1",
                "--flag",
                "cmd1",
                "5",
            )[0].strip(),
            str({"verbosity": 2, "flag": True, "count": 5}),
        )

        self.assertEqual(
            run_command(
                self.command, *self.settings, "--verbosity", "1", "grp1", "cmd2", "2.5"
            )[0].strip(),
            str({"verbosity": 1, "flag": False, "fraction": 2.5}),
        )

    def test_native_groups_run_subgrp(self, flag=False):
        self.assertEqual(
            run_command(self.command, *self.settings, "grp1", "subgrp", "42!")[
                0
            ].strip(),
            str({"verbosity": 0, "flag": flag, "msg": "42!"}),
        )

    def test_native_groups_call(self):
        self.assertEqual(
            call_command(self.command, "main", "Brian", verbosity=3),
            {"verbosity": 3, "name": "Brian"},
        )

        self.assertEqual(
            call_command(self.command, "grp1", "cmd1", "5", verbosity=2, flag=True),
            {"verbosity": 2, "flag": True, "count": 5},
        )

        self.assertEqual(
            call_command(self.command, "--verbosity", "1", "grp1", "cmd2", "2.5"),
            {"verbosity": 1, "flag": False, "fraction": 2.5},
        )

    def test_native_groups_call_subgrp(self, flag=False):
        self.assertEqual(
            call_command(self.command, "grp1", "subgrp", "42!", flag=flag),
            {"verbosity": 0, "flag": flag, "msg": "42!"},
        )


class TestNativeGroupsWithSelf(TestNativeGroups):
    command = "native_groups_self"


native_tweaks_help_rich = """
                                                                                
 Usage: ./manage.py native_tweaks [OPTIONS] {name}                              
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    name      <str>  [required]                                             │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Django ─────────────────────────────────────────────────────────────────────╮
│ --version                                  Show program's version number and │
│                                            exit.                             │
│ --verbosity         <int range> [0<=x<=3]  Verbosity level; 0=minimal        │
│                                            output, 1=normal output,          │
│                                            2=verbose output, 3=very verbose  │
│                                            output                            │
│                                            [default: 1]                      │
│ --settings          <str>                  The Python path to a settings     │
│                                            module, e.g.                      │
│                                            "myproject.settings.main". If     │
│                                            this isn't provided, the          │
│                                            DJANGO_SETTINGS_MODULE            │
│                                            environment variable will be      │
│                                            used.                             │
│ --pythonpath        <path>                 A directory to add to the Python  │
│                                            path, e.g.                        │
│                                            "/home/djangoprojects/myproject". │
│ --no-color                                 Don't colorize the command        │
│                                            output.                           │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_tweaks_help_no_rich = """
Usage: ./manage.py native_tweaks [OPTIONS] {name}

Arguments:
  name  [required]

Options:
  --version                Show program's version number and exit.
  --verbosity <int range>  Verbosity level; 0=minimal output, 1=normal output,
                           2=verbose output, 3=very verbose output  [default:
                           1; 0<=x<=3]
  --settings <str>         The Python path to a settings module, e.g.
                           "myproject.settings.main". If this isn't provided,
                           the DJANGO_SETTINGS_MODULE environment variable
                           will be used.
  --pythonpath <path>      A directory to add to the Python path, e.g.
                           "/home/djangoprojects/myproject".
  --no-color               Don't colorize the command output.
  --help                   Show this message and exit.
"""


class TestNativeTweaks(TestNative):
    command = "native_tweaks"

    native_help_rich = native_tweaks_help_rich
    native_help_no_rich = native_tweaks_help_no_rich


class TestBug145(TestCase):
    def test_bug_145(self):
        self.assertEqual(call_command("bug_145", "grp", "cmd"), "grp:cmd")
