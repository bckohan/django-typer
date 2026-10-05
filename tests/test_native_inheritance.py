"""
Tests for the typer-native style interface.
"""

from django.core.management import call_command

from django_typer.management import get_command
from tests.utils import run_command

from . import test_native


class TestNativeInheritance(test_native.TestNative):
    command = "native_inheritance1"


class TestNativeInheritanceWithSelf(test_native.TestNative):
    command = "native_inheritance2"


class TestNativeInheritanceGroups(test_native.TestNativeGroups):
    command = "native_inheritance3"


class TestNativeInheritanceGroupsWithSelf(test_native.TestNativeGroups):
    command = "native_inheritance4"


native_override_init_help_rich = """
                                                                                
 Usage: ./manage.py native_override_init [OPTIONS] COMMAND [ARGS]...            
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --fog     --no-fog      [default: no-fog]                                    │
│ --help                  Show this message and exit.                          │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Django ─────────────────────────────────────────────────────────────────────╮
│ --verbosity        <int range> [0<=x<=3]  Verbosity level; 0=minimal output, │
│                                           1=normal output, 2=verbose output, │
│                                           3=very verbose output              │
│                                           [default: 0]                       │
│ --version                                 Show program's version number and  │
│                                           exit.                              │
│ --settings         <str>                  The Python path to a settings      │
│                                           module, e.g.                       │
│                                           "myproject.settings.main". If this │
│                                           isn't provided, the                │
│                                           DJANGO_SETTINGS_MODULE environment │
│                                           variable will be used.             │
│ --no-color                                Don't colorize the command output. │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ main                                                                         │
│ grp1  Override GRP1 (initialize only)                                        │
╰──────────────────────────────────────────────────────────────────────────────╯
"""


native_override_init_grp1_help_rich = """
                                                                                
 Usage: ./manage.py native_override_init grp1 [OPTIONS] COMMAND [ARGS]...       
                                                                                
 Override GRP1 (initialize only)                                                
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --flag        <int>  [default: 4]                                            │
│ --help               Show this message and exit.                             │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ cmd2                                                                         │
│ cmd1                                                                         │
│ subgrp                                                                       │
╰──────────────────────────────────────────────────────────────────────────────╯
"""


class TestNativeInitOverride(test_native.TestNativeGroups):
    command = "native_override_init"

    commands = [
        ("{command}", native_override_init_help_rich),
        ("{command} main", test_native.native_groups_main_help_rich),
        ("{command} grp1", native_override_init_grp1_help_rich),
        ("{command} grp1 subgrp", test_native.native_groups_grp1_subgrp_help_rich),
        ("{command} grp1 cmd1", test_native.native_groups_grp1_cmd1_help_rich),
        ("{command} grp1 cmd2", test_native.native_groups_grp1_cmd2_help_rich),
    ]

    def test_native_groups_direct(self):
        native_groups = get_command(self.command)
        native_groups.init(verbosity=3)
        self.assertEqual(native_groups.main("Brian"), {"verbosity": 3, "name": "Brian"})

        native_groups.init_grp1(flag=8)

        self.assertEqual(native_groups.cmd1(5), {"verbosity": 3, "flag": 8, "count": 5})
        native_groups.cmd1(5)

        native_groups.init_grp1()
        self.assertEqual(
            native_groups.cmd2(3.5), {"verbosity": 3, "flag": 4, "fraction": 3.5}
        )
        self.assertEqual(
            native_groups.init(fog=True, verbosity=7), {"verbosity": 7, "fog": True}
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
                "3",
                "cmd1",
                "5",
            )[0].strip(),
            str({"verbosity": 2, "flag": 3, "count": 5}),
        )

        self.assertEqual(
            run_command(
                self.command, *self.settings, "--verbosity", "1", "grp1", "cmd2", "2.5"
            )[0].strip(),
            str({"verbosity": 1, "flag": 4, "fraction": 2.5}),
        )

    def test_native_groups_call(self):
        self.assertEqual(
            call_command(self.command, "main", "Brian", verbosity=3),
            {"verbosity": 3, "name": "Brian"},
        )

        self.assertEqual(
            call_command(self.command, "grp1", "cmd1", "5", verbosity=2, flag=9),
            {"verbosity": 2, "flag": 9, "count": 5},
        )

        self.assertEqual(
            call_command(
                self.command, "--verbosity", "1", "grp1", "--flag", "2", "cmd2", "2.5"
            ),
            {"verbosity": 1, "flag": 2, "fraction": 2.5},
        )

    def test_native_groups_direct_run_subgrp(self, flag=3):
        return super().test_native_groups_direct_run_subgrp(flag=flag)

    def test_native_groups_call_subgrp(self, flag=6):
        super().test_native_groups_call_subgrp(flag=flag)

    def test_native_groups_run_subgrp(self, flag=4):
        super().test_native_groups_run_subgrp(flag=flag)


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


