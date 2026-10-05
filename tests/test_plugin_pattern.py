import sys
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from django_typer.management import get_command
from tests.utils import rich_installed, run_command, similarity

adapted_help = """
Usage: ./manage.py adapted [OPTIONS] COMMAND [ARGS]...

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

Commands:
  adapted
  echo     Echo both messages.
  no-self
"""

adapted_adapted_help = """
Usage: ./manage.py adapted adapted [OPTIONS] {message}

Arguments:
  message  [required]

Options:
  --help  Show this message and exit.
"""

adapted_rich_help = """
                                                                                
 Usage: ./manage.py adapted [OPTIONS] COMMAND [ARGS]...                         
                                                                                
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
│ adapted                                                                      │
│ echo     Echo both messages.                                                 │
│ no-self                                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

adapted_adapted_rich_help = """
                                                                                
 Usage: ./manage.py adapted adapted [OPTIONS] {message}                         
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    message      <str>  [required]                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

adapted_echo_help = """
Usage: ./manage.py adapted echo [OPTIONS] {msg1} {msg2}

  Echo both messages.

Arguments:
  msg1  [required]
  msg2  [required]

Options:
  --help  Show this message and exit.
"""

adapted_echo_rich_help = """
                                                                                
 Usage: ./manage.py adapted echo [OPTIONS] {msg1} {msg2}                        
                                                                                
 Echo both messages.                                                            
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    msg1      <str>  [required]                                             │
│ *    msg2      <str>  [required]                                             │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
"""

adapted_help_no_adapters = """
                                                                                
 Usage: ./manage.py adapted [OPTIONS] {message}                                 
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    message      <str>  [required]                                          │
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
adapted_help_no_adapters_no_rich = """
Usage: ./manage.py adapted [OPTIONS] {message}

Arguments:
  message  [required]

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


class ResetAppsMixin:
    @classmethod
    def setUpClass(self):
        from django_typer import utils

        utils._command_extensions = {}
        for mod in list(sys.modules.keys()):
            if any(
                [
                    mod.startswith(path)
                    for path in [
                        "tests.apps.adapter1",
                        "tests.apps.adapter2",
                        "tests.apps.test_app.management.commandstests.apps.adapter0",
                    ]
                ]
            ):
                sys.modules[mod]
                del sys.modules[mod]
        super().setUpClass()


class UnadaptedTests(TestCase):
    @pytest.mark.rich
    @pytest.mark.skipif(not rich_installed, reason="rich is not installed")
    def test_no_adapter_apps(self):
        hlp = run_command("adapted", "--help", "--no-color")[0]
        self.assertGreater(
            sim := similarity(adapted_help_no_adapters, hlp),
            0.99,  # width inconsistences drive this number < 1
        )
        print(f"adapted --help similiarity: {sim}")

    @pytest.mark.no_rich
    @pytest.mark.skipif(rich_installed, reason="rich is installed")
    def test_no_adapter_apps_no_rich(self):
        stdout = StringIO()
        adapted = get_command("adapted", no_color=True, stdout=stdout)
        adapted.print_help("./manage.py", "adapted")
        self.assertGreater(
            sim := similarity(adapted_help_no_adapters_no_rich, stdout.getvalue()),
            0.99,  # width inconsistences drive this number < 1
        )
        print(f"adapted --help similiarity: {sim}")

    def test_adapted_is_compound(self):
        self.assertFalse(get_command("adapted").is_compound_command)


