import json
import os
import re
from decimal import Decimal
from io import StringIO
from pathlib import Path
from datetime import date, datetime, time, timedelta
import random
import typing as t

import django
from django.apps import apps
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone as tz_utils

from django_typer.management.commands.shellcompletion import (
    DETECTED_SHELL,
    Command as ShellCompletion,
)
from django_typer.management import get_command
from django_typer.utils import with_typehint
from django.db.models import Model
from django.db.models import F
from django.db.models.functions import Cast
from django.db.models import CharField
from tests.apps.test_app.models import ShellCompleteTester, ChoicesShellCompleteTester
from tests.utils import run_command
import platform
from django.utils.timezone import get_default_timezone, get_default_timezone_name
import pytest
from django.db import connection

SHELL = {
    "zsh": "zsh",
    "bash": "bash",
    "pwsh": "pwsh",
    "powershell": "powershell",
    "fish": "fish",
}.get(DETECTED_SHELL, "bash")


def get_values_and_helps(completion) -> t.List[t.Tuple[str, str]]:
    if SHELL == "zsh":
        return list(zip(completion.split("\n")[1::3], completion.split("\n")[2::3]))
    elif SHELL == "bash":
        return [(line.split(",")[1], "") for line in completion.split("\n") if line]
    elif SHELL in ["pwsh", "powershell"]:
        return [
            (line.split(":::")[1], line.split(":::")[2])
            for line in completion.splitlines()
            if line
        ]
    elif SHELL == "fish":
        values = []
        for line in completion.splitlines():
            if not line:
                continue
            parts = line.split(",")[1].split("\t", 1)
            values.append((parts[0], parts[1] if len(parts) > 1 else ""))
        return values
    raise NotImplementedError(f"get_values for shell {SHELL} not implemented")


def get_values(completion) -> t.List[str]:
    if SHELL == "zsh":
        return completion.split("\n")[1::3]
    elif SHELL == "bash":
        return [line.split(",")[1] for line in completion.split("\n") if line]
    elif SHELL in ["pwsh", "powershell"]:
        return [line.split(":::")[1] for line in completion.splitlines() if line]
    elif SHELL == "fish":
        return [
            line.split(",")[1].split("\t")[0]
            for line in completion.splitlines()
            if line
        ]
    raise NotImplementedError(f"get_values for shell {SHELL} not implemented")


class ParserCompleterMixin(with_typehint(TestCase)):
    field_values = {}
    MODEL_CLASS: t.Type[Model]

    def setUp(self):
        super().setUp()
        for field, values in self.field_values.items():
            for value in values:
                self.MODEL_CLASS.objects.create(**{field: value})

    def tearDown(self) -> None:
        self.MODEL_CLASS.objects.all().delete()
        return super().tearDown()

    @property
    def shellcompletion(self) -> ShellCompletion:
        shellcompletion = get_command("shellcompletion", ShellCompletion)
        shellcompletion.init(shell=SHELL)
        return shellcompletion


