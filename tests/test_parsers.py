import warnings

import pytest
import typer
from django.core.management import CommandError, call_command
from django.test import TestCase

from django_typer.parsers.model import ModelObjectParser
from tests.apps.test_app.models import ShellCompleteTester
from tests.utils import run_command


class TestParamTypeDeprecation(TestCase):
    def test_import_warns(self):
        import django_typer.parsers as parsers

        with pytest.warns(DeprecationWarning, match="ParamType is deprecated"):
            from django_typer.parsers import ParamType  # noqa: F401

        with pytest.warns(DeprecationWarning):
            parsers.ParamType

    def test_other_attributes_raise(self):
        import django_typer.parsers as parsers

        with self.assertRaises(AttributeError):
            parsers.DoesNotExist

    def test_param_type_api(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from django_typer.parsers import ParamType

        param_type = ParamType()
        self.assertIsNone(param_type(None))
        self.assertEqual(param_type("value"), "value")
        with self.assertRaises(typer.BadParameter):
            param_type.fail("bad")

    def test_param_type_subclass_parser(self):
        self.assertEqual(call_command("deprecated_param_type", "abc"), "ABC")
        stdout, stderr, retcode = run_command("deprecated_param_type", "bad")
        self.assertNotEqual(retcode, 0)
        self.assertIn("bad is not allowed.", stderr)


class TestModelObjectParserCallable(TestCase):
    def test_callable(self):
        obj = ShellCompleteTester.objects.create(char_field="hello")
        parser = ModelObjectParser(ShellCompleteTester, "char_field")
        self.assertIsNone(parser(None))
        self.assertEqual(parser("hello"), obj)
        self.assertEqual(parser(obj), obj)
        self.assertEqual(parser.convert("hello"), obj)
        with self.assertRaises(CommandError):
            parser("missing")


class TestParserTypeLabels(TestCase):
    """
    Parameters with a named parser are labeled with the parser's ``__name__`` in help.
    """

    def test_app_config_label(self):
        stdout, stderr, retcode = run_command("completion", "--no-color", "--help")
        self.assertEqual(retcode, 0, stderr)
        self.assertRegex(stdout, r"django_apps\.*\s+<list\[APP_LABEL\]>")
        self.assertRegex(stdout, r"--option\s+<APP_LABEL>")

    def test_param_type_name_label(self):
        stdout, stderr, retcode = run_command(
            "deprecated_param_type", "--no-color", "--help"
        )
        self.assertEqual(retcode, 0, stderr)
        self.assertRegex(stdout, r"value\s+<upper>")

    def test_label_rules(self):
        stdout, stderr, retcode = run_command("parser_labels", "--no-color", "--help")
        self.assertEqual(retcode, 0, stderr)
        # named function parsers and instances with a name attribute label the type
        self.assertRegex(stdout, r"--func\s+<named>")
        self.assertRegex(stdout, r"--funcs\s+<list\[named\]>")
        self.assertRegex(stdout, r"--instance\s+<named_instance>")
        # parsers without a usable name keep the annotation label
        self.assertRegex(stdout, r"--unnamed\s+<str>")
        self.assertRegex(stdout, r"--anon\s+<str>")
        self.assertNotIn("lambda", stdout)
        # tuples keep their arity and choices keep their values
        self.assertRegex(stdout, r"--pair\s+<str,str>")
        self.assertRegex(stdout, r"--color\s+<red\|blue>")
