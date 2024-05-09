import json

from django.core.management import call_command
from django.test import TestCase

from django_typer import get_command
from django_typer.tests.utils import run_command


class TestOverloaded(TestCase):
    """
    Tests that overloaded group/command names work as expected.
    """

    def test_overloaded_direct(self):
        overloaded = get_command("overloaded")
        overloaded.test(1, flag=True)
        self.assertEqual(
            json.loads(overloaded.samename(5, flag=False)),
            {
                "samename": {"precision": 5, "flag": False},
                "test": {"precision": 1, "flag": True},
            },
        )

        overloaded.test(5, flag=False)
        self.assertEqual(
            json.loads(overloaded.samename(1, flag=True)),
            {
                "samename": {"precision": 1, "flag": True},
                "test": {"precision": 5, "flag": False},
            },
        )

        overloaded.test(1, flag=True)
        self.assertEqual(
            json.loads(overloaded.diffname(5, flag2=False)),
            {
                "diffname": {"precision2": 5, "flag2": False},
                "test": {"precision": 1, "flag": True},
            },
        )

        overloaded.test(5, flag=False)
        self.assertEqual(
            json.loads(overloaded.diffname(1, flag2=True)),
            {
                "diffname": {"precision2": 1, "flag2": True},
                "test": {"precision": 5, "flag": False},
            },
        )

    def test_overloaded_cli(self):
        result = run_command(
            "overloaded", "test", "--flag", "1", "samename", "5", "--no-flag"
        )[0]
        self.assertEqual(
            result,
            {
                "samename": {"precision": 5, "flag": False},
                "test": {"precision": 1, "flag": True},
            },
        )

        result = run_command(
            "overloaded", "test", "--no-flag", "5", "samename", "1", "--flag"
        )[0]
        self.assertEqual(
            result,
            {
                "samename": {"precision": 1, "flag": True},
                "test": {"precision": 5, "flag": False},
            },
        )
        result = run_command(
            "overloaded", "test", "--flag", "1", "diffname", "5", "--no-flag"
        )[0]
        self.assertEqual(
            result,
            {
                "diffname": {"precision2": 5, "flag2": False},
                "test": {"precision": 1, "flag": True},
            },
        )

        result = run_command(
            "overloaded", "test", "--no-flag", "5", "diffname", "1", "--flag"
        )[0]
        self.assertEqual(
            result,
            {
                "diffname": {"precision2": 1, "flag2": True},
                "test": {"precision": 5, "flag": False},
            },
        )

    def test_overloaded_call_command(self):
        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded",
                    ["test", "--flag", "1", "samename", "5", "--no-flag"],
                )
            ),
            {
                "samename": {"precision": 5, "flag": False},
                "test": {"precision": 1, "flag": True},
            },
        )
        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded",
                    ["test", "--no-flag", "5", "samename", "1", "--flag"],
                )
            ),
            {
                "samename": {"precision": 1, "flag": True},
                "test": {"precision": 5, "flag": False},
            },
        )
        self.assertEqual(
            json.loads(
                call_command("overloaded", ["test", "5", "samename", "1"], flag=True)
            ),
            {
                "samename": {"precision": 1, "flag": True},
                "test": {"precision": 5, "flag": True},
            },
        )

        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded",
                    ["test", "--no-flag", "5", "diffname", "1", "--flag"],
                )
            ),
            {
                "diffname": {"precision2": 1, "flag2": True},
                "test": {"precision": 5, "flag": False},
            },
        )
        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded",
                    ["test", "--flag", "1", "diffname", "5", "--no-flag"],
                )
            ),
            {
                "diffname": {"precision2": 5, "flag2": False},
                "test": {"precision": 1, "flag": True},
            },
        )
        self.assertEqual(
            json.loads(
                call_command(
                    "overloaded", ["test", "5", "diffname", "1"], flag=True, flag2=False
                )
            ),
            {
                "diffname": {"precision2": 1, "flag2": False},
                "test": {"precision": 5, "flag": True},
            },
        )