class Adapter2InterferenceTests(ResetAppsMixin, TestCase):
    """
    A very complicated test that adapts a command that is extended
    from another complicated command. This also insures adaptations
    do not unintentionally interfere with upstream base commands.
    """

    def test_adapted2_baseline(self):
        self.assertEqual(
            run_command(
                "adapted2", "--verbosity", "3", "grp2", "--flag1", "grp2-cmd1", "4"
            )[0].strip(),
            "test_app::adapted2(3)::grp2(True)::grp2_cmd1(4)",
        )

        self.assertEqual(
            run_command("adapted2", "--verbosity", "2", "grp2", "grp2-cmd2", "arg")[
                0
            ].strip(),
            "test_app::adapted2(2)::grp2(False)::grp2_cmd2(arg)",
        )

        self.assertEqual(
            call_command("adapted2", "--verbosity", "4", "grp1", "5", "grp1-ext"),
            "test_app::adapted2(4)::grp1(5.0)::grp1_ext()",
        )

        self.assertEqual(
            call_command("adapted2", "grp2", "grp2-cmd1", "arg"),
            "test_app::adapted2(1)::grp2(False)::grp2_cmd1(arg)",
        )

        with self.assertRaises(CommandError):
            # 6 is out of bounds
            call_command("adapted2", "--verbosity", "6", "grp1", "5", "grp1-ext")

        with self.assertRaises(CommandError):
            call_command("adapted2", "top1", "a1", "a2")

        with self.assertRaises(CommandError):
            call_command("adapted2", "top2")

        with self.assertRaises(CommandError):
            call_command("adapted2", "grp1", "3", "grp1-adpt1")

        with self.assertRaises(CommandError):
            call_command("adapted2", "grp1", "4", "subgroup", "subsubgroup", "ssg-cmd")


@override_settings(
    INSTALLED_APPS=[
        "tests.apps.adapter0",
        "tests.apps.test_app",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]
)
class AdapterTests(ResetAppsMixin, TestCase):
    def test_adapted_is_compound(self):
        self.assertTrue(get_command("adapted").is_compound_command)

    @pytest.mark.no_rich
    @pytest.mark.skipif(rich_installed, reason="rich is installed")
    def test_adapted_helps_no_rich(self):
        hlp = run_command("adapted", "--settings", "tests.settings.adapted", "--help")[
            0
        ]
        self.assertGreater(
            sim := similarity(adapted_help, hlp),
            0.99,  # width inconsistences drive this number < 1
        )
        print(f"adapted --help similiarity: {sim}")

        hlp = run_command(
            "adapted",
            "--settings",
            "tests.settings.adapted",
            "adapted",
            "--help",
        )[0]
        self.assertGreater(
            sim := similarity(adapted_adapted_help, hlp),
            0.99,  # width inconsistences drive this number < 1
        )
        print(f"adapted adapted --help similiarity: {sim}")

        hlp = run_command(
            "adapted",
            "--settings",
            "tests.settings.adapted",
            "echo",
            "--help",
        )[0]
        self.assertGreater(
            sim := similarity(adapted_echo_help, hlp),
            0.99,  # width inconsistences drive this number < 1
        )
        print(f"adapted echo --help similiarity: {sim}")

    def test_adapted_runs(self):
        self.assertEqual(
            run_command(
                "adapted",
                "--settings",
                "tests.settings.adapted",
                "adapted",
                "hello",
            )[0].strip(),
            "test_app: hello",
        )
        self.assertEqual(
            run_command(
                "adapted",
                "--settings",
                "tests.settings.adapted",
                "echo",
                "hello",
                "world",
            )[0].strip(),
            "test_app2: hello world",
        )

    def test_adapted_calls(self):
        stdout = StringIO()
        call_command("adapted", "adapted", "hello", stdout=stdout)
        self.assertEqual(stdout.getvalue().strip(), "test_app: hello")
        stdout.seek(0)
        call_command("adapted", ["echo", "hello", "world"], stdout=stdout)
        self.assertEqual(stdout.getvalue().strip(), "test_app2: hello world")

    def test_adapted_direct(self):
        stdout = StringIO()
        adapted = get_command("adapted", stdout=stdout)
        adapted("hello")
        self.assertEqual(stdout.getvalue().strip(), "test_app: hello")
        stdout.seek(0)
        adapted.new_echo("hello", "world")
        self.assertEqual(stdout.getvalue().strip(), "test_app2: hello world")

    @pytest.mark.rich
    @pytest.mark.skipif(not rich_installed, reason="rich is not installed")
    def test_adapted_helps(self):
        stdout = StringIO()
        adapted = get_command("adapted", no_color=True, stdout=stdout)
        adapted.print_help("./manage.py", "adapted")
        self.assertGreater(
            sim := similarity(adapted_rich_help, stdout.getvalue()),
            0.99,  # width inconsistences drive this number < 1
        )
        print(f"adapted --help similiarity: {sim}")

        stdout = StringIO()
        adapted = get_command("adapted", no_color=True, stdout=stdout)
        adapted.print_help("./manage.py", "adapted", "adapted")
        self.assertGreater(
            sim := similarity(adapted_adapted_rich_help, stdout.getvalue()),
            0.99,  # width inconsistences drive this number < 1
        )
        print(f"adapted adapted --help similiarity: {sim}")

        stdout = StringIO()
        adapted = get_command("adapted", no_color=True, stdout=stdout)
        adapted.print_help("./manage.py", "adapted", "echo")
        self.assertGreater(
            sim := similarity(adapted_echo_rich_help, stdout.getvalue()),
            0.99,  # width inconsistences drive this number < 1
        )
        print(f"adapted echo --help similiarity: {sim}")


