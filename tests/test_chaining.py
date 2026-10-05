import contextlib
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from django_typer.management import DTGroup, get_command
from tests.utils import run_command


class TestChaining(TestCase):
    def test_command_chaining(self):
        result = run_command(
            "chain", "command1", "--option=one", "command2", "--option=two"
        )[0]
        self.assertEqual(
            result.splitlines(), "command1\ncommand2\n['one', 'two']\n".splitlines()
        )

        result = run_command(
            "chain", "command2", "--option=two", "command1", "--option=one"
        )[0]
        self.assertEqual(
            result.splitlines(), "command2\ncommand1\n['two', 'one']\n".splitlines()
        )

        stdout = StringIO()
        with contextlib.redirect_stdout(stdout):
            result = call_command(
                "chain", "command2", "--option=two", "command1", "--option=one"
            )
        self.assertEqual(
            stdout.getvalue().splitlines(),
            "command2\ncommand1\n['two', 'one']\n".splitlines(),
        )
        self.assertEqual(result, ["two", "one"])

        chain = get_command("chain")
        self.assertEqual(chain.command1(option="one"), "one")
        self.assertEqual(chain.command2(option="two"), "two")

    def test_chain_with_initializer(self):
        # an initializer must not switch chain mode off and chained subcommands
        # may take positional arguments
        self.assertEqual(
            call_command("chain_init", "echo", "a", "upper", "b", "echo", "c"),
            ["a", "B", "c"],
        )
        self.assertEqual(
            call_command("chain_init", "--prefix", "x-", "echo", "a", "upper", "b"),
            ["x-a", "x-B"],
        )
        self.assertEqual(
            call_command("chain_init", "echo", "a", "upper", "b", prefix="y-"),
            ["y-a", "y-B"],
        )
        stdout, stderr, retcode = run_command(
            "chain_init", "--no-color", "--prefix", "z-", "echo", "a", "upper", "b"
        )
        self.assertEqual(retcode, 0, stderr)

    def test_chain_missing_command(self):
        # a chained group without invoke_without_command requires a subcommand
        stdout, stderr, retcode = run_command("chain")
        self.assertNotEqual(retcode, 0)
        self.assertIn("Missing command.", stderr)
        with self.assertRaisesMessage(CommandError, "Missing command."):
            call_command("chain")

    def test_chain_no_args_is_help(self):
        # any argument at all (even --no-color) defeats no_args_is_help
        stdout, stderr, retcode = run_command("chain_no_args")
        self.assertNotEqual(retcode, 0)
        self.assertIn("Usage:", stdout + stderr)
        self.assertIn("command1", stdout + stderr)
        self.assertIn("command2", stdout + stderr)
        # rich help is printed straight to stdout, plain help rides on the error
        stdout = StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(CommandError) as cm:
            call_command("chain_no_args")
        self.assertIn("Usage:", stdout.getvalue() + str(cm.exception))

        self.assertEqual(
            run_command("chain_no_args", "command2", "command1")[0].strip(),
            "['command2', 'command1']",
        )

    def test_chain_rejects_optional_arguments(self):
        from typer.core import TyperArgument

        ChainGroup = type("ChainGroup", (DTGroup,), {"chain": True})
        with self.assertRaises(RuntimeError):
            ChainGroup(
                name="grp",
                callback=None,
                params=[TyperArgument(param_decls=["arg"], required=False, nargs=1)],
            )
        # required arguments are fine
        ChainGroup(
            name="grp",
            callback=None,
            params=[TyperArgument(param_decls=["arg"], required=True, nargs=1)],
        )
