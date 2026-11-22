import warnings

import pytest
import typer
from django.core.management import CommandError, call_command
from django.test import TestCase

from django_typer.parsers.model import ModelObjectParser
from tests.apps.test_app.models import ShellCompleteTester
from tests.utils import run_command


class TestParamTypeDeprecation(TestCase):
    def test_subclass_warns_once(self):
        from django_typer.parsers import ParamType

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")

            class Mine(ParamType):
                pass

            # only naming ParamType as a base warns, at the class definition
            class Derived(Mine):
                pass

            Mine()
            Derived()

        self.assertEqual(len(caught), 1)
        self.assertIs(caught[0].category, DeprecationWarning)
        self.assertIn("ParamType is deprecated", str(caught[0].message))
        self.assertEqual(caught[0].filename, __file__)

    def test_import_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            from django_typer.parsers import ParamType  # noqa: F401

    def test_param_type_api(self):
        from django_typer.parsers import ParamType

        with pytest.warns(DeprecationWarning, match="ParamType is deprecated"):
            param_type = ParamType()
        self.assertIsNone(param_type(None))
        self.assertEqual(param_type("value"), "value")
        with self.assertRaises(typer.BadParameter):
            param_type.fail("bad")
        # the rest of click's interface is present with its defaults
        self.assertEqual(param_type.to_info_dict(), {"param_type": "", "name": "text"})
        self.assertIsNone(param_type.get_metavar(None, None))
        self.assertIsNone(param_type.get_missing_message(None, None))
        self.assertEqual(param_type.split_envvar_value("a b"), ["a", "b"])
        self.assertEqual(param_type.shell_complete(None, None, ""), [])
        self.assertEqual((param_type.is_composite, param_type.arity), (False, 1))
        self.assertIsNone(param_type.envvar_list_splitter)

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

    def test_label_rules_in_process(self):
        from io import StringIO

        from django_typer.management import DTArgument, DTOption, get_command

        for name, expected in (
            ("parser_labels", [r"--func\s+<named>", r"--pair\s+<str,str>"]),
            ("deprecated_param_type", [r"value\s+<upper>"]),
            ("completion", [r"<list\[APP_LABEL\]>", r"--option\s+<APP_LABEL>"]),
        ):
            stdout = StringIO()
            cmd = get_command(name, no_color=True, stdout=stdout)
            cmd.print_help("./manage.py", name)
            for pattern in expected:
                self.assertRegex(stdout.getvalue(), pattern)

        params = get_command("parser_labels").command_tree.click_command.params
        self.assertTrue(params)
        for param in params:
            self.assertIsInstance(param, (DTOption, DTArgument))

    def test_only_typer_params_are_switched(self):
        from django_typer.management import _use_dt_params

        class NotATyperParam:
            pass

        other = NotATyperParam()
        _use_dt_params([other])
        self.assertIs(type(other), NotATyperParam)
