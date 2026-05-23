from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from django_typer.management import get_command
from tests.utils import run_command


class ModifyOnInitializeTests(TestCase):
    """
    Tests that you can build a command programmatically when it is instantiated.
    """

    def test_mod_on_init_run(self):
        self.assertEqual(
            run_command(
                "mod_on_init",
                "--settings",
                "tests.settings.mod_init",
                "routine2",
                "--package",
                "--deploy",
            )[0].strip(),
            "('routine2', ['deploy', 'package'])",
        )
        self.assertEqual(
            run_command(
                "mod_on_init",
                "--settings",
                "tests.settings.mod_init",
                "routine3",
            )[0].strip(),
            "('routine3', [])",
        )
        result = run_command(
            "mod_on_init",
            "--settings",
            "tests.settings.mod_init",
            "routine3",
            "--deploy",
        )[1].strip()
        self.assertTrue("No such option" in result and "--deploy" in result)

    @override_settings(
        ROUTINES={
            "routine1": ["initial", "destroy"],
            "routine2": ["deploy", "package", "upload"],
            "routine3": [],
        }
    )
    def test_mod_on_init_call(self):
        self.assertEqual(
            call_command("mod_on_init", "routine2", package=True, deploy=True),
            ("routine2", ["deploy", "package"]),
        )
        self.assertEqual(call_command("mod_on_init", "routine3"), ("routine3", []))
        with self.assertRaises(CommandError):
            call_command("mod_on_init", "routine3", "--deploy")

    @override_settings(
        ROUTINES={
            "routine1": ["initial", "destroy"],
            "routine2": ["deploy", "package", "upload"],
            "routine3": [],
        }
    )
    def test_mod_on_init_direct(self):
        mod_on_init = get_command("mod_on_init")
        # make sure __init__ is run more than once
        mod_on_init = get_command("mod_on_init")
        mod_on_init = get_command("mod_on_init")
        self.assertEqual(len(mod_on_init.typer_app.registered_commands), 3)
        self.assertEqual(
            mod_on_init.routine2(package=True, upload=True),
            ("routine2", ["package", "upload"]),
        )