@override_settings(
    INSTALLED_APPS=[
        "tests.apps.adapter0",
        "tests.apps.test_app2",
        "tests.apps.test_app",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]
)
class Adapter2AdaptedLevel1Tests(ResetAppsMixin, TestCase):
    def test_command_adapter_level1(self):
        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted",
                "--verbosity",
                "0",
                "top1",
                "arg1",
                "arg2",
            )[0].strip(),
            "test_app2::adapted2(0)::top1(arg1, arg2)",
        )
        self.assertEqual(
            call_command("adapted2", "--verbosity", "0", "top1", "arg1", "arg2"),
            "test_app2::adapted2(0)::top1(arg1, arg2)",
        )

        with self.assertRaises(CommandError):
            call_command("adapted2", "top1", "arg1")

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        self.assertEqual(
            adapted2.top1("a1", "a2"), "test_app2::adapted2(3)::top1(a1, a2)"
        )

        with self.assertRaises(TypeError):
            adapted2.top1("a1")

    def test_group_adapter_level1(self):
        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted",
                "--verbosity",
                "0",
                "grp1",
                "3",
                "grp1-adpt1",
            )[0].strip(),
            "test_app2::adapted2(0)::grp1(3.0)::grp1_adpt1()",
        )

        self.assertEqual(
            call_command("adapted2", "--verbosity", "2", "grp1", "2.5", "grp1-adpt1"),
            "test_app2::adapted2(2)::grp1(2.5)::grp1_adpt1()",
        )

        with self.assertRaises(CommandError):
            (call_command("adapted2", "grp1", "2.5", "grp1-adpt1", "5"),)

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        adapted2.grp1(3.2)
        self.assertEqual(
            adapted2.grp1_adpt1(), "test_app2::adapted2(3)::grp1(3.2)::grp1_adpt1()"
        )

        with self.assertRaises(TypeError):
            adapted2.grp1_adpt1(4)

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted",
                "--verbosity",
                "0",
                "grp2",
                "--flag1",
                "sub-grp2",
            )[0].strip(),
            "test_app2::adapted2(0)::grp2(True)::sub_grp2()",
        )

        self.assertEqual(
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2"),
            "test_app2::adapted2(2)::grp2(False)::sub_grp2()",
        )

        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2", "5")

        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2", "5", "4")

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        adapted2.grp2(flag1=True)
        self.assertEqual(
            adapted2.sub_grp2(), "test_app2::adapted2(3)::grp2(True)::sub_grp2()"
        )

        with self.assertRaises(TypeError):
            adapted2.sub_grp2(4)

        self.assertFalse(hasattr(adapted2, "subsub_grp2"))
        with self.assertRaises(CommandError):
            call_command(
                "adapted2", "--verbosity", "2", "grp2", "sub-grp2", "subsub-grp2"
            )

        self.assertFalse(hasattr(adapted2, "grp3"))
        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp3")

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted",
                "grp1",
                "5",
                "subgroup",
                "subsubgroup",
                "subsubcommand",
            )[0].strip(),
            "test_app::interference::grp1(5.0)::subgroup(False)::subsubgroup(True)::subsubcommand()",
        )
        self.assertEqual(
            call_command(
                "adapted2",
                "grp1",
                "10",
                "subgroup",
                "subsubgroup",
                "subsubcommand",
                arg5_0=True,
            ),
            "test_app::interference::grp1(10.0)::subgroup(True)::subsubgroup(True)::subsubcommand()",
        )

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted",
                "grp1",
                "5",
                "subgroup",
                "subsubgroup",
                "ssg-cmd",
            )[0].strip(),
            "test_app2::interference::grp1(5.0)::subgroup(False)::subsubgroup(True)::ssg_cmd()",
        )
        self.assertEqual(
            call_command(
                "adapted2",
                "grp1",
                "10",
                "subgroup",
                "subsubgroup",
                "ssg-cmd",
                arg5_0=True,
            ),
            "test_app2::interference::grp1(10.0)::subgroup(True)::subsubgroup(True)::ssg_cmd()",
        )
        adapted2.grp1(3.4)
        adapted2.subgroup(True)
        self.assertEqual(
            adapted2.ssg_cmd(),
            "test_app2::interference::grp1(3.4)::subgroup(True)::subsubgroup(False)::ssg_cmd()",
        )