class TestShellCompletersAndParsers(ParserCompleterMixin, TestCase):
    MODEL_CLASS = ShellCompleteTester

    field_values = {
        "char_field": ["jon", "john", "jack", "jason"],
        "text_field": [
            "sockeye",
            "chinook",
            "steelhead",
            "coho",
            "atlantic",
            "pink",
            "chum",
        ],
        "float_field": [1.1, 1.12, 2.2, 2.3, 2.4, 3.0, 4.0],
        "decimal_field": [
            Decimal("1.5"),
            Decimal("1.50"),
            Decimal("1.51"),
            Decimal("1.52"),
            Decimal("1.2"),
            Decimal("1.6"),
        ],
        "uuid_field": [
            "12345678-1234-5678-1234-567812345678",
            "12345678-1234-5678-1234-567812345679",
            "12345678-5678-5678-1234-567812345670",
            "12345678-5678-5678-1234-567812345671",
            "12345678-5678-5678-1234-A67812345671",
            "12345678-5678-5678-f234-A67812345671",
        ],
        "ip_field": [
            "192.168.1.1",
            "192.0.2.30",
            "10.0.0.1",
            "2a02:42fe::4",
            "2a02:42ae::4",
            #'2001:0::0:01', this gets normalized to the one below
            "2001::1",
            "::ffff:10.10.10.10",
        ],
        "file_field": [
            "path1/file1.txt",
            "path1/file2.txt",
            "path2/file3.txt",
            "file3.txt",
        ],
        "file_path_field": [
            "dir1/file1.txt",
            "dir1/file2.txt",
            "dir2/file3.txt",
            "file4.txt",
        ],
        "date_field": [
            date(1984, 8, 7),
            date(1989, 7, 27),
            date(2021, 1, 6),
            date(2021, 1, 7),
            date(2021, 1, 8),
            date(2021, 1, 31),
            date(2021, 2, 9),
            date(2021, 2, 10),
            date(2024, 2, 29),
            date(2024, 9, 20),
            date(2025, 2, 28),
        ],
        "time_field": [
            time(0, 0, 0),
            time(2, 0, 0),
            time(20, 0, 0),
            time(22, 0, 0),
            time(22, 30, 45, 990000),
            time(22, 30, 46, 990000),
            time(22, 30, 46, 990100),
            time(22, 30, 46, 999900),
            time(23, 59, 59, 999999),
        ],
        "duration_field": [
            # TODO - the negative durations are not being completed because typer/click
            # interprets the incomplete string as an option, not a value.
            # https://github.com/django-commons/django-typer/issues/161
            timedelta(days=5),
            timedelta(days=52),
            timedelta(days=541),
            timedelta(days=5298),
            timedelta(days=52, hours=1, minutes=4, seconds=5),
            timedelta(days=52, hours=1, minutes=4, seconds=52),
            timedelta(days=52, hours=1, minutes=45, seconds=3),
            timedelta(days=52, hours=1, minutes=45, seconds=32),
            timedelta(days=52, hours=12, minutes=1, seconds=5, microseconds=123456),
            timedelta(days=52, hours=12, minutes=1, seconds=5, microseconds=12),
            timedelta(days=52, hours=12, minutes=15, seconds=52, microseconds=987654),
            timedelta(days=52, hours=12, minutes=15, seconds=52, microseconds=9877),
            timedelta(days=52, hours=2),
            timedelta(days=52, hours=23),
            # days = 5, 52, 541
            # hours = 0, 1, 2, 12, 23
            # minutes = 0, 1, 4, 15, 45
            # seconds = 0, 3, 5, 32, 52
            # timedelta with random values generated by random number gen
            timedelta(),
            timedelta(seconds=1),
            timedelta(minutes=1),
            timedelta(hours=1),
            timedelta(days=1),
            # we add some random values. neat little trick to explore more edge
            # cases each time the tests are run! - make sure hard coded tests
            # 100% coverage
            *[
                timedelta(
                    days=random.randint(0, 6000),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59),
                    microseconds=random.randint(0, 999999),
                )
                for _ in range(20)
            ],
        ],
    }

    def test_model_object_parser_metavar(self):
        stdout, stderr, retcode = run_command(
            "model_fields", "--no-color", "test", "--help"
        )
        if platform.system() == "Windows":
            stdout = stdout.replace("\r\n", "")
        if retcode:
            self.fail(stderr)
        try:
            self.assertTrue(re.search(r"--char\s+TXT", stdout))
            self.assertTrue(re.search(r"--ichar\s+TXT", stdout))
            self.assertTrue(re.search(r"--text\s+TXT", stdout))
            self.assertTrue(re.search(r"--itext\s+TXT", stdout))
            self.assertTrue(re.search(r"--uuid\s+UUID", stdout))
            self.assertTrue(re.search(r"--id\s+INT", stdout))
            self.assertTrue(re.search(r"--id-limit\s+INT", stdout))
            self.assertTrue(re.search(r"--float\s+FLOAT", stdout))
            self.assertTrue(re.search(r"--decimal\s+FLOAT", stdout))
            self.assertTrue(re.search(r"--ip\s+\[IPV4\|IPV6\]", stdout))
            self.assertTrue(re.search(r"--email\s+EMAIL", stdout))
            self.assertTrue(re.search(r"--url\s+URL", stdout))
            self.assertTrue(re.search(r"--file\s+PATH", stdout))
            self.assertTrue(re.search(r"--file-path\s+PATH", stdout))
            self.assertTrue(re.search(r"--date\s+YYYY-MM-DD", stdout))
            self.assertTrue(re.search(r"--datetime\s+ISO 8601", stdout))
            self.assertTrue(re.search(r"--time\s+HH:MM:SS.SSS", stdout))
            self.assertTrue(re.search(r"--duration\s+ISO 8601", stdout))
        except AssertionError:
            self.fail(stdout)

    def test_model_object_parser_metavar_override(self):
        stdout, stderr, retcode = run_command("poll_as_option", "--help", "--no-color")
        # TODO - why are extra newlines inserted here on windows??
        if platform.system() == "Windows":
            stdout = stdout.replace("\r\n", "")
        if retcode:
            self.fail(stderr)
        try:
            self.assertTrue(re.search(r"--polls\s+POLL", stdout))
        except AssertionError:
            self.fail(stdout)

    def test_model_object_parser_idempotency(self):
        from django_typer.parsers.model import ModelObjectParser
        from tests.apps.examples.polls.models import Question

        q1 = Question.objects.create(
            question_text="Is Putin a war criminal?",
            pub_date=tz_utils.now(),
        )

        parser = ModelObjectParser(Question)
        self.assertEqual(parser.convert(q1, None, None), q1)

    def test_app_label_parser_idempotency(self):
        from django_typer.parsers.apps import app_config

        poll_app = apps.get_app_config("tests_apps_examples_polls")
        self.assertEqual(app_config(poll_app), poll_app)

    def test_shellcompletion_stdout(self):
        result = self.shellcompletion.complete("completion ")
        self.assertTrue("test_app" in result)
        self.assertTrue("tests_apps_util" in result)
        self.assertTrue("django_typer" in result)

        result2 = StringIO()
        call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "completion ",
            stdout=result2,
        )
        stdout_result = result2.getvalue().strip()
        self.assertTrue("test_app" in stdout_result)
        self.assertTrue("tests_apps_util" in stdout_result)
        self.assertTrue("django_typer" in stdout_result)

    def test_app_label_parser_completers(self):
        from django.apps import apps

        result = call_command(
            "shellcompletion", "--shell", SHELL, "complete", "completion "
        )
        self.assertTrue("test_app" in result)
        self.assertTrue("tests_apps_util" in result)
        self.assertTrue("django_typer" in result)
        self.assertTrue("tests_apps_examples_polls" in result)
        self.assertTrue("admin" in result)
        self.assertTrue("auth" in result)
        self.assertTrue("contenttypes" in result)
        self.assertTrue("sessions" in result)
        self.assertTrue("messages" in result)
        self.assertTrue("staticfiles" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "completion --app-opt ",
        )
        self.assertTrue("test_app" in result)
        self.assertTrue("tests_apps_util" in result)

        result = call_command(
            "shellcompletion", "--shell", SHELL, "complete", "completion tests."
        )
        self.assertTrue("tests.apps.examples.polls" in result)
        self.assertTrue("tests.apps.test_app" in result)

        result = call_command(
            "shellcompletion", "--shell", SHELL, "complete", "completion tests"
        )
        self.assertTrue("tests_apps_examples_polls" in result)
        self.assertTrue("tests_apps_util" in result)

        self.assertEqual(
            json.loads(call_command("completion", "tests_apps_examples_polls")),
            ["tests_apps_examples_polls"],
        )
        self.assertEqual(
            json.loads(call_command("completion", "tests.apps.examples.polls")),
            ["tests_apps_examples_polls"],
        )

        with self.assertRaises(CommandError):
            call_command("completion", "tests.polls")

        poll_app = apps.get_app_config("tests_apps_examples_polls")
        test_app = apps.get_app_config("test_app")
        cmd = get_command("completion")
        self.assertEqual(
            json.loads(cmd([poll_app])),
            ["tests_apps_examples_polls"],
        )

        self.assertEqual(
            json.loads(cmd(django_apps=[poll_app])),
            ["tests_apps_examples_polls"],
        )

        self.assertEqual(
            json.loads(cmd(django_apps=[poll_app], option=test_app)),
            {
                "django_apps": ["tests_apps_examples_polls"],
                "option": "test_app",
            },
        )

        self.assertEqual(
            json.loads(
                call_command(
                    "completion",
                    "tests_apps_examples_polls",
                    option=test_app,
                )
            ),
            {
                "django_apps": ["tests_apps_examples_polls"],
                "option": "test_app",
            },
        )

        self.assertEqual(
            json.loads(
                call_command(
                    "completion",
                    "tests_apps_examples_polls",
                    "--option=test_app",
                )
            ),
            {
                "django_apps": ["tests_apps_examples_polls"],
                "option": "test_app",
            },
        )

    def test_char_field(self):
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --char ja",
        )
        self.assertTrue("jack" in result)
        self.assertTrue("jason" in result)
        self.assertFalse("jon" in result)
        self.assertFalse("john" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --ichar Ja",
        )
        self.assertTrue("Jack" in result)
        self.assertTrue("Jason" in result)
        self.assertFalse("Jon" in result)
        self.assertFalse("John" in result)

        self.assertEqual(
            json.loads(call_command("model_fields", "test", "--char", "jack")),
            {
                "char": {
                    str(ShellCompleteTester.objects.get(char_field="jack").pk): "jack"
                }
            },
        )

        self.assertEqual(
            json.loads(call_command("model_fields", "test", "--ichar", "john")),
            {
                "ichar": {
                    str(ShellCompleteTester.objects.get(char_field="john").pk): "john"
                }
            },
        )

        with self.assertRaises(CommandError):
            call_command("model_fields", "test", "--char", "jane")

        with self.assertRaises(RuntimeError):
            call_command("model_fields", "test", "--ichar", "jane")

    def test_file_field(self):
        completions = get_values(
            self.shellcompletion.complete("model_fields test --file ")
        )
        self.assertEqual(
            set(completions),
            {"path1/file1.txt", "path1/file2.txt", "path2/file3.txt", "file3.txt"},
        )

        completions = get_values(
            self.shellcompletion.complete("model_fields test --file p")
        )
        self.assertEqual(
            set(completions), {"path1/file1.txt", "path1/file2.txt", "path2/file3.txt"}
        )

        completions = get_values(
            self.shellcompletion.complete("model_fields test --file path1/f")
        )
        self.assertEqual(set(completions), {"path1/file1.txt", "path1/file2.txt"})

        completions = get_values(
            self.shellcompletion.complete("model_fields test --file f")
        )
        self.assertEqual(set(completions), {"file3.txt"})

        self.assertEqual(
            json.loads(call_command("model_fields", "test", "--file", "file3.txt")),
            {
                "file": {
                    str(
                        ShellCompleteTester.objects.get(file_field="file3.txt").pk
                    ): "file3.txt"
                }
            },
        )

    def test_file_path_field(self):
        completions = get_values(
            self.shellcompletion.complete("model_fields test --file-path ")
        )
        self.assertEqual(
            set(completions),
            {"dir1/file1.txt", "dir1/file2.txt", "dir2/file3.txt", "file4.txt"},
        )

        completions = get_values(
            self.shellcompletion.complete("model_fields test --file-path d")
        )
        self.assertEqual(
            set(completions), {"dir1/file1.txt", "dir1/file2.txt", "dir2/file3.txt"}
        )

        completions = get_values(
            self.shellcompletion.complete("model_fields test --file-path dir1/f")
        )
        self.assertEqual(set(completions), {"dir1/file1.txt", "dir1/file2.txt"})

        completions = get_values(
            self.shellcompletion.complete("model_fields test --file-path dir2")
        )
        self.assertEqual(set(completions), {"dir2/file3.txt"})

        self.assertEqual(
            json.loads(
                call_command("model_fields", "test", "--file-path", "dir2/file3.txt")
            ),
            {
                "file_path": {
                    str(
                        ShellCompleteTester.objects.get(
                            file_path_field="dir2/file3.txt"
                        ).pk
                    ): "dir2/file3.txt"
                }
            },
        )

    def test_date_field(self):
        def date_vals(values):
            return list(reversed(get_values(values)))

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date ")),
            [
                "1984-08-07",
                "1989-07-27",
                "2021-01-06",
                "2021-01-07",
                "2021-01-08",
                "2021-01-31",
                "2021-02-09",
                "2021-02-10",
                "2024-02-29",
                "2024-09-20",
                "2025-02-28",
            ],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 1")),
            ["1984-08-07", "1989-07-27"],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 19")),
            ["1984-08-07", "1989-07-27"],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 198")),
            ["1984-08-07", "1989-07-27"],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 1984-")),
            ["1984-08-07"],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 2-")),
            [],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 20")),
            [
                "2021-01-06",
                "2021-01-07",
                "2021-01-08",
                "2021-01-31",
                "2021-02-09",
                "2021-02-10",
                "2024-02-29",
                "2024-09-20",
                "2025-02-28",
            ],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 2021")),
            [
                "2021-01-06",
                "2021-01-07",
                "2021-01-08",
                "2021-01-31",
                "2021-02-09",
                "2021-02-10",
            ],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 2021-0")),
            [
                "2021-01-06",
                "2021-01-07",
                "2021-01-08",
                "2021-01-31",
                "2021-02-09",
                "2021-02-10",
            ],
        )

        self.assertEqual(
            date_vals(
                self.shellcompletion.complete("model_fields test --date 2021-01-")
            ),
            [
                "2021-01-06",
                "2021-01-07",
                "2021-01-08",
                "2021-01-31",
            ],
        )

        self.assertEqual(
            date_vals(
                self.shellcompletion.complete("model_fields test --date 2021-01-3")
            ),
            [
                "2021-01-31",
            ],
        )

        self.assertEqual(
            date_vals(
                self.shellcompletion.complete("model_fields test --date 2021-01-0")
            ),
            ["2021-01-06", "2021-01-07", "2021-01-08"],
        )

        self.assertEqual(
            date_vals(
                self.shellcompletion.complete("model_fields test --date 2021-01-06")
            ),
            ["2021-01-06"],
        )

        self.assertEqual(
            date_vals(
                self.shellcompletion.complete("model_fields test --date 2021-01-09")
            ),
            [],
        )

        self.assertEqual(
            date_vals(self.shellcompletion.complete("model_fields test --date 2024")),
            ["2024-02-29", "2024-09-20"],
        )

        self.assertEqual(
            date_vals(
                self.shellcompletion.complete("model_fields test --date 2024-02-2")
            ),
            ["2024-02-29"],
        )

        self.assertEqual(
            date_vals(
                self.shellcompletion.complete("model_fields test --date 2025-02-")
            ),
            ["2025-02-28"],
        )

        self.assertEqual(
            json.loads(call_command("model_fields", "test", "--date", "2024-02-29")),
            {
                "date": {
                    str(
                        ShellCompleteTester.objects.get(date_field=date(2024, 2, 29)).pk
                    ): "2024-02-29"
                }
            },
        )

    def test_time_field(self):
        def time_vals(completions):
            return list(reversed(get_values(completions)))

        self.assertEqual(
            time_vals(self.shellcompletion.complete("model_fields test --time ")),
            [
                "00:00:00",
                "02:00:00",
                "20:00:00",
                "22:00:00",
                "22:30:45.990000",
                "22:30:46.990000",
                "22:30:46.990100",
                "22:30:46.999900",
                "23:59:59.999999",
            ],
        )

        self.assertEqual(
            time_vals(self.shellcompletion.complete("model_fields test --time 0")),
            [
                "00:00:00",
                "02:00:00",
            ],
        )

        self.assertEqual(
            time_vals(self.shellcompletion.complete("model_fields test --time 00:")),
            ["00:00:00"],
        )

        self.assertEqual(
            time_vals(self.shellcompletion.complete("model_fields test --time 02:00")),
            ["02:00:00"],
        )

        self.assertEqual(
            time_vals(self.shellcompletion.complete("model_fields test --time 2")),
            [
                "20:00:00",
                "22:00:00",
                "22:30:45.990000",
                "22:30:46.990000",
                "22:30:46.990100",
                "22:30:46.999900",
                "23:59:59.999999",
            ],
        )

        self.assertEqual(
            time_vals(self.shellcompletion.complete("model_fields test --time 22")),
            [
                "22:00:00",
                "22:30:45.990000",
                "22:30:46.990000",
                "22:30:46.990100",
                "22:30:46.999900",
            ],
        )

        self.assertEqual(
            time_vals(self.shellcompletion.complete("model_fields test --time 22:3")),
            [
                "22:30:45.990000",
                "22:30:46.990000",
                "22:30:46.990100",
                "22:30:46.999900",
            ],
        )

        self.assertEqual(
            time_vals(
                self.shellcompletion.complete("model_fields test --time 22:30:4")
            ),
            [
                "22:30:45.990000",
                "22:30:46.990000",
                "22:30:46.990100",
                "22:30:46.999900",
            ],
        )
        self.assertEqual(
            time_vals(
                self.shellcompletion.complete("model_fields test --time 22:30:46")
            ),
            ["22:30:46.990000", "22:30:46.990100", "22:30:46.999900"],
        )
        self.assertEqual(
            time_vals(
                self.shellcompletion.complete("model_fields test --time 22:30:46.")
            ),
            ["22:30:46.990000", "22:30:46.990100", "22:30:46.999900"],
        )
        self.assertEqual(
            time_vals(
                self.shellcompletion.complete("model_fields test --time 22:30:46.9")
            ),
            ["22:30:46.990000", "22:30:46.990100", "22:30:46.999900"],
        )

        self.assertEqual(
            time_vals(
                self.shellcompletion.complete("model_fields test --time 22:30:46.99")
            ),
            ["22:30:46.990000", "22:30:46.990100", "22:30:46.999900"],
        )

        self.assertEqual(
            time_vals(
                self.shellcompletion.complete("model_fields test --time 22:30:46.990")
            ),
            [
                "22:30:46.990000",
                "22:30:46.990100",
            ],
        )

        self.assertEqual(
            time_vals(
                self.shellcompletion.complete("model_fields test --time 22:30:46.9901")
            ),
            [
                "22:30:46.990100",
            ],
        )
        self.assertEqual(
            time_vals(
                self.shellcompletion.complete("model_fields test --time 22:30:46.99012")
            ),
            [],
        )
        self.assertFalse(self.shellcompletion.complete("model_fields test --time 3"))

        for time in self.field_values["time_field"]:
            self.assertEqual(
                json.loads(call_command("model_fields", "test", "--time", str(time))),
                {
                    "time": {
                        str(ShellCompleteTester.objects.get(time_field=time).pk): str(
                            time
                        )
                    }
                },
            )

    def test_duration_field(self):
        from django_typer.utils import parse_iso_duration, duration_iso_string

        def completions(incomplete=""):
            return list(
                get_values(
                    self.shellcompletion.complete(
                        f"model_fields test --duration {incomplete}"
                    )
                )
            )

        durations = [
            (duration, duration_iso_string(duration))
            for duration in sorted(self.field_values["duration_field"])
        ]

        # try all permutations
        tried = set()
        for _, duration_str in durations:
            for i in range(len(duration_str)):
                incomplete = duration_str[:i]
                if incomplete in tried:
                    continue
                tried.add(incomplete)

                expected = {
                    dur[0] for dur in durations if dur[1].startswith(incomplete)
                }
                comps = {parse_iso_duration(dur)[0] for dur in completions(incomplete)}

                self.assertEqual(
                    comps,
                    expected,
                    msg=f"{incomplete=} has unexpected completions: {[duration_iso_string(d) for d in (comps - expected)]} and missing completions: {[duration_iso_string(d) for d in (expected - comps)]}",
                )

        print(f"Tried {len(tried)} permutations.")

        # try some non-matches
        # self.assertEqual(completions("P5D"), [])
        with self.assertRaises(CommandError):
            call_command(
                "model_fields",
                "test",
                "--duration",
                "P5DT1",
            )

        with self.assertRaises(CommandError):
            call_command(
                "model_fields",
                "test",
                "--duration",
                "P9999999D",
            )

        for duration in self.field_values["duration_field"]:
            self.assertEqual(
                json.loads(
                    call_command(
                        "model_fields",
                        "test",
                        "--duration",
                        duration_iso_string(duration),
                    )
                ),
                {
                    "duration": {
                        str(
                            ShellCompleteTester.objects.get(duration_field=duration).pk
                        ): str(duration)
                    }
                },
            )

    def test_ip_field(self):
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --ip ",
        )
        for ip in self.field_values["ip_field"]:
            self.assertTrue(ip in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --ip 2001:",
        )
        for ip in ["2001::1"]:
            self.assertTrue(ip in result)

        # IP normalization complexity is unhandled
        # result = StringIO()
        # with contextlib.redirect_stdout(result):
        #     call_command("shellcompletion", "--shell", SHELL, "complete", "model_fields test --ip 2001:0")
        # result = result.getvalue()
        # self.assertFalse(result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --ip 2a02:42",
        )
        for ip in ["2a02:42fe::4", "2a02:42ae::4"]:
            self.assertTrue(ip in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --ip 2a02:42f",
        )
        for ip in ["2a02:42fe::4"]:
            self.assertTrue(ip in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --ip 192.",
        )
        for ip in ["192.168.1.1", "192.0.2.30"]:
            self.assertTrue(ip in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --ip 192.1",
        )
        for ip in ["192.168.1.1"]:
            self.assertTrue(ip in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --ip :",
        )
        for ip in ["::ffff:10.10.10.10"]:
            self.assertTrue(ip in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields", "test", "--ip", "2001:0::0:01", "--ip", "192.0.2.30"
                )
            ),
            {
                "ip": [
                    {
                        str(
                            ShellCompleteTester.objects.get(ip_field="2001:0::0:01").pk
                        ): "2001::1"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(ip_field="192.0.2.30").pk
                        ): "192.0.2.30"
                    },
                ]
            },
        )

    def test_text_field(self):
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --text ",
        )
        self.assertTrue("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertTrue("steelhead" in result)
        self.assertTrue("coho" in result)
        self.assertTrue("atlantic" in result)
        self.assertTrue("pink" in result)
        self.assertTrue("chum" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --text ch",
        )
        self.assertFalse("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertFalse("steelhead" in result)
        self.assertFalse("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertFalse("pink" in result)
        self.assertTrue("chum" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --itext S",
        )
        self.assertTrue("Sockeye" in result)
        self.assertFalse("chinook" in result)
        self.assertTrue("Steelhead" in result)
        self.assertFalse("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertFalse("pink" in result)
        self.assertFalse("chum" in result)

        # distinct completions by default
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --text atlantic --text sockeye --text steelhead --text ",
        )
        self.assertFalse("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertFalse("steelhead" in result)
        self.assertTrue("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertTrue("pink" in result)
        self.assertTrue("chum" in result)

        # check distinct flag set to False
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --itext atlantic --itext sockeye --itext steelhead --itext ",
        )
        self.assertTrue("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertTrue("steelhead" in result)
        self.assertTrue("coho" in result)
        self.assertTrue("atlantic" in result)
        self.assertTrue("pink" in result)
        self.assertTrue("chum" in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--text",
                    "atlantic",
                    "--text",
                    "sockeye",
                    "--text",
                    "steelhead",
                )
            ),
            {
                "text": [
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="atlantic").pk
                        ): "atlantic"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="sockeye").pk
                        ): "sockeye"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="steelhead").pk
                        ): "steelhead"
                    },
                ]
            },
        )
        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--itext",
                    "ATlanTIC",
                    "--itext",
                    "SOCKeye",
                    "--itext",
                    "STEELHEAD",
                )
            ),
            {
                "itext": [
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="atlantic").pk
                        ): "atlantic"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="sockeye").pk
                        ): "sockeye"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="steelhead").pk
                        ): "steelhead"
                    },
                ]
            },
        )

    def test_text_field_filtered(self):
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --filtered ",
        )
        self.assertFalse("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertFalse("steelhead" in result)
        self.assertTrue("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertTrue("pink" in result)
        self.assertTrue("chum" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --filtered ch",
        )
        self.assertFalse("sockeye" in result)
        self.assertTrue("chinook" in result)
        self.assertFalse("steelhead" in result)
        self.assertFalse("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertFalse("pink" in result)
        self.assertTrue("chum" in result)

        # distinct completions by default
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --filtered coho --filtered chinook --filtered ",
        )
        self.assertFalse("sockeye" in result)
        self.assertFalse("chinook" in result)
        self.assertFalse("steelhead" in result)
        self.assertFalse("coho" in result)
        self.assertFalse("atlantic" in result)
        self.assertTrue("pink" in result)
        self.assertTrue("chum" in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--filtered",
                    "coho",
                    "--filtered",
                    "chinook",
                )
            ),
            {
                "filtered": [
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="coho").pk
                        ): "coho"
                    },
                    {
                        str(
                            ShellCompleteTester.objects.get(text_field="chinook").pk
                        ): "chinook"
                    },
                ]
            },
        )

    def test_uuid_field(self):
        from uuid import UUID

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid ",
        )
        self.assertTrue("12345678-1234-5678-1234-567812345678" in result)
        self.assertTrue("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345670" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345671" in result)
        self.assertTrue("12345678-5678-5678-1234-a67812345671" in result)
        self.assertTrue("12345678-5678-5678-f234-a67812345671" in result)
        self.assertFalse("None" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid 12345678",
        )
        self.assertTrue("12345678-1234-5678-1234-567812345678" in result)
        self.assertTrue("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345670" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345671" in result)
        self.assertTrue("12345678-5678-5678-1234-a67812345671" in result)
        self.assertTrue("12345678-5678-5678-f234-a67812345671" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid 12345678-",
        )
        self.assertTrue("12345678-1234-5678-1234-567812345678" in result)
        self.assertTrue("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345670" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345671" in result)
        self.assertTrue("12345678-5678-5678-1234-a67812345671" in result)
        self.assertTrue("12345678-5678-5678-f234-a67812345671" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid 12345678-5",
        )
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345670" in result)
        self.assertTrue("12345678-5678-5678-1234-567812345671" in result)
        self.assertTrue("12345678-5678-5678-1234-a67812345671" in result)
        self.assertTrue("12345678-5678-5678-f234-a67812345671" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid 123456785",
        )
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("123456785678-5678-1234-567812345670" in result)
        self.assertTrue("123456785678-5678-1234-567812345671" in result)
        self.assertTrue("123456785678-5678-1234-a67812345671" in result)
        self.assertTrue("123456785678-5678-f234-a67812345671" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid 123456&78-^56785678-",
        )
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertTrue("123456&78-^56785678-1234-567812345670" in result)
        self.assertTrue("123456&78-^56785678-1234-567812345671" in result)
        self.assertTrue("123456&78-^56785678-1234-a67812345671" in result)
        self.assertTrue("123456&78-^56785678-f234-a67812345671" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid 123456&78-^56785678F",
        )
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertFalse("123456&78-^567856781234-567812345670" in result)
        self.assertFalse("123456&78-^567856781234-567812345671" in result)
        self.assertFalse("123456&78-^567856781234-a67812345671" in result)
        self.assertTrue("123456&78-^56785678F234-a67812345671" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid 123456&78-^56785678f",
        )
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertFalse("123456&78-^567856781234-567812345670" in result)
        self.assertFalse("123456&78-^567856781234-567812345671" in result)
        self.assertFalse("123456&78-^567856781234-a67812345671" in result)
        self.assertTrue("123456&78-^56785678f234-a67812345671" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "--no-color",
            "complete",
            "model_fields test --uuid 123456&78-^56785678f234---A",
        )
        self.assertFalse("12345678-1234-5678-1234-567812345678" in result)
        self.assertFalse("12345678-1234-5678-1234-567812345679" in result)
        self.assertFalse("123456&78-^567856781234-567812345670" in result)
        self.assertFalse("123456&78-^567856781234-567812345671" in result)
        self.assertFalse("123456&78-^567856781234-a67812345671" in result)
        self.assertTrue("123456&78-^56785678f234---A67812345671" in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--uuid",
                    "123456&78-^56785678f234---A67812345671",
                )
            ),
            {
                "uuid": {
                    str(
                        ShellCompleteTester.objects.get(
                            uuid_field=UUID("12345678-5678-5678-f234-a67812345671")
                        ).pk
                    ): "12345678-5678-5678-f234-a67812345671"
                }
            },
        )

        with self.assertRaises(CommandError):
            call_command(
                "model_fields", "test", "--uuid", "G2345678-5678-5678-f234-a67812345671"
            )

        with self.assertRaises(CommandError):
            call_command(
                "model_fields", "test", "--uuid", "12345678-5678-5678-f234-a67812345675"
            )

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --uuid 12345678-5678-5678-f234-a678123456755",
        )
        self.assertFalse("12345678" in result)

    def test_id_field(self):
        result = StringIO()

        ids = (
            ShellCompleteTester.objects.filter(id__isnull=False)
            .values_list("id", flat=True)
            .order_by("id")
        )

        starts = {}
        for id in ids:
            starts.setdefault(str(id)[0], []).append(str(id))
        start_chars = set(starts.keys())

        ids = ids[0:50]

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --id ",
            shell=SHELL,
        )
        for id in ids:
            self.assertTrue(f"{id}" in result)

        for start_char in start_chars:
            expected = starts[start_char]
            unexpected = [str(id) for id in ids if str(id) not in expected]
            result = call_command(
                "shellcompletion",
                "--shell",
                SHELL,
                "complete",
                f"model_fields test --id {start_char}",
            )

            for comp in get_values(result):
                self.assertTrue(comp in expected)
                self.assertTrue(comp not in unexpected)

        for id in ids:
            self.assertEqual(
                json.loads(call_command("model_fields", "test", "--id", str(id))),
                {"id": id},
            )

        # test the limit option
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --id-limit ",
        )
        for id in ids[0:5]:
            self.assertTrue(f"{id}" in result)
        for id in ids[5:]:
            self.assertFalse(f"{id}" in result)

    def test_float_field(self):
        values = [1.1, 1.12, 2.2, 2.3, 2.4, 3.0, 4.0]
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --float ",
        )
        for value in values:
            self.assertTrue(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --float 1",
        )
        for value in [1.1, 1.12]:
            self.assertTrue(str(value) in result)
        for value in set([1.1, 1.12]) - set(values):
            self.assertFalse(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --float 1.1",
        )
        for value in [1.1, 1.12]:
            self.assertTrue(str(value) in result)
        for value in set([1.1, 1.12]) - set(values):
            self.assertFalse(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --float 1.12",
        )
        for value in [1.12]:
            self.assertTrue(str(value) in result)
        for value in set([1.12]) - set(values):
            self.assertFalse(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --float 2",
        )
        for value in [2.2, 2.3, 2.4]:
            self.assertTrue(str(value) in result)
        for value in set([2.2, 2.3, 2.4]) - set(values):
            self.assertFalse(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --float 2.",
        )
        for value in [2.2, 2.3, 2.4]:
            self.assertTrue(str(value) in result)
        for value in set([2.2, 2.3, 2.4]) - set(values):
            self.assertFalse(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --float 2.3",
        )
        for value in [2.3]:
            self.assertTrue(str(value) in result)
        for value in set([2.3]) - set(values):
            self.assertFalse(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --float 3",
        )
        for value in [3.0]:
            self.assertTrue(str(value) in result)
        for value in set([3.0]) - set(values):
            self.assertFalse(str(value) in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--float",
                    "2.3",
                )
            ),
            {
                "float": {
                    str(ShellCompleteTester.objects.get(float_field=2.3).pk): "2.3"
                }
            },
        )

    def test_decimal_field(self):
        values = [
            Decimal("1.5"),
            Decimal("1.50"),
            Decimal("1.51"),
            Decimal("1.52"),
            Decimal("1.2"),
            Decimal("1.6"),
        ]
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --decimal ",
        )
        for value in values:
            self.assertTrue(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --decimal 1.",
        )
        for value in values:
            self.assertTrue(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --decimal 1.",
        )
        for value in values:
            self.assertTrue(str(value) in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "model_fields test --decimal 1.5",
        )
        for value in set(values) - {Decimal("1.2"), Decimal("1.6")}:
            self.assertTrue(str(value) in result)
        for value in {Decimal("1.2"), Decimal("1.6")}:
            self.assertFalse(str(value) in result)

        self.assertEqual(
            json.loads(
                call_command(
                    "model_fields",
                    "test",
                    "--decimal",
                    "1.6",
                )
            ),
            {
                "decimal": {
                    str(
                        ShellCompleteTester.objects.get(decimal_field=Decimal("1.6")).pk
                    ): "1.60"
                }
            },
        )

    def test_option_complete(self):
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "--no-color",
            "complete",
            "model_fields test ",
        )
        self.assertTrue("--char" in result)
        self.assertTrue("--ichar" in result)
        self.assertTrue("--text" in result)
        self.assertTrue("--itext" in result)
        self.assertTrue("--id" in result)
        self.assertTrue("--id-limit" in result)
        self.assertTrue("--float" in result)
        self.assertTrue("--decimal" in result)
        self.assertTrue("--help" in result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "noarg cmd ",
            shell=SHELL,
        )
        self.assertFalse(result)

        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "noarg cmd -",
            shell=SHELL,
        )
        self.assertFalse(result)
        self.assertFalse("--" in result)

        # test what happens if we try to complete a non existing command
        result = call_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "noargs cmd ",
            shell=SHELL,
        )
        self.assertFalse(result)

    def test_unsupported_field(self):
        from django_typer.completers.model import ModelObjectCompleter

        with self.assertRaises(ValueError):
            ModelObjectCompleter(ShellCompleteTester, "binary_field")

    def test_shellcompletion_unsupported_shell(self):
        from django_typer.management.commands import shellcompletion

        def raise_error():
            raise RuntimeError()

        shellcompletion.detect_shell = raise_error
        cmd = get_command("shellcompletion", ShellCompletion)
        with self.assertRaises(CommandError):
            cmd.shell = "DNE"
            cmd.shell_class

    def test_shellcompletion_complete_cmd(self):
        # test that we can leave proceeding script off the complete argument
        result = self.shellcompletion.complete("./manage.py completion dj")
        self.assertTrue("django_typer" in result)
        result2 = self.shellcompletion.complete("completion dj")
        self.assertTrue("django_typer" in result2)
        self.assertEqual(result, result2)

    def test_custom_fallback(self):
        result = run_command(
            "shellcompletion",
            "--shell",
            SHELL,
            "complete",
            "--fallback",
            "tests.fallback.custom_fallback",
            "shell ",
        )[0]
        self.assertTrue("custom_fallback" in result)

        result = self.shellcompletion.complete(
            "shell ", fallback="tests.fallback.custom_fallback_cmd_str"
        )
        self.assertTrue("shell" in result)

        with self.assertRaises(CommandError):
            call_command(
                "shellcompletion",
                "--shell",
                SHELL,
                "complete",
                "--fallback",
                "tests.fallback.does_not_exist",
                "shell ",
            )

    def test_unknown_shell_error(self):
        shellcompletion = get_command("shellcompletion", ShellCompletion)
        shellcompletion._shell = None
        with self.assertRaises(CommandError):
            shellcompletion.shell = None

    def test_import_path_completer(self):
        result = self.shellcompletion.complete("multi --settings ")
        self.assertIn("importlib", result)
        self.assertIn("django_typer", result)
        self.assertIn("typer", result)
        self.assertNotIn(".django_typer", result)

        result = self.shellcompletion.complete("multi --settings ")
        self.assertIn("importlib", result)
        self.assertIn("django_typer", result)
        self.assertIn("typer", result)
        self.assertNotIn(".django_typer", result)

        result = self.shellcompletion.complete("multi --settings djan")
        self.assertIn("django", result)
        self.assertIn("django_typer", result)
        for comp in get_values(result):
            self.assertTrue(comp.startswith("djan"), f"{comp} does not start with djan")

        result = self.shellcompletion.complete("multi --settings django_ty")
        self.assertNotIn("importlib", result)
        self.assertNotIn(".django_typer", result)
        for comp in get_values(result):
            self.assertTrue(
                comp.startswith("django_ty"), f"{comp} does not start with django_ty"
            )

        self.assertIn("django_typer.completers", result)
        self.assertIn("django_typer.management", result)
        self.assertIn("django_typer.parsers", result)
        self.assertIn("django_typer.patch", result)
        self.assertIn("django_typer.types", result)
        self.assertIn("django_typer.utils", result)

        result = self.shellcompletion.complete("multi --settings tests.settings.")

        for comp in get_values(result):
            self.assertTrue(
                comp.startswith("tests.settings."),
                f"{comp} does not start with tests.settings.",
            )

        settings_expected = [
            "tests.settings.adapted",
            "tests.settings.adapted1",
            "tests.settings.adapted1_2",
            "tests.settings.adapted2_1",
            "tests.settings.base",
            "tests.settings.examples",
            "tests.settings.mod_init",
            "tests.settings.override",
            "tests.settings.settings2",
            "tests.settings.settings_fail_check",
            "tests.settings.settings_tb_bad_config",
            "tests.settings.settings_tb_change_defaults",
            "tests.settings.settings_tb_false",
            "tests.settings.settings_tb_no_install",
            "tests.settings.settings_tb_none",
            "tests.settings.settings_throw_init_exception",
            "tests.settings.typer_examples",
        ]
        for mod in settings_expected:
            self.assertIn(f"{mod}", result)

        result = self.shellcompletion.complete(
            "multi --settings tests.settings.typer_examples"
        )
        for mod in settings_expected[:-1]:
            self.assertNotIn(f"{mod}", result)

        self.assertIn(f"{settings_expected[-1]}", result)

    def test_pythonpath_completer(self):
        local_dirs = [
            Path(pth).as_posix() for pth in os.listdir() if Path(pth).is_dir()
        ]
        local_files = [Path(f).as_posix() for f in os.listdir() if not Path(f).is_dir()]
        result = self.shellcompletion.complete("multi --pythonpath ")
        for pth in local_dirs:
            self.assertIn(f"{pth}", result)
        for pth in local_files:
            self.assertNotIn(f"{pth}", result)

        for incomplete, sep in [(".", os.path.sep), (".\\", "\\")]:
            result = self.shellcompletion.complete(f"multi --pythonpath {incomplete}")
            for pth in local_dirs:
                self.assertIn(f".{sep}{pth}", result)
            for pth in local_files:
                self.assertNotIn(f".{sep}{pth}", result)

        local_dirs = [
            (Path("./src/django_typer") / d).as_posix()
            for d in os.listdir("./src/django_typer")
            if (Path("./src/django_typer") / d).is_dir()
        ]
        result = self.shellcompletion.complete("multi --pythonpath ./src/d")
        self.assertNotIn("./doc", result)
        self.assertIn("./src/django_typer", result)
        for pth in [
            *local_files,
            *[pth for pth in local_dirs if not pth.startswith("./src/d")],
        ]:
            self.assertNotIn(f"./src/{pth}", result)

        local_files = [
            (Path("./src/django_typer") / f).as_posix()
            for f in os.listdir("./src/django_typer")
            if not (Path("./src/django_typer") / f).is_dir()
        ]
        result = self.shellcompletion.complete(f"multi --pythonpath src{os.path.sep}dj")
        for pth in local_dirs:
            self.assertIn(pth.replace("/", os.path.sep), result)
        for pth in local_files:
            self.assertNotIn(pth.replace("/", os.path.sep), result)

        result = self.shellcompletion.complete("multi --pythonpath ./src/dj")
        for pth in local_dirs:
            self.assertIn(f"./{pth}", result)
        for pth in local_files:
            self.assertNotIn(f"./{pth}", result)

        result = self.shellcompletion.complete("multi --pythonpath ./src/django_typer")
        self.assertIn("./src/django_typer/management", result)
        self.assertIn("./src/django_typer/locale", result)
        self.assertNotIn("./src/django_typer/__init__.py", result)

        result = self.shellcompletion.complete("multi --pythonpath src/django_typer/")
        self.assertIn("src/django_typer/management", result)
        self.assertIn("src/django_typer/locale", result)
        self.assertNotIn("src/django_typer/__init__.py", result)

        result = self.shellcompletion.complete(
            "multi --pythonpath src/django_typer/man"
        )
        self.assertIn("src/django_typer/management/commands", result)
        self.assertNotIn("src/django_typer/examples", result)
        self.assertNotIn("src/django_typer/locale", result)
        self.assertNotIn("src/django_typer/management/__init__.py", result)

        result = self.shellcompletion.complete("multi --pythonpath /")
        for pth in os.listdir("/"):
            if pth.startswith("$"):
                continue  # TODO weird case of /\\$Recycle.Bin on windows
            if Path(f"/{pth}").is_dir():
                self.assertIn(f"/{pth}", result)
            else:
                self.assertNotIn(f"/{pth}", result)

        result = self.shellcompletion.complete(
            "multi --pythonpath src/django_typer/utils"
        )
        self.assertNotIn("src/django_typer/utils.py", result)

        result = self.shellcompletion.complete(
            "multi --pythonpath src/django_typer/does_not_exist"
        )
        self.assertNotIn("src/django_typer", result)

        result = self.shellcompletion.complete(
            "multi --pythonpath does_not_exist/does_not_exist"
        )
        self.assertNotIn("src", result)

    def test_path_completer(self):
        local_paths = [Path(pth).as_posix() for pth in os.listdir()]
        result = self.shellcompletion.complete("completion --path ")
        for pth in local_paths:
            # some very long paths in CI are chopped making this fail spuriously
            self.assertIn(f"{pth}", result)

        for incomplete, sep in [(".", os.path.sep), ("./", "/")]:
            result = self.shellcompletion.complete(f"completion --path {incomplete}")
            for pth in local_paths:
                self.assertIn(f".{sep}{pth}", result)

        result = self.shellcompletion.complete("completion --path ./C")
        self.assertIn("./CONTRIBUTING.md", result)
        self.assertIn("./CODE_OF_CONDUCT.md", result)
        for pth in [
            *[pth for pth in local_paths if not pth.startswith("C")],
        ]:
            self.assertNotIn(f"./{pth}", result)

        result = self.shellcompletion.complete("completion --path ./p")
        for pth in [
            *[pth for pth in local_paths if not pth.startswith("p")],
        ]:
            self.assertNotIn(f"./{pth}", result)

        local_paths = [
            (Path("src/django_typer") / d).as_posix()
            for d in os.listdir("src/django_typer")
            if (Path("src/django_typer") / d).is_dir()
        ]
        result = self.shellcompletion.complete(f"completion --path src{os.path.sep}dj")
        for pth in local_paths:
            self.assertIn(str(pth).replace("/", os.path.sep), result)

        result = self.shellcompletion.complete("completion --path ./src/dj")
        for pth in local_paths:
            self.assertIn(f"./{pth}", result)

        result = self.shellcompletion.complete("completion --path ./src/django_typer")
        self.assertIn("./src/django_typer/management", result)
        self.assertIn("./src/django_typer/locale", result)
        self.assertIn("./src/django_typer/__init__.py", result)

        result = self.shellcompletion.complete("completion --path src/django_typer/")
        self.assertIn("src/django_typer/management", result)
        self.assertIn("src/django_typer/locale", result)
        self.assertIn("src/django_typer/__init__.py", result)

        result = self.shellcompletion.complete("completion --path src/django_typer/man")
        self.assertIn("src/django_typer/management/__init__.py", result)
        self.assertIn("src/django_typer/management/commands", result)
        self.assertNotIn("src/django_typer/examples", result)
        self.assertNotIn("src/django_typer/locale", result)

        result = self.shellcompletion.complete("completion --path /")
        for pth in os.listdir("/"):
            if pth.startswith("$"):
                continue  # TODO weird case of /\\$Recycle.Bin on windows
            self.assertIn(f"/{pth}", result)

        result = self.shellcompletion.complete(
            "completion --path src/django_typer/completers"
        )
        self.assertIn("src/django_typer/completers", result)

        result = self.shellcompletion.complete(
            "completion --path src/django_typer/apps.py"
        )
        self.assertIn("src/django_typer/apps.py", result)

        result = self.shellcompletion.complete(
            "completion --path src/django_typer/does_not_exist"
        )
        self.assertNotIn("src/django_typer", result)

        result = self.shellcompletion.complete(
            "completion --path does_not_exist/does_not_exist"
        )
        self.assertNotIn("src/django_typer", result)

    def test_mixed_divider_path_completer(self):
        shellcompletion = get_command("shellcompletion", ShellCompletion)
        shellcompletion.init(shell=SHELL)
        completions = shellcompletion.complete(
            "completion --path ./src/django_typer\\compl"
        )
        if platform.system() == "Windows":
            self.assertIn("./src/django_typer\\completers", completions)
        else:
            self.assertFalse(completions.strip())

    def test_these_strings_completer(self):
        for opt in ["--str", "--dup"]:
            result = self.shellcompletion.complete(f"completion {opt} ")
            for s in ["str1", "str2", "ustr"]:
                self.assertIn(f"{s}", result)

            result = self.shellcompletion.complete(f"completion {opt} s")
            self.assertNotIn("ustr", result)
            for s in ["str1", "str2"]:
                self.assertIn(f"{s}", result)

            result = self.shellcompletion.complete(f"completion {opt} str")
            self.assertNotIn("ustr", result)
            for s in ["str1", "str2"]:
                self.assertIn(f"{s}", result)

        result = self.shellcompletion.complete("completion --str str1 --str ")
        self.assertNotIn("str1", result)
        for s in ["str2", "ustr"]:
            self.assertIn(f"{s}", result)

        result = self.shellcompletion.complete("completion --dup str1 --dup ")
        for s in ["str1", "str2", "ustr"]:
            self.assertIn(f"{s}", result)

        result = self.shellcompletion.complete("completion --str str1 --dup ")
        for s in ["str1", "str2", "ustr"]:
            self.assertIn(f"{s}", result)

        result = self.shellcompletion.complete("completion --dup str1 --str ")
        for s in ["str1", "str2", "ustr"]:
            self.assertIn(f"{s}", result)

    def test_chain_and_commands_completer(self):
        result = self.shellcompletion.complete("completion --cmd dj").strip()

        self.assertTrue("django" in result)
        self.assertTrue("django_typer" in result)

        self.assertTrue("dj_params1" in result)
        self.assertTrue("dj_params2" in result)
        self.assertTrue("dj_params3" in result)
        self.assertTrue("dj_params4" in result)

        result = self.shellcompletion.complete(
            "completion --cmd django_typer --cmd dj"
        ).strip()

        self.assertTrue("django" in result)
        self.assertFalse("django_typer" in result)

        self.assertTrue("dj_params1" in result)
        self.assertTrue("dj_params2" in result)
        self.assertTrue("dj_params3" in result)
        self.assertTrue("dj_params4" in result)

        result = self.shellcompletion.complete(
            "completion --cmd-dup django_typer --cmd-dup dj"
        ).strip()

        self.assertTrue("django" in result)
        self.assertTrue("django_typer" in result)

        self.assertTrue("dj_params1" in result)
        self.assertTrue("dj_params2" in result)
        self.assertTrue("dj_params3" in result)
        self.assertTrue("dj_params4" in result)

        result = self.shellcompletion.complete("completion --cmd-first dj").strip()

        self.assertTrue("django" in result)
        self.assertTrue("django_typer" in result)

        self.assertFalse("dj_params1" in result)
        self.assertFalse("dj_params2" in result)
        self.assertFalse("dj_params3" in result)
        self.assertFalse("dj_params4" in result)

    def test_databases_completer(self):
        result = self.shellcompletion.complete("completion --db ").strip()

        self.assertTrue("default" in result)

    def test_model_completer_argument_test(self):
        from django_typer.completers.model import ModelObjectCompleter

        class NotAModel:
            pass

        with self.assertRaises(ValueError):
            ModelObjectCompleter(NotAModel, "char_field", "test")

    def test_empty_complete_and_env_stability(self):
        env = os.environ.copy()
        self.assertIn("makemigrations", self.shellcompletion.complete(""))
        self.assertEqual(env, os.environ)
        self.assertIn("makemigrations", self.shellcompletion.complete())
        self.assertEqual(env, os.environ)

    def test_return_field_value(self):
        completions = get_values(self.shellcompletion.complete("field_value P54"))
        self.assertTrue("P541D" in completions)
        self.assertEqual(call_command("field_value", "P541D"), "P541D")
        self.assertEqual(run_command("field_value", "P541D")[0].strip(), "P541D")

        with self.assertRaisesMessage(CommandError, "Test custom error"):
            call_command("field_value", "P541X")

    def test_return_queryset(self):
        completions = get_values(self.shellcompletion.complete("queryset P54"))
        self.assertTrue("P541D" in completions)
        objects = ShellCompleteTester.objects.filter(duration_field=timedelta(days=541))
        data1 = json.loads(call_command("queryset", "P541D"))
        for obj in objects:
            self.assertEqual(data1[str(obj.id)], "P541D")

    def test_cursor_position(self):
        completions = get_values(
            self.shellcompletion.complete("shellcompletion --set  install", 21)
        )
        self.assertTrue("--settings" in completions)
        completions = get_values(
            self.shellcompletion.complete("shellcompletion --settings  install", 27)
        )
        self.assertTrue("tests" in completions)

    def test_language_completer(self):
        from django.conf import settings

        languages = {code: language for code, language in settings.LANGUAGES}
        all_e = {lang for lang, _ in settings.LANGUAGES if lang.startswith("e")}
        result = get_values_and_helps(
            self.shellcompletion.complete("completion --lang e").strip()
        )
        completed_set = {result[0] for result in result}
        self.assertEqual(completed_set, all_e)
        if self.shellcompletion.shell != "bash":
            for code, language in result:
                self.assertEqual(language, languages[code])

        # sanity check
        self.assertTrue("es" in completed_set)
        self.assertTrue("en" in completed_set)

    def test_setting_completer(self):
        from django.conf import settings

        settings_expected = {
            setting
            for setting in dir(settings)
            if setting.isupper() and setting.startswith("S")
        }

        result = get_values_and_helps(
            self.shellcompletion.complete("completion --setting S").strip()
        )
        completed_set = {result[0] for result in result}
        self.assertEqual(completed_set, settings_expected)
        # sanity check
        self.assertTrue("STATIC_URL" in completed_set)
        self.assertTrue("SECRET_KEY" in completed_set)


