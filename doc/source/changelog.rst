.. include:: ./refs.rst

==========
Change Log
==========

v4.1.2 (2026-10-01)
===================

* Drop :pypi:`django-tailwind-cli` from the showcase.

v4.1.1 (2026-09-30)
===================

* Add :pypi:`django-systemd` to the showcase.

v4.1.0 (2026-09-05)
===================

* Support Typer 0.27+
* Help output follows Typer 0.27's metavar rendering (e.g. ``<str>`` instead of
  ``TEXT`` and ``{arg}`` instead of ``ARG`` in usage lines)
* Model field parser metavars are lowercase to match Typer's (e.g. ``<int>``, ``<txt>``)

v4.0.0 (2026-09-05)
===================

* Support Typer 0.26.8+
* Added :attr:`~django_typer.management.TyperCommand.atomic` to run a command's whole
  invocation - initializer, chained subcommands and finalizer - in a database transaction.
  Implements `Add a command option that will wrap execute() in a transaction
  <https://github.com/django-commons/django-typer/issues/219>`_. See :ref:`howto:Wrap a Command in a Transaction`.
* Fixed chain mode being switched off when a chained command defines an initializer
* Implemented `ModelObjectParser should have a setting that returns the lookup value if no row
  was found. <https://github.com/django-commons/django-typer/issues/218>`_ - see the
  ``return_lookup_on_miss`` parameter. The return value of ``on_error`` handlers is now
  documented as the parsed value.
* The click command tree Typer builds for a command is now cached per app and only rebuilt
  when commands, groups, callbacks or finalizers are registered, instead of being rebuilt
  several times on every invocation
* Fixed `typer.Exit is swallowed on the execute() path: exit code returned as output and
  process exits 0 <https://github.com/django-commons/django-typer/issues/318>`_
* Fixed `Avoid redundant context construction <https://github.com/django-commons/django-typer/issues/210>`_
* Fixed `FileBinaryRead: file is already closed <https://github.com/django-commons/django-typer/issues/209>`_
* Fixed `Typer app options do not inherit/override correctly
  <https://github.com/django-commons/django-typer/issues/256>`_
* Drop dependency on Click (vendored by Typer). The Click types needed to write completers
  and parsers are re-exported from :mod:`django_typer.completers` (``Context``, ``Parameter``,
  ``CompletionItem``) and :mod:`django_typer.parsers` (``Context``, ``Parameter``, ``ParamType``)
* Drop support for Python 3.10
* Added a :doc:`settings <settings>` reference. ``DT_MANAGE_SCRIPT`` and ``DT_PRINT_RESULT``
  may also be given as environment variables of the same name.
* BREAKING: Values returned from commands are no longer written to stdout by default. Set
  ``print_result = True`` on a command, or ``DT_PRINT_RESULT = True`` in settings, to restore
  the previous behavior.
* Fixed result printing being applied to the wrong stream: with ``print_result`` off the
  returned value was still written when ``stdout=`` was passed to
  :func:`~django.core.management.call_command`, and a command instance reused after a run
  dropped its own output.
* Passing a ``prompt_required=False`` option flag without a value no longer triggers
  the prompt - Typer's vendored Click dropped support for this. Omit the flag to be
  prompted or pass the value explicitly.
* Fixed `Fix documentation PDF build <https://github.com/django-commons/django-typer/issues/228>`_
* Documented `installing shell completion for a just manage script <https://github.com/django-commons/django-typer/issues/190>`_ and other wrapped invocations, see :ref:`shell_completion:Completions for Wrapped Invocations`. Multi-word manage scripts remain unsupported (`#191 <https://github.com/django-commons/django-typer/issues/191>`_).
* Fixed `get_usage_script resolves full path when command is resolvable on path <https://github.com/django-commons/django-typer/issues/310>`_ and added the ``DT_MANAGE_SCRIPT`` setting to override the detected program name.


Migrating from 3.x to 4.x
-------------------------

* Python 3.10 is no longer supported, 4.x requires Python 3.11 or later.

* Typer_ 0.26.8 or later is required and Click_ is no longer a dependency of django-typer_. Typer_
  now vendors Click_, so the ``click`` package may not be installed in your environment and even
  when it is, its classes are not the ones Typer_ uses. If your commands import from ``click``:

  - Import the types used to write completers from :mod:`django_typer.completers`:

    .. code-block:: python

        # 3.x
        from click import Context, Parameter
        from click.shell_completion import CompletionItem

        # 4.x
        from django_typer.completers import CompletionItem, Context, Parameter

  - Import the types used to write parsers from :mod:`django_typer.parsers`:

    .. code-block:: python

        # 3.x
        from click import Context, Parameter, ParamType

        # 4.x
        from django_typer.parsers import Context, Parameter, ParamType

  - Use ``typer.Exit``, ``typer.Abort`` and ``typer.BadParameter`` in place of their ``click``
    counterparts. Raising :exc:`~django.core.management.CommandError` remains the recommended
    way to report errors from a command.

  - Replace calls to ``click.get_current_context()`` with a parameter annotated as
    :class:`~django_typer.management.Context` on the command, group or callback that needs it,
    Typer_ will pass the active context in. :func:`~django_typer.utils.get_current_command`
    continues to provide the running command instance.

  - ``isinstance`` checks against ``click`` classes will no longer match.

  - The ``click_type`` parameter to ``typer.Option`` and ``typer.Argument`` was removed upstream,
    pass the type to ``parser`` instead. Parsers already passed through ``parser`` are unaffected:
    plain callables and ``ParamType`` subclasses, including ones derived from a separately
    installed Click_, continue to work.

