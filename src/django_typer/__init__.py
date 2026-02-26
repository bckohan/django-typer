r"""
::

      ██████╗      ██╗ █████╗ ███╗   ██╗ ██████╗  ██████╗
      ██╔══██╗     ██║██╔══██╗████╗  ██║██╔════╝ ██╔═══██╗
      ██║  ██║     ██║███████║██╔██╗ ██║██║  ███╗██║   ██║
      ██║  ██║██   ██║██╔══██║██║╚██╗██║██║   ██║██║   ██║
      ██████╔╝╚█████╔╝██║  ██║██║ ╚████║╚██████╔╝╚██████╔╝
      ╚═════╝  ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝

         ████████╗██╗   ██╗██████╗ ███████╗██████╗
         ╚══██╔══╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗
            ██║    ╚████╔╝ ██████╔╝█████╗  ██████╔╝
            ██║     ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗
            ██║      ██║   ██║     ███████╗██║  ██║
            ╚═╝      ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝


django-typer_ provides an extension class,
:class:`~django_typer.management.TyperCommand`, to the
:class:`~django.core.management.BaseCommand` class that melds the Typer_ and
:doc:`click <click:index>` infrastructure with the Django_ infrastructure. The result is
all the ease of specifying commands, groups and options and arguments using Typer_ and
:doc:`click <click:index>` in a way that feels like and is interface compatible with
Django_'s :class:`~django.core.management.BaseCommand` This should enable a smooth
transition for existing Django_ commands and an intuitive feel for implementing new
commands.

django-typer_ also supports shell completion for bash_, zsh_, fish_ and powershell_ and
extends that support to native Django_ management commands as well.


The goal of django-typer_ is to provide full Typer_ style functionality while
maintaining compatibility with the Django management command system. This means that the
:class:`~django.core.management.BaseCommand` interface is preserved and the Typer_
interface is added on top of it. This means that this code base is more robust to
changes in the Django management command system - because most of the base class
functionality is preserved but many Typer_ and :doc:`click <click:index>` internals are
used directly to achieve this. We rely on robust CI to catch breaking changes upstream
and keep a tight version lock on Typer.
"""

VERSION = (3, 6, 3)

__title__ = "Django Typer"
__version__ = ".".join(str(i) for i in VERSION)
__author__ = "Brian Kohan"
__license__ = "MIT"
__copyright__ = "Copyright 2023-2026 Brian Kohan"