@override_settings(
    MEDIA_ROOT=Path(__file__).parent / "media",
    STATIC_ROOT=str(Path(__file__).parent / "static"),
)
class TestRestrictedRootPathCompleters(ParserCompleterMixin, TestCase):
    MODEL_CLASS = ShellCompleteTester

    def test_relative_import_path(self):
        completions = get_values(
            self.shellcompletion.complete("completion --settings-module ")
        )

        mods = [
            mod[:-3]
            for mod in os.listdir(Path(__file__).parent / "settings")
            if mod.endswith(".py") and not mod.startswith("__")
        ]
        self.assertEqual(
            len(set(mods) - set(completions)), 0, set(mods) - set(completions)
        )

    def test_media_root_completer(self):
        completions = get_values(self.shellcompletion.complete("completion --media "))
        self.assertEqual(completions, ["file.txt"])

    def test_static_root_completer(self):
        completions = get_values(self.shellcompletion.complete("completion --statics "))
        self.assertEqual(set(completions), {"subdir", "static1.txt"})

        completions = get_values(
            self.shellcompletion.complete("completion --statics subd")
        )
        self.assertEqual(completions, ["subdir"])

        completions = get_values(
            self.shellcompletion.complete("completion --statics subdir/")
        )
        self.assertEqual(completions, ["subdir/static2.txt"])

        completions = get_values(
            self.shellcompletion.complete("completion --statics /subdir/")
        )
        self.assertEqual(completions, ["/subdir/static2.txt"])

    @override_settings(STATIC_ROOT=None)
    def test_static_root_completer_no_setting(self):
        completions = get_values(self.shellcompletion.complete("completion --statics "))
        self.assertEqual(set(completions), set(os.listdir()))


