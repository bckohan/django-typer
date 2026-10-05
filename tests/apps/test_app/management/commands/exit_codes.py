"""
Exercise how typer.Exit, typer.Abort, interrupts and sys.exit leave a compound
command - see issue #318.
"""

import sys
import threading

import typer
from django.core.management import CommandError

from django_typer.management import TyperCommand, command


class Command(TyperCommand):
    @command()
    def exit(self, code: int = 0):
        raise typer.Exit(code)

    @command()
    def abort(self):
        raise typer.Abort()

    @command()
    def interrupt(self):
        raise KeyboardInterrupt()

    @command()
    def eof(self):
        # what a prompt raises when input has ended
        raise EOFError()

    @command()
    def sysexit(self, code: int = 0):
        sys.exit(code)

    @command()
    def error(self, code: int = 1):
        raise CommandError("something went wrong", returncode=code)

    @command()
    def boom(self):
        raise RuntimeError("unexpected failure")

    @command()
    def ok(self):
        return "done"

    @command()
    def say(self, message: str):
        self.stdout.write(message)

    @command()
    def spew(self, size: int = 300000):
        """Write a lot - more than a pipe buffers - to stdout."""
        self.stdout.write("x" * size)

    @command()
    def wait_then_exit(self, code: int = 0):
        """Signal that we are running, wait to be released, then exit."""
        started.set()
        release.wait(timeout=10)
        raise typer.Exit(code)


# used by the tests to interleave executions of a shared command instance
started = threading.Event()
release = threading.Event()
