.. include:: ./refs.rst

==========
Change Log
==========

v3.6.2 (2026-02-16)
===================

* Support typer 0.24

v3.6.1 (2026-02-14)
===================

* Remove monkey patch for ``TYPER_USE_RICH`` environment variable - `this was fixed upstream.
  <https://github.com/fastapi/typer/pull/1539>`_
* Minimum typer is now 0.23.1.


v3.6.0 (2026-02-12)
===================

* `Support typer 0.22.0. <https://github.com/django-commons/django-typer/pull/259>`_

  * :pypi:`typer-slim` has been `made an alias for typer <https://github.com/fastapi/typer/pull/1522>`_. This means rich is installed
    automatically now.
  * If you want to disable rich:

    1. **At runtime**: you can set the environment variable ``TYPER_USE_RICH`` to ``0`` or
       ``false``.
    2. **In code (for all invocations)**: you can set the class variable ``rich_markup_mode`` to
       ``None`` on your command class or any parent group. This will disable rich for that command
       and all subcommands.

* You may also run into an `error like this <https://github.com/fastapi/typer/issues/1537>`_:

  .. code-block:: console

    Traceback (most recent call last):
      File "/home/user/code/myproject/main.py", line 1, in <module>
        import typer
    ModuleNotFoundError: No module named 'typer'

  If this happens just reinstall your virtual environment.

v3.5.1 (2026-01-13)
===================

* Support typer-slim 0.21
* Fixed `options_metavar interface change causes regression <https://github.com/django-commons/django-typer/issues/254>`_

  - ``options_metavar`` parameters now apply correctly

v3.5.0 (2025-11-21)
===================

* `Drop support for Django 3.2-4.1 <https://github.com/django-commons/django-typer/issues/248>`_
* `Drop support for python 3.9 <https://github.com/django-commons/django-typer/issues/247>`_

v3.4.0 (2025-10-20)
===================

* `Support Typer version >=0.20 <https://github.com/django-commons/django-typer/issues/241>`_

v3.3.2 (2025-09-27)
===================

* Early support release for Django 6.0 (tested against 6.0a1)

v3.3.1 (2025-09-22)
===================

* Fixed `--hide/show locals option on stack trace is not working as expected. <https://github.com/django-commons/django-typer/issues/233>`_
* Implemented `Support typer 0.18-0.19 and click 8.3 <https://github.com/django-commons/django-typer/issues/232>`_

v3.3.0 (2025-08-31)
===================

* Documented `Add note on startup performance to docs. <https://github.com/django-commons/django-typer/issues/227>`_
* Fixed `Support typer 0.17 <https://github.com/django-commons/django-typer/issues/225>`_

v3.2.2 (2025-07-17)
===================

* Fixed `Raise a CommandError instead of a KeyError if get_command does not find the command. <https://github.com/django-commons/django-typer/issues/222>`_

v3.2.1 (2025-07-16)
===================

* Docs `Add django-admin role for shellcompletion reference. <https://github.com/django-commons/django-typer/issues/221>`_

v3.2.0 (2025-05-31)
===================

* Support Python 3.14
* Implemented `Support click 8.2 <https://github.com/django-commons/django-typer/issues/215>`_

v3.1.1 (2025-04-30)
===================

* Implemented `Support rich 14 <https://github.com/django-commons/django-typer/issues/213>`_

v3.1.0 (2025-04-02)
===================

* Fixed `Fish shell completion fails for any script named something other than "manage" <https://github.com/django-commons/django-typer/issues/207>`_
* Fixed `shellcompletion install fails on fish when the command resolves to a script path <https://github.com/django-commons/django-typer/issues/206>`_
* Implemented `Add completer for settings names. <https://github.com/django-commons/django-typer/issues/203>`_
* Implemented `Separate ModelObjectCompleter default queries out into standalone functions. <https://github.com/django-commons/django-typer/issues/202>`_
* Fixed `Shell completion tests let failures through in CI <https://github.com/django-commons/django-typer/issues/194>`_
* Fixed `fish completion installs should respect XDG_CONFIG_HOME <https://github.com/django-commons/django-typer/issues/193>`_
* Fixed `zsh completion installs should respect ZDOTDIR <https://github.com/django-commons/django-typer/issues/192>`_
* Implemented `Prompt before writing to dotfiles when installing completions <https://github.com/django-commons/django-typer/issues/189>`_
* Implemented `Support Django 5.2 <https://github.com/django-commons/django-typer/issues/188>`_
* Implemented `Use intersphinx for external document references. <https://github.com/django-commons/django-typer/issues/187>`_
* Implemented `Add completer for language codes. <https://github.com/django-commons/django-typer/issues/186>`_
* Implemented `Switch poetry -> uv <https://github.com/django-commons/django-typer/issues/185>`_
* Implemented `Model object completers should handle fields with choices appropriately <https://github.com/django-commons/django-typer/issues/182>`_
* Implemented `Require tests to pass before release action runs. <https://github.com/django-commons/django-typer/issues/173>`_


