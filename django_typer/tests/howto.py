#!/usr/bin/env python
"""A shortcut manage script for running the howto example code"""

from django_typer.tests.manage import main

if __name__ == "__main__":
    main("django_typer.tests.settings.howto")