class TestDateTimeParserCompleter(ParserCompleterMixin, TestCase):
    tz_info = None
    MODEL_CLASS = ShellCompleteTester

    def populate_db(self):
        from django.conf import settings

        ShellCompleteTester.objects.all().delete()
        if settings.USE_TZ:
            self.tz_info = get_default_timezone()
        else:
            self.tz_info = None
        self.field_values = {
            "datetime_field": [
                datetime(2021, 1, 31, 0, 0, 0, tzinfo=self.tz_info),
                datetime(2021, 2, 9, 2, 0, 0, tzinfo=self.tz_info),
                datetime(2021, 2, 10, 20, 0, 0, tzinfo=self.tz_info),
                datetime(2021, 2, 10, 22, 0, 0, tzinfo=self.tz_info),
                datetime(2024, 2, 29, 22, 30, 45, 990000, tzinfo=self.tz_info),
                datetime(2024, 2, 29, 22, 30, 46, 990000, tzinfo=self.tz_info),
                datetime(2024, 9, 20, 22, 30, 46, 990100, tzinfo=self.tz_info),
                datetime(2024, 9, 20, 22, 30, 46, 999900, tzinfo=self.tz_info),
                datetime(2025, 2, 28, 23, 59, 59, 999999, tzinfo=self.tz_info),
            ]
        }
        super().setUp()

    def run_tests(self, tz1="+00:00", tz2="+00:00"):
        self.assertEqual(
            get_values(self.shellcompletion.complete("model_fields test --datetime ")),
            [
                f"2021-01-31T00:00:00{tz1}",
                f"2021-02-09T02:00:00{tz1}",
                f"2021-02-10T20:00:00{tz1}",
                f"2021-02-10T22:00:00{tz1}",
                f"2024-02-29T22:30:45.990000{tz1}",
                f"2024-02-29T22:30:46.990000{tz1}",
                f"2024-09-20T22:30:46.990100{tz2}",
                f"2024-09-20T22:30:46.999900{tz2}",
                f"2025-02-28T23:59:59.999999{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete("model_fields test --datetime 202")
            ),
            [
                f"2021-01-31T00:00:00{tz1}",
                f"2021-02-09T02:00:00{tz1}",
                f"2021-02-10T20:00:00{tz1}",
                f"2021-02-10T22:00:00{tz1}",
                f"2024-02-29T22:30:45.990000{tz1}",
                f"2024-02-29T22:30:46.990000{tz1}",
                f"2024-09-20T22:30:46.990100{tz2}",
                f"2024-09-20T22:30:46.999900{tz2}",
                f"2025-02-28T23:59:59.999999{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete("model_fields test --datetime 2021-")
            ),
            [
                f"2021-01-31T00:00:00{tz1}",
                f"2021-02-09T02:00:00{tz1}",
                f"2021-02-10T20:00:00{tz1}",
                f"2021-02-10T22:00:00{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete("model_fields test --datetime 2021-02-1")
            ),
            [
                f"2021-02-10T20:00:00{tz1}",
                f"2021-02-10T22:00:00{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2021-02-10T"
                )
            ),
            [
                f"2021-02-10T20:00:00{tz1}",
                f"2021-02-10T22:00:00{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2021-02-10T2"
                )
            ),
            [
                f"2021-02-10T20:00:00{tz1}",
                f"2021-02-10T22:00:00{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2021-02-10T22:"
                )
            ),
            [
                f"2021-02-10T22:00:00{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2021-02-10T22:00:"
                )
            ),
            [
                f"2021-02-10T22:00:00{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2021-02-10T22:00:00+"
                )
            ),
            [
                f"2021-02-10T22:00:00{'+' if not tz1 else ''}{tz1}",
            ]
            if tz1.startswith("+")
            else [],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2021-02-10T22:00:00+00:"
                )
            ),
            [
                f"2021-02-10T22:00:00{'+00:' if not tz1 else ''}{tz1}",
            ]
            if tz1.startswith("+00:")
            else [],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2021-02-10T22:00:00+00:0"
                )
            ),
            [
                f"2021-02-10T22:00:00{'+00:0' if not tz1 else ''}{tz1}",
            ]
            if tz1.startswith("+00:0")
            else [],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    f"model_fields test --datetime 2021-02-10T22:00:00{tz1}"
                )
            ),
            [
                f"2021-02-10T22:00:00{tz1}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2024-02-29T22:30:4"
                )
            ),
            [f"2024-02-29T22:30:45.990000{tz1}", f"2024-02-29T22:30:46.990000{tz1}"],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2024-02-29T22:30:46."
                )
            ),
            [f"2024-02-29T22:30:46.990000{tz1}"],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2024-02-29T22:30:46.9"
                )
            ),
            [f"2024-02-29T22:30:46.990000{tz1}"],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2024-09-20T22:30:46.99"
                )
            ),
            [
                f"2024-09-20T22:30:46.990100{tz2}",
                f"2024-09-20T22:30:46.999900{tz2}",
            ],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2024-09-20T22:30:46.990"
                )
            ),
            [f"2024-09-20T22:30:46.990100{tz2}"],
        )

        self.assertEqual(
            get_values(
                self.shellcompletion.complete(
                    "model_fields test --datetime 2024-09-20T22:30:46.999"
                )
            ),
            [f"2024-09-20T22:30:46.999900{tz2}"],
        )

        for dt in self.field_values["datetime_field"]:
            self.assertEqual(
                json.loads(call_command("model_fields", "test", "--datetime", str(dt))),
                {
                    "datetime": {
                        str(ShellCompleteTester.objects.get(datetime_field=dt).pk): str(
                            dt
                        )
                    }
                },
            )

    @override_settings(USE_TZ=True)
    def test_datetime_field_use_tz(self):
        self.assertEqual(get_default_timezone_name(), "UTC")
        self.populate_db()
        self.run_tests()

    @override_settings(USE_TZ=False)
    def test_datetime_field_no_tz(self):
        self.assertEqual(get_default_timezone_name(), "UTC")
        self.populate_db()
        self.run_tests(tz1="", tz2="")

    @pytest.mark.skipif(
        connection.vendor == "sqlite", reason="Skipped because the database is SQLite"
    )
    @override_settings(USE_TZ=True, TIME_ZONE="America/Los_Angeles")
    def test_datetime_field_tz_pacific(self):
        self.assertEqual(get_default_timezone_name(), "America/Los_Angeles")
        self.populate_db()
        self.run_tests(tz1="-08:00", tz2="-07:00")