v3.0.0 (2025-02-16)
===================

* Implemented `Completer for media files. <https://github.com/django-commons/django-typer/issues/175>`_
* Implemented `Completer for static files. <https://github.com/django-commons/django-typer/issues/174>`_
* Fixed `Completions before the end of the typed command string do not work. <https://github.com/django-commons/django-typer/issues/168>`_
* Implemented `Add print_return class field to enable/disable result printing <https://github.com/django-commons/django-typer/issues/167>`_
* BREAKING `Default rich traceback should not show locals - its too much information. <https://github.com/django-commons/django-typer/issues/166>`_
* Implemented `path completers should be configurable with a root directory other than cwd <https://github.com/django-commons/django-typer/issues/165>`_
* Implemented `Migrate pyproject.toml to poetry 2 and portable project specifiers. <https://github.com/django-commons/django-typer/issues/164>`_
* BREAKING `Split parsers.py and completers.py into submodules. <https://github.com/django-commons/django-typer/issues/163>`_
* Implemented `Model completer/parser should support returning the field value <https://github.com/django-commons/django-typer/issues/162>`_
* Fixed `Model objects with null lookup fields should not be included in model field completion output <https://github.com/django-commons/django-typer/issues/160>`_
* Implemented `Add a performance regression. <https://github.com/django-commons/django-typer/issues/157>`_
* Implemented `Use in-house shell completer classes. <https://github.com/django-commons/django-typer/issues/156>`_
* Implemented `Add precommit hook to fix safe lint and format issues <https://github.com/django-commons/django-typer/issues/153>`_
* Fixed `Fish shell complete is broken when rich is installed. <https://github.com/django-commons/django-typer/issues/152>`_
* BREAKING `Remove name parameter from initialize()/callback(). <https://github.com/django-commons/django-typer/issues/150>`_
* Implemented `Run full test suite on mac osx <https://github.com/django-commons/django-typer/issues/148>`_
* Implemented `Convert check.sh to justfile <https://github.com/django-commons/django-typer/issues/147>`_
* Implemented `Run full test suite on windows in CI <https://github.com/django-commons/django-typer/issues/146>`_
* Implemented `ANSI color control sequences should optionally be scrubbed from shell completions <https://github.com/django-commons/django-typer/issues/144>`_
* Fixed `supressed_base_arguments are still present in the Context <https://github.com/django-commons/django-typer/issues/143>`_
* Implemented `Add showcase of commands using django-typer to docs <https://github.com/django-commons/django-typer/issues/142>`_
* Implemented `Add a @finalize decorator for functions to collect/operate on subroutine results. <https://github.com/django-commons/django-typer/issues/140>`_
* Fixed `Remove management imports in django_typer/__init__.py <https://github.com/django-commons/django-typer/issues/95>`_
* Fixed `ParamSpec includes self for group methods <https://github.com/django-commons/django-typer/issues/73>`_
* Fixed `Installed shellcompletion scripts do not pass values of --settings or --pythonpath <https://github.com/django-commons/django-typer/issues/68>`_
* Implemented `Add support for QuerySet parameter types. <https://github.com/django-commons/django-typer/issues/58>`_
* Fixed `shellcompletion complete should print to the command's stdout. <https://github.com/django-commons/django-typer/issues/19>`_
* Implemented `Add translations for helps.. <https://github.com/django-commons/django-typer/issues/18>`_
* Implemented `Add completer/parser for FileField and FilePathField <https://github.com/django-commons/django-typer/issues/17>`_
* Implemented `Add completer/parser for DurationField <https://github.com/django-commons/django-typer/issues/16>`_
* Implemented `Add completer/parser for DateTimeField <https://github.com/django-commons/django-typer/issues/15>`_
* Implemented `Add completer/parser for DateField <https://github.com/django-commons/django-typer/issues/14>`_
* Implemented `Add completer/parser for TimeField <https://github.com/django-commons/django-typer/issues/13>`_
* Implemented `Improve shell completion continuous integration tests  <https://github.com/django-commons/django-typer/issues/11>`_