@override_settings(
    INSTALLED_APPS=[
        "tests.apps.adapter1",
        "tests.apps.adapter0",
        "tests.apps.test_app2",
        "tests.apps.test_app",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]
)
class Adapter2AdaptedLevel2Tests(ResetAppsMixin, TestCase):
    def test_command_adapter_level2(self):
        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "top1",
                "arg1",
            )[0].strip(),
            "adapter1::adapted2(1)::top1(arg1)",
        )
        self.assertEqual(
            call_command("adapted2", "top1", "arg1"),
            "adapter1::adapted2(1)::top1(arg1)",
        )

        with self.assertRaises(CommandError):
            call_command("adapted2", "top1", "arg1", "arg2")

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        self.assertEqual(adapted2.top1("a1"), "adapter1::adapted2(3)::top1(a1)")

        with self.assertRaises(TypeError):
            adapted2.top1()

    def test_group_adapter_level2(self):
        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "--verbosity",
                "0",
                "grp1",
                "3",
                "grp1-adpt1",
                "7",
            )[0].strip(),
            "adapter1::adapted2(0)::grp1(3.0)::grp1_adpt1(7)",
        )

        self.assertEqual(
            call_command(
                "adapted2", "--verbosity", "2", "grp1", "2.5", "grp1-adpt1", "12"
            ),
            "adapter1::adapted2(2)::grp1(2.5)::grp1_adpt1(12)",
        )

        with self.assertRaises(CommandError):
            (call_command("adapted2", "grp1", "2.5", "grp1-adpt1"),)

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        adapted2.grp1(3.2)
        self.assertEqual(
            adapted2.grp1_adpt1(6), "adapter1::adapted2(3)::grp1(3.2)::grp1_adpt1(6)"
        )

        with self.assertRaises(TypeError):
            adapted2.grp1_adpt1()

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "--verbosity",
                "0",
                "grp2",
                "--flag1",
                "sub-grp2",
                "8",
            )[0].strip(),
            "adapter1::adapted2(0)::grp2(True)::sub_grp2(8)",
        )

        self.assertEqual(
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2", "9"),
            "adapter1::adapted2(2)::grp2(False)::sub_grp2(9)",
        )

        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2")

        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2", "5", "4")

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        adapted2.grp2(flag1=True)
        self.assertEqual(
            adapted2.sub_grp2(3), "adapter1::adapted2(3)::grp2(True)::sub_grp2(3)"
        )

        with self.assertRaises(TypeError):
            adapted2.sub_grp2()

        self.assertFalse(hasattr(adapted2, "subsub_grp2"))
        with self.assertRaises(CommandError):
            call_command(
                "adapted2", "--verbosity", "2", "grp2", "sub-grp2", "subsub-grp2"
            )

        self.assertEqual(
            call_command("adapted2", "--verbosity", "2", "grp3"),
            "adapter1::adapted2(2)::grp3()",
        )
        self.assertEqual(adapted2.grp3(), "adapter1::adapted2(3)::grp3()")

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "grp1",
                "5",
                "subgroup",
                "subsubgroup",
                "subsubcommand",
            )[0].strip(),
            "test_app::interference::grp1(5.0)::subgroup(False)::subsubgroup(True)::subsubcommand()",
        )
        self.assertEqual(
            call_command(
                "adapted2",
                "grp1",
                "10",
                "subgroup",
                "subsubgroup",
                "subsubcommand",
                arg5_0=True,
            ),
            "test_app::interference::grp1(10.0)::subgroup(True)::subsubgroup(True)::subsubcommand()",
        )

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "grp1",
                "5",
                "subgroup",
                "subsubgroup",
                "ssg-cmd",
                "0",
            )[0].strip(),
            "adapter1::interference::grp1(5.0)::subgroup(False)::subsubgroup(True)::ssg_cmd(0)",
        )
        self.assertEqual(
            call_command(
                "adapted2",
                "grp1",
                "10",
                "subgroup",
                "subsubgroup",
                "ssg-cmd",
                "2",
                arg5_0=True,
            ),
            "adapter1::interference::grp1(10.0)::subgroup(True)::subsubgroup(True)::ssg_cmd(2)",
        )
        adapted2.grp1(3.4)
        adapted2.subgroup(True)
        self.assertEqual(
            adapted2.ssg_cmd(5),
            "adapter1::interference::grp1(3.4)::subgroup(True)::subsubgroup(False)::ssg_cmd(5)",
        )