class TestChoicesCompletion(ParserCompleterMixin, TestCase):
    if django.VERSION[0] < 5:
        MODEL_CLASS = ChoicesShellCompleteTester
    else:
        from tests.apps.dj5plus.models import ChoicesShellCompleteTesterDJ5Plus

        MODEL_CLASS = ChoicesShellCompleteTesterDJ5Plus

    # creates models with increasing numbers of instances for each additional choice
    field_values = {
        field: [
            choice[0]
            for idx, choice in enumerate(
                getattr(
                    ChoicesShellCompleteTester._meta.get_field(field), "choices", []
                )
                or []
            )
            for _ in range(0, idx + 1)
        ]
        for field in ["char_choice", "int_choice", "ip_choice"]
    }

    def test_choices_completer(self):
        n_tests = 0
        for field, values in self.field_values.items():
            field_choices = {
                k: v for k, v in self.MODEL_CLASS._meta.get_field(field).choices
            }
            for value in values:
                value_str = str(value)
                for idx in range(0, len(value_str)):
                    test_str = value_str[0:idx]
                    completions = get_values_and_helps(
                        self.shellcompletion.complete(
                            f"choices --{field.replace('_', '-')}s {test_str}"
                        )
                    )
                    str_qry = self.MODEL_CLASS.objects.annotate(
                        field_as_str=Cast(field, output_field=CharField())
                    )
                    if test_str:
                        str_qry = str_qry.filter(field_as_str__startswith=test_str)
                    else:
                        str_qry = str_qry.filter(**{f"{field}__isnull": False})
                    expected = list(
                        str_qry.values_list("field_as_str", flat=True).distinct()
                    )

                    if not expected:
                        self.assertFalse(completions)
                        continue

                    n_tests += 1

                    # postgres normalizes the IPs - revert that
                    if field == "ip_choice":
                        for idx in range(0, len(expected)):
                            expected[idx] = expected[idx].split("/")[0]

                    self.assertEqual(
                        set(expected),
                        set([comp[0] for comp in completions]),
                    )
                    # verify helps
                    if self.shellcompletion.shell != "bash":
                        for val, help_txt in completions:
                            self.assertEqual(help_txt, field_choices[type(value)(val)])

        # sanity check!
        self.assertEqual(n_tests, 872)