Migrating from 2.x to 3.x
-------------------------

* Imports from the ``django_typer`` namespace have been removed. You should now import from
  ``django_typer.management``.

* The `name` parameter has been removed from
  :func:`django_typer.management.initialize()` and :func:`django_typer.management.Typer.callback()`.
  This change was forced by `upstream changes <https://github.com/fastapi/typer/pull/1052>`_ in
  Typer_ that will allow :func:`django_typer.management.Typer.add_typer` to define commands across
  multiple files.

* Rich tracebacks will not include local variables by default. To replicate the old behavior
  you will need to add this to your settings:

  .. code-block:: python

      RICH_TRACEBACK_CONFIG={"show_locals": True}

  --show-locals and --hide-locals common parameters are added to toggle local variables on
  and off in the stack trace output.

Shell Completions
~~~~~~~~~~~~~~~~~

.. list-table:: **Some imports have changed in the django_typer namespace!**
  :widths: 50 50
  :header-rows: 1

  * - old
    - new
  * - ``management.model_parser_completer``
    - ``utils.model_parser_completer``
  * - ``parsers.ModelObjectParser``
    - ``parsers.model.ModelObjectParser``
  * - ``parsers.parse_app_label``
    - ``parsers.apps.app_config``
  * - ``completers.complete_app_label``
    - ``completers.apps.app_labels``
  * - ``completers.commands``
    - ``completers.cmd.commands``
  * - ``completers.databases``
    - ``completers.db.databases``
  * - ``completers.ModelObjectCompleter``
    - ``completers.model.ModelObjectCompleter``
  * - ``completers.complete_path``
    - ``completers.path.paths``
  * - ``completers.complete_directory``
    - ``completers.path.directories``
  * - ``completers.complete_import_path``
    - ``completers.path.import_paths``

* If you are using shell tab completions you will need to reinstall the completion scripts. Using
  the `shellcompletion install` command. To be extra safe you may want to uninstall the old
  scripts before updating, using the v2.x ``shellcompletion remove`` command.

* The interface to shellcompletion has changed. ``--shell`` is now an initialization option and
  ``remove`` was renamed to ``uninstall``.:

    .. code-block::

        # old interface
        manage shellcompletion complete --shell zsh "command string"
        manage shellcompletion remove

        # new interface
        manage shellcompletion --shell zsh complete "command string"
        manage shellcompletion uninstall

* The function signature for :ref:`shellcompletion fallbacks <completion_fallbacks>` has changed.
  The fallback signature is now:

    .. code-block::

        import typing as t
        from click.shell_complete import CompletionItem

        def fallback(args: t.List[str], incomplete: str) -> t.List[CompletionItem]:
            ...


v2.6.0 (2024-12-03)
===================

* Fixed `On Python 3.13, sometimes flush is called on the stream wrapped by OutputWrapper after it is closed. <https://github.com/django-commons/django-typer/issues/155>`_
* Implemented `Support Typer 0.15.x <https://github.com/django-commons/django-typer/issues/154>`_

v2.5.0 (2024-11-29)
===================

* Implemented `Support Typer >=0.14 <https://github.com/django-commons/django-typer/issues/149>`_
* Fixed `Typer-style interface throws an assertion when no callback is present on a subgroup. <https://github.com/django-commons/django-typer/issues/145>`_

v2.4.0 (2024-11-07)
===================

* Implemented `Support Typer 0.13 <https://github.com/django-commons/django-typer/issues/138>`_

v2.3.0 (2024-10-13)
===================

* Fixed `Inheritance more than one level deep of TyperCommands does not work. <https://github.com/django-commons/django-typer/issues/131>`_
* Implemented `Drop python 3.8 support. <https://github.com/django-commons/django-typer/issues/130>`_
* Implemented `Command help order should respect definition order for class based commands. <https://github.com/django-commons/django-typer/issues/129>`_
* Fixed `Overriding the command group class does not work. <https://github.com/django-commons/django-typer/issues/128>`_
* Completed `Add project to test PyPI <https://github.com/django-commons/django-typer/issues/126>`_
* Completed `Open up vulnerability reporting and add security policy. <https://github.com/django-commons/django-typer/issues/124>`_
* Completed `Add example of custom plugin logic to plugins tutorial. <https://github.com/django-commons/django-typer/issues/122>`_
* Completed `Move architecture in docs to ARCHITECTURE.md <https://github.com/django-commons/django-typer/issues/121>`_
* Completed `Transfer to django-commons <https://github.com/django-commons/django-typer/issues/117>`_
* Completed `Add howto for how to change the display order of commands in help. <https://github.com/django-commons/django-typer/issues/116>`_