* Options declared with ``prompt=True, prompt_required=False`` no longer prompt when the flag is
  passed without a value, doing so is now a usage error. Omit the flag to be prompted or pass
  the value explicitly.

* If you document your commands with the ``typer`` directive from sphinxcontrib-typer_, upgrade
  it to 0.10 or later. Earlier releases drive the real Click_ package and fail against
  Typer_ 0.26+.

* The program name shown in the ``Usage:`` line of command help (and used when installing shell
  completions) is now the bare command name whenever that name resolves on the path, including when
  the script was launched through a shim or wrapper of the same name or through a relative path to
  the same script. Previously the full path was shown in these cases. Set
  ``DT_MANAGE_SCRIPT`` to pin the name if you need a specific value, see
  :ref:`howto:Configure the Manage Script Name`.

* :exc:`typer.Exit`, :exc:`typer.Abort` and :exc:`KeyboardInterrupt` leaving a command now
  follow one policy. From the command line the process exits with the status (``Abort``
  prints ``Aborted!`` and exits 1, an interrupt exits 130) and nothing else is printed.
  From :func:`~django.core.management.call_command`, a non-zero ``Exit`` and an ``Abort`` raise
  :exc:`~django.core.management.CommandError` with ``returncode`` set, and ``Exit(0)``
  returns ``None``. Command functions called directly from Python are plain calls and
  whatever they raise propagates unchanged. Previously ``Exit`` was returned (and printed)
  as the command's output when executed and ended the process when the command object was
  called directly. See :ref:`howto:Exit Codes, Errors and Aborts`.

* Return values are no longer printed. In 3.x a truthy value returned from a command was
  written to stdout, mirroring :class:`~django.core.management.BaseCommand`. In 4.x nothing
  is printed unless the command sets ``print_result = True`` or the project sets
  ``DT_PRINT_RESULT = True`` - see :ref:`howto:Toggle on/off result printing`. If a command's
  return value doubled as its output, set one of those or write the output explicitly.

* Starting with 4.1 (Typer_ 0.27+), help output renders type metavars in lowercase angle
  brackets (``<str>``, ``<int>``, ``<path>``) instead of ``TEXT``, ``INTEGER`` and ``PATH``,
  and usage lines show required arguments as ``{arg}`` and optional arguments as ``[arg]``
  instead of ``ARG``. The provided model field parsers follow suit (``<int>``, ``<txt>``, ...).
  Update any tests that assert on help text.

* No changes are required for chained groups (``chain=True``), finalizers, the provided
  completers and parsers, custom shell completer classes registered with
  :func:`~django_typer.shells.register_completion_class` or the shellcompletion command. These
  were reimplemented or adapted internally and behave as before.


v3.9.0 (2026-09-02)
===================

* Support Click 8.5.x


v3.8.0 (2026-08-04)
===================

* Fixed `Model field completers can return completions that don't extend the typed text; integer completer hangs on "0" <https://github.com/django-commons/django-typer/issues/304>`_
* Fixed `Get fish completion tests working <https://github.com/django-commons/django-typer/issues/180>`_
    - Fish shellcompletion is now better supported.
* Drop support for Django 4.2
* Support Python 3.15

v3.7.4 (2026-07-31)
===================

* Support Django 6.1

v3.7.3 (2026-05-23)
===================

* Support `Click 8.4.x <https://github.com/pallets/click/releases/tag/8.4.0>`_
* Fixed `Completions longer than the terminal width are chopped with \n by rich console formatter
  <https://github.com/django-commons/django-typer/issues/292>`_

v3.7.2 (2026-04-26)
===================

* Support `Typer 0.25.x <https://github.com/fastapi/typer/releases/tag/0.25.0>`_

v3.7.1 (2026-03-31)
===================

* Update installation instructions to reflect `rich <https://github.com/textualize/rich>`_ `no
  longer being an optional dependency <https://github.com/fastapi/typer/pull/1522>`_. You can
  `disable rich formatting <https://typer.tiangolo.com/?h=typer_use_rich#license>`_ by setting
  ``TYPER_USE_RICH=False``

v3.7.0 (2026-03-19)
===================

* Results returned from groups are now included in the result sets passed to finalize().

v3.6.6 (2026-03-18)
===================

* Duraton parser now supports Y, M, and W.

v3.6.5 (2026-03-16)
===================

* Switch from `pre-commit <https://pre-commit.com/>`_ to `prek <https://prek.j178.dev/>`_.
* Run `Bandit <https://bandit.readthedocs.io/en/latest/>`_ in CI.

v3.6.4 (2026-03-02)
===================

* Add typed classifier/badge.

v3.6.3 (2026-02-25)
===================

* Add badges to docs.

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

* The function signature for :ref:`shellcompletion fallbacks
  <shell_completion:Integrating with Other CLI Completion Libraries>` has changed. The fallback
  signature is now:

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
