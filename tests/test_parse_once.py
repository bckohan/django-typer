import json
import tempfile
from pathlib import Path
from threading import Thread

from django.core.management import call_command
from django.test import TestCase

from django_typer.management import get_command
from tests.apps.test_app.models import ShellCompleteTester
from tests.utils import run_command


class TestParseOnce(TestCase):
    """
    Django's BaseCommand parses in one step and executes in another. The context
    built while parsing must be the one executed, so conversion side effects
    happen once and resources it opened outlive the parse.
    """

    def test_file_argument_stays_open(self):
        # https://github.com/django-commons/django-typer/issues/209
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.bin"
            path.write_bytes(b"hello from a file")

            self.assertEqual(
                call_command("parse_once_file", str(path)), "hello from a file"
            )

            stdout, stderr, retcode = run_command("parse_once_file", str(path))
            self.assertEqual(retcode, 0, stderr)
            self.assertIn("hello from a file", stdout)

        stdout, stderr, retcode = run_command(
            "parse_once_file", "-", input=b"hello from stdin"
        )
        self.assertEqual(retcode, 0, stderr)
        self.assertIn("hello from stdin", stdout)

    def test_model_argument_converted_once(self):
        # https://github.com/django-commons/django-typer/issues/210
        ShellCompleteTester.objects.create(char_field="jack")
        with self.assertNumQueries(1):
            result = call_command("parse_once_model", "jack")
        self.assertEqual(result, "jack")

    def test_parser_called_once(self):
        from tests.apps.test_app.management.commands import parse_once_count

        before = parse_once_count.conversions
        self.assertEqual(call_command("parse_once_count", "abc"), f"ABC {before + 1}")
        self.assertEqual(parse_once_count.conversions, before + 1)

    def test_shared_command_instance_across_threads(self):
        # the parsed context is held per thread, so a command instance can be
        # driven from several threads at once without them seeing each other's args
        cmd = get_command("basic")
        results: dict[str, str] = {}

        def run(tag: str):
            results[tag] = call_command(cmd, tag, f"{tag}-second", arg4=len(tag))

        threads = [Thread(target=run, args=(f"thread{i}",)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(results), 8)
        for tag, result in results.items():
            parsed = json.loads(result)
            self.assertEqual(parsed["arg1"], tag)
            self.assertEqual(parsed["arg2"], f"{tag}-second")
            self.assertEqual(parsed["arg4"], len(tag))