v2.2.2 (2024-08-25)
====================

* Implemented `Support python 3.13 <https://github.com/django-commons/django-typer/issues/109>`_
* Fixed `typer > 0.12.5 toggles rich help renderings off by default <https://github.com/django-commons/django-typer/issues/108>`_

v2.2.1 (2024-08-17)
====================

* Fixed `Remove shell_complete monkey patch when upstream PR is merged. <https://github.com/django-commons/django-typer/issues/66>`_

v2.2.0 (2024-07-26)
====================

* Implemented `ModelObjectCompleter should optionally accept a QuerySet in place of a Model class. <https://github.com/django-commons/django-typer/issues/96>`_

v2.1.3 (2024-07-15)
====================

* Fixed `Move from django_typer to django_typer.management broke doc reference links. <https://github.com/django-commons/django-typer/issues/98>`_
* Implemented `Support Django 5.1 <https://github.com/django-commons/django-typer/issues/97>`_

v2.1.2 (2024-06-07)
====================

* Fixed `Type hint kwargs to silence pylance warnings about partially unknown types <https://github.com/django-commons/django-typer/issues/93>`_

v2.1.1 (2024-06-06)
====================

* Fixed `handle = None does not work for mypy to silence type checkers <https://github.com/django-commons/django-typer/issues/90>`_

v2.1.0 (2024-06-05)
====================

.. warning::

    **Imports from** ``django_typer`` **have been deprecated and will be removed in 3.0!** Imports
    have moved to ``django_typer.management``:

    .. code-block::

        # old way
        from django_typer import TyperCommand, command, group, initialize, Typer

        # new way!
        from django_typer.management import TyperCommand, command, group, initialize, Typer

* Implemented `Only attempt to import rich and typer if settings has not disabled tracebacks. <https://github.com/django-commons/django-typer/issues/88>`_
* Implemented `Move tests into top level dir. <https://github.com/django-commons/django-typer/issues/87>`_
* Implemented `Move core code out of __init__.py into management/__init__.py <https://github.com/django-commons/django-typer/issues/81>`_
* Fixed `Typer(help="") doesnt work. <https://github.com/django-commons/django-typer/issues/78>`_

v2.0.2 (2024-06-03)
====================

* Fixed `class help attribute should be type hinted to allow a lazy translation string. <https://github.com/django-commons/django-typer/issues/85>`_


v2.0.1 (2024-05-31)
====================

* Fixed `Readme images are broken. <https://github.com/django-commons/django-typer/issues/77>`_

v2.0.0 (2024-05-31)
====================

This major version release, includes an extensive internal refactor, numerous bug fixes and the
addition of a plugin-based extension pattern.

* Fixed `Stack trace produced when attempted to tab-complete a non-existent management command. <https://github.com/django-commons/django-typer/issues/75>`_
* Fixed `Overriding handle() in inherited commands results in multiple commands. <https://github.com/django-commons/django-typer/issues/74>`_
* Implemented `Support subgroup name overloads. <https://github.com/django-commons/django-typer/issues/70>`_
* Fixed `Helps from class docstrings and TyperCommand class parameters are not inherited. <https://github.com/django-commons/django-typer/issues/69>`_
* Implemented `Allow callback and initialize to be aliases of each other. <https://github.com/django-commons/django-typer/issues/66>`_
* Implemented `Shell completion for --pythonpath <https://github.com/django-commons/django-typer/issues/65>`_
* Implemented `Shell completion for --settings <https://github.com/django-commons/django-typer/issues/64>`_
* Fixed `An intelligible exception should be thrown when a command is invoked that has no implementation. <https://github.com/django-commons/django-typer/issues/63>`_
* Implemented `TyperCommand class docstring should be used as the help as a last resort. <https://github.com/django-commons/django-typer/issues/62>`_
* Implemented `Adapter pattern that allows commands and groups to be added without extension by apps further up the app stack. <https://github.com/django-commons/django-typer/issues/61>`_
* Fixed `ModelObjectParser should use a metavar appropriate to the field type. <https://github.com/django-commons/django-typer/issues/60>`_
* Implemented `Switch to ruff for linting and formatting. <https://github.com/django-commons/django-typer/issues/56>`_
* Implemented `Add a wrapper for typer's echo/secho <https://github.com/django-commons/django-typer/issues/55>`_
* Implemented `Support a native typer-like interface. <https://github.com/django-commons/django-typer/issues/53>`_
* Fixed `@group type hint does not carry over the parameter spec of the wrapped function <https://github.com/django-commons/django-typer/issues/38>`_
* Implemented `Better test organization. <https://github.com/django-commons/django-typer/issues/34>`_
* Implemented `Add completer/parser for GenericIPAddressField. <https://github.com/django-commons/django-typer/issues/12>`_


