from django.core.management import CommandError, call_command
from django.test import TestCase

from tests.utils import run_command


class UsageErrorTests(TestCase):
    def test_missing_parameter(self):
        result = run_command("missing")
        self.assertTrue("Test missing parameter." in result[0])
        self.assertTrue("arg1 must be given." in result[1])

        result = run_command("error")
        self.assertTrue("Test usage error behavior." in result[0])
        self.assertTrue("Missing parameter: arg1" in result[1])

        with self.assertRaises(CommandError):
            call_command("missing")

        with self.assertRaises(CommandError):
            call_command("error")

    def test_bad_param(self):
        result = run_command("error", "a")
        self.assertTrue("Test usage error behavior." in result[0])
        self.assertTrue("'a' is not a valid integer." in result[1])

        with self.assertRaises(CommandError):
            call_command("error", "a")

    def test_no_option(self):
        result = run_command("error", "--flg1")
        self.assertTrue("Test usage error behavior." in result[0])
        self.assertTrue("No such option" in result[1] and "--flg1" in result[1])

        with self.assertRaises(CommandError):
            call_command("error", "--flg1")

    def test_bad_option(self):
        result = run_command("error", "--opt1", "d")
        self.assertTrue("Test usage error behavior." in result[0])
        self.assertTrue("'d' is not a valid integer." in result[1])

        with self.assertRaises(CommandError):
            call_command("error", "--opt1", "d")