native_override_grp1_help_rich = """
                                                                                
 Usage: ./manage.py native_override grp1 [OPTIONS] COMMAND [ARGS]...            
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --flag    --no-flag      [default: no-flag]                                  │
│ --help                   Show this message and exit.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ cmd2                                                                         │
│ cmd1                                                                         │
│ subgrp  Override SUBGROUP                                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_override_subgrp_help_rich = """
                                                                                
 Usage: ./manage.py native_override grp1 subgrp [OPTIONS] COMMAND [ARGS]...     
                                                                                
 Override SUBGROUP                                                              
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --option1    --no-option1      [default: no-option1]                         │
│ --option2    --no-option2      [default: no-option2]                         │
│ --help                         Show this message and exit.                   │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ sg-cmd1  Subgroup command 1. No args.                                        │
│ sg-cmd2  Subgroup command 2, Takes an int.                                   │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_override_sgcmd1_help_rich = """
                                                                                
 Usage: ./manage.py native_override grp1 subgrp sg-cmd1 [OPTIONS]               
                                                                                
 Subgroup command 1. No args.                                                   
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

native_override_sgcmd2_help_rich = """
                                                                                
 Usage: ./manage.py native_override grp1 subgrp sg-cmd2 [OPTIONS] {number}      
                                                                                
 Subgroup command 2, Takes an int.                                              
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    number      <int>  [required]                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
"""


class TestNativeOverrides(test_native.TestNativeGroups):
    command = "native_override"

    commands = [
        ("{command}", test_native.native_groups_help_rich),
        ("{command} main", test_native.native_groups_main_help_rich),
        ("{command} grp1", native_override_grp1_help_rich),
        ("{command} grp1 subgrp", native_override_subgrp_help_rich),
        ("{command} grp1 subgrp sg-cmd1", native_override_sgcmd1_help_rich),
        ("{command} grp1 subgrp sg-cmd2", native_override_sgcmd2_help_rich),
        ("{command} grp1 cmd1", test_native.native_groups_grp1_cmd1_help_rich),
        ("{command} grp1 cmd2", test_native.native_groups_grp1_cmd2_help_rich),
    ]

    def test_native_groups_direct_run_subgrp(self):
        native_groups = get_command(self.command)
        native_groups.init(verbosity=3)
        native_groups.init_grp1(flag=True)
        native_groups.subgrp(option2=False, option1=True)
        self.assertEqual(
            native_groups.sg_cmd1(),
            {"verbosity": 3, "flag": True, "option1": True, "option2": False},
        )
        self.assertEqual(
            native_groups.sg_cmd2(7),
            {
                "verbosity": 3,
                "flag": True,
                "option1": True,
                "option2": False,
                "number": 7,
            },
        )

    def test_native_groups_run_subgrp(self):
        self.assertEqual(
            run_command(
                self.command,
                *self.settings,
                "--verbosity",
                "1",
                "grp1",
                "subgrp",
                "--option1",
                "sg-cmd1",
            )[0].strip(),
            str({"verbosity": 1, "flag": False, "option1": True, "option2": False}),
        )

        self.assertEqual(
            run_command(
                self.command,
                *self.settings,
                "--verbosity",
                "2",
                "grp1",
                "--flag",
                "subgrp",
                "--option2",
                "sg-cmd2",
                "5",
            )[0].strip(),
            str(
                {
                    "verbosity": 2,
                    "flag": True,
                    "option1": False,
                    "option2": True,
                    "number": 5,
                }
            ),
        )

    def test_native_groups_call_subgrp(self):
        self.assertEqual(
            call_command(
                self.command,
                "--verbosity",
                "3",
                "grp1",
                "subgrp",
                "--no-option2",
                "sg-cmd1",
                option1=True,
                flag=True,
            ),
            {"verbosity": 3, "flag": True, "option1": True, "option2": False},
        )

        self.assertEqual(
            call_command(
                self.command,
                "grp1",
                "--flag",
                "subgrp",
                "--option2",
                "sg-cmd2",
                "5",
                verbosity=2,
            ),
            {
                "verbosity": 2,
                "flag": True,
                "option1": False,
                "option2": True,
                "number": 5,
            },
        )