v1.1.2 (2024-04-22)
====================

* Fixed `Overridden common Django arguments fail to pass through when passed through call_command <https://github.com/django-commons/django-typer/issues/54>`_

v1.1.1 (2024-04-11)
====================

* Implemented `Fix pyright type checking and add to CI <https://github.com/django-commons/django-typer/issues/51>`_
* Implemented `Convert CONTRIBUTING.rst to markdown <https://github.com/django-commons/django-typer/issues/50>`_

v1.1.0 (2024-04-03)
====================

* Implemented `Convert readme to markdown. <https://github.com/django-commons/django-typer/issues/48>`_
* Fixed `typer 0.12.0 breaks django_typer 1.0.9 <https://github.com/django-commons/django-typer/issues/47>`_


v1.0.9 (yanked)
===============

* Fixed `Support typer 0.12.0 <https://github.com/django-commons/django-typer/issues/46>`_

v1.0.8 (2024-03-26)
====================

* Fixed `Support typer 0.10 and 0.11 <https://github.com/django-commons/django-typer/issues/45>`_

v1.0.7 (2024-03-17)
====================

* Fixed `Helps throw an exception when invoked from an absolute path that is not relative to the getcwd() <https://github.com/django-commons/django-typer/issues/44>`_

v1.0.6 (2024-03-14)
====================

* Fixed `prompt options on groups still prompt when given as named parameters on call_command <https://github.com/django-commons/django-typer/issues/43>`_


v1.0.5 (2024-03-14)
====================

* Fixed `Options with prompt=True are prompted twice <https://github.com/django-commons/django-typer/issues/42>`_


v1.0.4 (2024-03-13)
====================

* Fixed `Help sometimes shows full script path in Usage: when it shouldnt. <https://github.com/django-commons/django-typer/issues/40>`_
* Fixed `METAVAR when ModelObjectParser supplied should default to model name <https://github.com/django-commons/django-typer/issues/39>`_

v1.0.3 (2024-03-08)
====================

* Fixed `Incomplete typing info for @command decorator <https://github.com/django-commons/django-typer/issues/33>`_

v1.0.2 (2024-03-05)
====================

* Fixed `name property on TyperCommand is too generic and should be private. <https://github.com/django-commons/django-typer/issues/37>`_
* Fixed `When usage errors are thrown the help output should be that of the subcommand invoked not the parent group. <https://github.com/django-commons/django-typer/issues/36>`_
* Fixed `typer installs its own system exception hook when commands are run and this may step on the installed rich hook <https://github.com/django-commons/django-typer/issues/35>`_
* Fixed `Add py.typed stub <https://github.com/django-commons/django-typer/issues/31>`_
* Fixed `Run type checking with django-stubs installed. <https://github.com/django-commons/django-typer/issues/30>`_
* Fixed `Add pyright to linting and resolve any pyright errors. <https://github.com/django-commons/django-typer/issues/29>`_
* Fixed `Missing subcommand produces stack trace without --traceback. <https://github.com/django-commons/django-typer/issues/27>`_
* Fixed `Allow handle() to be an initializer. <https://github.com/django-commons/django-typer/issues/24>`_

v1.0.1 (2024-02-29)
====================

* Fixed `shell_completion broken for click < 8.1 <https://github.com/django-commons/django-typer/issues/21>`_

v1.0.0 (2024-02-26)
====================

* Initial production/stable release.

v0.6.1b (2024-02-24)
=====================

* Incremental beta release - this is also the second release candidate for version 1.
* Peg typer version to 0.9.x

v0.6.0b (2024-02-23)
=====================

* Incremental beta release - this is also the first release candidate for version 1.


v0.5.0b (2024-01-31)
=====================

* Incremental Beta Release

v0.4.0b (2024-01-08)
=====================

* Incremental Beta Release

v0.3.0b (2024-01-06)
=====================

* Incremental Beta Release

v0.2.0b (2024-01-04)
=====================

* Incremental Beta Release


v0.1.0b (2023-12-05)
=====================

* Initial Release (Beta)