@override_settings(
    INSTALLED_APPS=[
        "tests.apps.adapter2",
        "tests.apps.adapter1",
        "tests.apps.adapter0",
        "tests.apps.test_app2",
        "tests.apps.test_app",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]
)
class Adapter2AdaptedLevel3Tests(ResetAppsMixin, TestCase):
    def test_command_adapter_level3(self):
        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1_2",
                "top1",
            )[0].strip(),
            "adapter2::adapted2(1)::top1()",
        )
        self.assertEqual(
            call_command("adapted2", "top1", verbosity=4),
            "adapter2::adapted2(4)::top1()",
        )

        with self.assertRaises(CommandError):
            call_command("adapted2", "top1", "arg1", "arg2")

        with self.assertRaises(CommandError):
            call_command("adapted2", "top1", "arg1")

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=2)
        self.assertEqual(adapted2.top1(), "adapter2::adapted2(2)::top1()")

        with self.assertRaises(TypeError):
            adapted2.top1("a1", "a2")

    def test_group_adapter_level3(self):
        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1_2",
                "--verbosity",
                "0",
                "grp1",
                "3",
                "grp1-adpt1",
                "7",
                "6",
            )[0].strip(),
            "adapter2::adapted2(0)::grp1(3.0)::grp1_adpt1(7, 6)",
        )

        self.assertEqual(
            call_command(
                "adapted2", "--verbosity", "2", "grp1", "2.5", "grp1-adpt1", "12", "8"
            ),
            "adapter2::adapted2(2)::grp1(2.5)::grp1_adpt1(12, 8)",
        )

        with self.assertRaises(CommandError):
            (call_command("adapted2", "grp1", "2.5", "grp1-adpt1"),)

        with self.assertRaises(CommandError):
            (call_command("adapted2", "grp1", "2.5", "grp1-adpt1", "12"),)

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        adapted2.grp1(3.2)
        self.assertEqual(
            adapted2.grp1_adpt1(3, 6),
            "adapter2::adapted2(3)::grp1(3.2)::grp1_adpt1(3, 6)",
        )

        with self.assertRaises(TypeError):
            adapted2.grp1_adpt1()

        with self.assertRaises(TypeError):
            adapted2.grp1_adpt1(55)

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1_2",
                "--verbosity",
                "0",
                "grp2",
                "--flag1",
                "sub-grp2",
                "8",
                "7",
            )[0].strip(),
            "adapter2::adapted2(0)::grp2(True)::sub_grp2(8, 7)",
        )

        self.assertEqual(
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2", "9", "7"),
            "adapter2::adapted2(2)::grp2(False)::sub_grp2(9, 7)",
        )

        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2")

        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2", "5")

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        adapted2.grp2(flag1=True)
        self.assertEqual(
            adapted2.sub_grp2(6, 3),
            "adapter2::adapted2(3)::grp2(True)::sub_grp2(6, 3)",
        )

        with self.assertRaises(TypeError):
            adapted2.sub_grp2()

        with self.assertRaises(TypeError):
            adapted2.sub_grp2(3)

        self.assertEqual(
            call_command(
                "adapted2",
                "--verbosity",
                "2",
                "grp2",
                "sub-grp2",
                "4",
                "5",
                "subsub-grp2",
            ),
            "adapter2::adapted2()::grp2()::sub_grp2()::subsub_grp2()",
        )

        self.assertEqual(
            call_command("adapted2", "--verbosity", "2", "grp3"),
            "adapter1::adapted2(2)::grp3()",
        )
        self.assertEqual(adapted2.grp3(), "adapter1::adapted2(3)::grp3()")

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1_2",
                "grp1",
                "5",
                "subgroup",
                "subsubgroup",
                "subsubcommand",
            )[0].strip(),
            "test_app::interference::grp1(5.0)::subgroup(False)::subsubgroup(True)::subsubcommand()",
        )
        self.assertEqual(
            call_command(
                "adapted2",
                "grp1",
                "10",
                "subgroup",
                "subsubgroup",
                "subsubcommand",
                arg5_0=True,
            ),
            "test_app::interference::grp1(10.0)::subgroup(True)::subsubgroup(True)::subsubcommand()",
        )

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1_2",
                "grp1",
                "5",
                "subgroup",
                "subsubgroup",
                "ssg-cmd",
                "0",
                "1",
            )[0].strip(),
            "adapter2::interference::grp1(5.0)::subgroup(False)::subsubgroup(True)::ssg_cmd(0, 1)",
        )
        self.assertEqual(
            call_command(
                "adapted2",
                "grp1",
                "10",
                "subgroup",
                "subsubgroup",
                "ssg-cmd",
                "2",
                "3",
                arg5_0=True,
            ),
            "adapter2::interference::grp1(10.0)::subgroup(True)::subsubgroup(True)::ssg_cmd(2, 3)",
        )
        adapted2.grp1(3.4)
        adapted2.subgroup(True)
        self.assertEqual(
            adapted2.ssg_cmd(5, 6),
            "adapter2::interference::grp1(3.4)::subgroup(True)::subsubgroup(False)::ssg_cmd(5, 6)",
        )


