"""
The ``atomic`` option wraps everything execute() runs - initializer, chained
subcommands and finalizer - in one transaction. The transaction commits when the
command ends successfully (a return, typer.Exit(0) or sys.exit(0)) and rolls
back on every other outcome. See https://github.com/django-commons/django-typer/issues/219
"""

import os

from django.core.management import CommandError, call_command
from django.db import connections
from django.test import TestCase, TransactionTestCase

from django_typer.management import TyperCommand, get_command
from tests.apps.test_app.models import ShellCompleteTester
from tests.utils import run_command


def rows(using="default"):
    return ShellCompleteTester.objects.using(using).count()


class AtomicCallCommandTests(TestCase):
    databases = {"default", "other"}

    def chain(self, *args, atomic=True, **options):
        cmd = get_command("atomic_chain")
        cmd.atomic = atomic
        return call_command(cmd, "write", "a", "write", "b", *args, **options)

    def test_atomic_is_off_by_default(self):
        self.assertIs(TyperCommand.atomic, False)

    def test_commits_when_the_command_returns(self):
        self.chain("end", "return")
        self.assertEqual(rows(), 2)

    def test_commits_on_exit_zero(self):
        self.assertIsNone(self.chain("end", "exit0"))
        self.assertEqual(rows(), 2)

    def test_commits_on_sys_exit_zero(self):
        with self.assertRaises(SystemExit) as raised:
            self.chain("end", "sysexit0")
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(rows(), 2)

    def test_rolls_back_on_non_zero_exit(self):
        with self.assertRaises(CommandError) as raised:
            self.chain("end", "exit3")
        self.assertEqual(raised.exception.returncode, 3)
        self.assertEqual(rows(), 0)

    def test_rolls_back_on_abort(self):
        with self.assertRaises(CommandError):
            self.chain("end", "abort")
        self.assertEqual(rows(), 0)

    def test_rolls_back_on_non_zero_sys_exit(self):
        with self.assertRaises(SystemExit) as raised:
            self.chain("end", "sysexit4")
        self.assertEqual(raised.exception.code, 4)
        self.assertEqual(rows(), 0)

    def test_rolls_back_on_interrupt(self):
        with self.assertRaises(KeyboardInterrupt):
            self.chain("end", "interrupt")
        self.assertEqual(rows(), 0)

    def test_rolls_back_on_command_error(self):
        with self.assertRaises(CommandError) as raised:
            self.chain("end", "cmderror")
        self.assertEqual(raised.exception.returncode, 5)
        self.assertEqual(rows(), 0)

    def test_rolls_back_on_unexpected_exception(self):
        with self.assertRaises(ValueError):
            self.chain("end", "valueerror")
        self.assertEqual(rows(), 0)

    def test_rolls_back_when_the_finalizer_fails(self):
        with self.assertRaises(RuntimeError):
            self.chain("end", "return", fail_finalize=True)
        self.assertEqual(rows(), 0)

    def test_earlier_subcommands_persist_when_not_atomic(self):
        with self.assertRaises(ValueError):
            self.chain("end", "valueerror", atomic=False)
        self.assertEqual(rows(), 2)

    def test_direct_calls_are_not_wrapped(self):
        cmd = get_command("atomic_chain")
        cmd.write("a")
        with self.assertRaises(ValueError):
            cmd.end("valueerror")
        self.assertEqual(rows(), 1)

    def test_alias_string_wraps_only_that_database(self):
        with self.assertRaises(ValueError):
            self.chain(
                "write", "--using", "other", "c", "end", "valueerror", atomic="other"
            )
        self.assertEqual(rows("default"), 2)
        self.assertEqual(rows("other"), 0)

    def test_alias_sequence_wraps_each_database(self):
        with self.assertRaises(ValueError):
            self.chain(
                "write",
                "--using",
                "other",
                "c",
                "end",
                "valueerror",
                atomic=("default", "other"),
            )
        self.assertEqual(rows("default"), 0)
        self.assertEqual(rows("other"), 0)

    def test_all_wraps_every_database(self):
        with self.assertRaises(ValueError):
            self.chain(
                "write", "--using", "other", "c", "end", "valueerror", atomic="__all__"
            )
        self.assertEqual(rows("default"), 0)
        self.assertEqual(rows("other"), 0)

    def test_true_honors_the_database_option(self):
        with self.assertRaises(ValueError):
            self.chain(
                "write", "--using", "other", "c", "end", "valueerror", database="other"
            )
        self.assertEqual(rows("default"), 2)
        self.assertEqual(rows("other"), 0)

        with self.assertRaises(ValueError):
            call_command(
                "atomic_chain",
                "--database",
                "other",
                "write",
                "a",
                "write",
                "--using",
                "other",
                "c",
                "end",
                "valueerror",
            )
        self.assertEqual(rows("default"), 3)
        self.assertEqual(rows("other"), 0)


class AtomicCommandLineTests(TransactionTestCase):
    """
    From the command line the exit policy turns Exit/Abort/interrupts into a
    process status. The transaction follows the same rule: commit on success,
    roll back on anything else. Each subprocess writes to the shared test database.
    """

    databases = {"default", "other"}

    def setUp(self):
        # subprocesses run by earlier tests may have committed rows
        for alias in self.databases:
            ShellCompleteTester.objects.using(alias).all().delete()
        # point the subprocess at the test databases - on sqlite the test
        # database is the configured file, on postgres it is a separate database
        self.env = {
            **os.environ,
            "POSTGRES_DB": str(connections["default"].settings_dict["NAME"]),
            "POSTGRES_OTHER_DB": str(connections["other"].settings_dict["NAME"]),
        }

    def test_transaction_follows_the_exit_status(self):
        table = [
            ("return", 0, 2),
            ("exit0", 0, 2),
            ("sysexit0", 0, 2),
            ("exit3", 3, 0),
            ("abort", 1, 0),
            ("sysexit4", 4, 0),
            ("interrupt", 130, 0),
            ("cmderror", 5, 0),
            ("valueerror", 1, 0),
        ]
        for how, status, expected_rows in table:
            with self.subTest(how=how):
                ShellCompleteTester.objects.all().delete()
                _, stderr, retcode = run_command(
                    "atomic_chain",
                    "--no-color",
                    "write",
                    "a",
                    "write",
                    "b",
                    "end",
                    how,
                    env=self.env,
                )
                self.assertEqual(retcode, status, stderr)
                self.assertEqual(rows(), expected_rows)

    def test_database_option_selects_the_transaction(self):
        _, stderr, retcode = run_command(
            "atomic_chain",
            "--no-color",
            "--database",
            "other",
            "write",
            "a",
            "write",
            "--using",
            "other",
            "c",
            "end",
            "valueerror",
            env=self.env,
        )
        self.assertEqual(retcode, 1, stderr)
        self.assertEqual(rows("default"), 1)
        self.assertEqual(rows("other"), 0)
