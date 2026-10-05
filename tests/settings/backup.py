from pathlib import Path

from .base import *

# the backup example is a single database project - the second database the
# base settings configure for the transaction tests is not part of it
DATABASES = {"default": DATABASES["default"]}

INSTALLED_APPS = [
    "tests.apps.examples.plugins.backup",
    "tests.apps.util",
    "django_typer",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

from tests.apps import examples

MEDIA_ROOT = str(Path(examples.__file__).parent.parent.parent / "media")