@override_settings(
    INSTALLED_APPS=[
        "tests.apps.adapter1",
        "tests.apps.adapter2",
        "tests.apps.adapter0",
        "tests.apps.test_app2",
        "tests.apps.test_app",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]
)
class Adapter2AdaptedPrecedenceTests(ResetAppsMixin, TestCase):
    """
    Reverse app stack order and test that we observe the correct app
    winning out.
    """

    def test_command_adapter_precedence(self):
        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted2_1",
                "top1",
                "arg1",
            )[0].strip(),
            "adapter1::adapted2(1)::top1(arg1)",
        )
        self.assertEqual(
            call_command("adapted2", "top1", "arg1"),
            "adapter1::adapted2(1)::top1(arg1)",
        )

        with self.assertRaises(CommandError):
            call_command("adapted2", "top1", "arg1", "arg2")

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        self.assertEqual(adapted2.top1("a1"), "adapter1::adapted2(3)::top1(a1)")

        with self.assertRaises(TypeError):
            adapted2.top1()

    def test_group_adapter_precedence(self):
        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "--verbosity",
                "0",
                "grp1",
                "3",
                "grp1-adpt1",
                "7",
            )[0].strip(),
            "adapter1::adapted2(0)::grp1(3.0)::grp1_adpt1(7)",
        )

        self.assertEqual(
            call_command(
                "adapted2", "--verbosity", "2", "grp1", "2.5", "grp1-adpt1", "12"
            ),
            "adapter1::adapted2(2)::grp1(2.5)::grp1_adpt1(12)",
        )

        with self.assertRaises(CommandError):
            (call_command("adapted2", "grp1", "2.5", "grp1-adpt1"),)

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        adapted2.grp1(3.2)
        self.assertEqual(
            adapted2.grp1_adpt1(6), "adapter1::adapted2(3)::grp1(3.2)::grp1_adpt1(6)"
        )

        with self.assertRaises(TypeError):
            adapted2.grp1_adpt1()

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "--verbosity",
                "0",
                "grp2",
                "--flag1",
                "sub-grp2",
                "8",
            )[0].strip(),
            "adapter1::adapted2(0)::grp2(True)::sub_grp2(8)",
        )

        self.assertEqual(
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2", "9"),
            "adapter1::adapted2(2)::grp2(False)::sub_grp2(9)",
        )

        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2")

        with self.assertRaises(CommandError):
            call_command("adapted2", "--verbosity", "2", "grp2", "sub-grp2", "5", "4")

        adapted2 = get_command("adapted2")
        adapted2.init(verbosity=3)
        adapted2.grp2(flag1=True)
        self.assertEqual(
            adapted2.sub_grp2(3), "adapter1::adapted2(3)::grp2(True)::sub_grp2(3)"
        )

        with self.assertRaises(TypeError):
            adapted2.sub_grp2()

        # this doesnt work because adapter1 overrides the whole subgroup
        with self.assertRaises(CommandError):
            call_command(
                "adapted2", "--verbosity", "2", "grp2", "sub-grp2", "4", "subsub-grp2"
            )

        self.assertFalse(hasattr(adapted2.__class__, "subsub_grp2"))
        self.assertFalse(hasattr(adapted2, "subsub_grp2"))

        self.assertEqual(
            call_command("adapted2", "--verbosity", "2", "grp3"),
            "adapter1::adapted2(2)::grp3()",
        )
        self.assertEqual(adapted2.grp3(), "adapter1::adapted2(3)::grp3()")

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "grp1",
                "5",
                "subgroup",
                "subsubgroup",
                "subsubcommand",
            )[0].strip(),
            "test_app::interference::grp1(5.0)::subgroup(False)::subsubgroup(True)::subsubcommand()",
        )
        self.assertEqual(
            call_command(
                "adapted2",
                "grp1",
                "10",
                "subgroup",
                "subsubgroup",
                "subsubcommand",
                arg5_0=True,
            ),
            "test_app::interference::grp1(10.0)::subgroup(True)::subsubgroup(True)::subsubcommand()",
        )

        self.assertEqual(
            run_command(
                "adapted2",
                "--settings",
                "tests.settings.adapted1",
                "grp1",
                "5",
                "subgroup",
                "subsubgroup",
                "ssg-cmd",
                "0",
            )[0].strip(),
            "adapter1::interference::grp1(5.0)::subgroup(False)::subsubgroup(True)::ssg_cmd(0)",
        )
        self.assertEqual(
            call_command(
                "adapted2",
                "grp1",
                "10",
                "subgroup",
                "subsubgroup",
                "ssg-cmd",
                "2",
                arg5_0=True,
            ),
            "adapter1::interference::grp1(10.0)::subgroup(True)::subsubgroup(True)::ssg_cmd(2)",
        )
        adapted2.grp1(3.4)
        adapted2.subgroup(True)
        self.assertEqual(
            adapted2.ssg_cmd(5),
            "adapter1::interference::grp1(3.4)::subgroup(True)::subsubgroup(False)::ssg_cmd(5)",
        )
