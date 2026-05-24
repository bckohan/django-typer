.. include:: ./refs.rst

.. _shellcompletions:

=========================
Tutorial: Tab-Completions
=========================

.. only:: html

    .. image:: /_static/img/closepoll_example.gif
        :align: center

.. only:: latex

    .. image:: /_static/img/closepoll_example.png
        :align: center

|

Shell completions are helpful suggestions displayed when you press the
``<TAB>`` key while typing a command in a shell.  They are especially useful
when you are not sure about the exact name of a command, its options, its arguments
or the potential values of either.

Django has some support for bash completions, but it is not enabled by default and
left to the user to install.

django-typer_ augments the upstream functionality of Typer_ and
:doc:`Click <click:shell-completion>` to provide both an easy way to define shell completions for
your custom CLI options and arguments as well as a way to install them in your shell.

.. tip::

    django-typer_ supports shell completion on bash_, zsh_, fish_ and
    powershell_.


Installation
============

.. tip::

    TLDR; To install completions for your Django project run:

    ``./manage.py shellcompletion install``

Each shell has its own mechanism for enabling completions complicated
by how different shells are installed and configured on different platforms. All shells
have the same basic process. Completion logic needs to be registered with the shell that will be
invoked when tabs are pressed for a specific command or script. To install tab completions
for django commands we need to register our completion logic for Django manage script with
the shell. This process has two phases:

1. Ensure that your shell is configured to support completions.
2. Use the :django-admin:`shellcompletion` command to install the completion hook for your Django
   manage script. This usually entails adding a specifically named script to a certain directory or
   adding lines to an existing profile. The :django-admin:`shellcompletion` command will handle this
   for you.


The goal of this guide is not to be an exhaustive list of how to enable completions for each
supported shell on all possible platforms, but rather to provide general guidance on how to
enable completions for the most common platforms and environments. If you encounter issues
or have solutions, please `report them on our discussions page <https://github.com/django-commons/django-typer/discussions>`_

.. tabs::

    .. tab:: Windows

        powershell_ is now bundled with most modern versions of Windows. There should be no
        additional installation steps necessary, but please refer to the Windows documentation if
        powershell_ is not present on your system. Earlier (<6) versions of powershell_ and later
        versions (>=6) may be present on your system. We support both versions, but you should be
        sure that you are in the correct shell when you run the install routine. The executable for
        earlier versions is ``powershell`` and later versions is ``pwsh``.

        You may install more recent versions
        `using winget <https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-windows?view=powershell-7.4>`_

        .. tip::

            ``cmd``, the default shell on Windows, does not support completions. Python scripts are
            sometimes bundled for execution on Windows in a way that results in runs through the
            default shell in a subprocess. django-typer_ will attempt to resolve the parent shell,
            but you may need to specify ``--shell`` explicitly when installing completions.

    .. tab:: Linux

        bash_ is the default shell on most Linux distributions. Completions should be enabled out
        of the box. Of the supported shells, bash_ completions are the least robust. Menu selection
        and help strings are not supported.

        If completions are an important to you, we suggest installing either Zsh_ or fish_ which
        are also supported and easily installable on most Linux distributions. You may also extend
        bash_ using `ble.sh <https://github.com/akinomyoga/ble.sh>`_ to enable zsh_ style menu
        selection.

    .. tab:: Mac OSX

        zsh_ is currently the default shell on OSX. Unfortunately completions are not supported
        out of the box. We recommend using
        `homebrew to install the zsh-completions package <https://formulae.brew.sh/formula/zsh-completions>`_.

        After installing the package you will need to add some configuration to your ``.zshrc``
        file. Our zsh_ installer will add something similar to the following to your ``.zshrc``
        file if necessary.

        .. code-block:: bash

            if type brew &>/dev/null; then
                fpath=(~/.zfunc $(brew --prefix)/share/zsh-completions $fpath)
            else
                fpath=(~/.zfunc $fpath)
            fi

            autoload -Uz compinit
            compinit

            zstyle ':completion:*' menu select

        .. tip::

            powershell_, bash_ and fish_ shells are also supported on OSX!

Install the Completion Hook
---------------------------

django-typer_ comes with a management command called :django-admin:`shellcompletion`. To install
completions for your Django_ project simply run the install command:

.. code-block:: bash

    ./manage.py shellcompletion install

**The install command will list the precise edits to dotfiles and shell configuration files that it
will make and ask for permission before proceeding. To skip the prompt use** ``--no-prompt``.

.. note::

    The manage script may be named differently in your project - this is fine. The only requirement
    is that you invoke the shellcompletion command in the same way you would invoke any commands you
    would like tab completions to work for.

The installation script should be able to automatically detect your shell and install the
appropriate scripts. If it is unable to do so you may force it to install for a specific shell by
passing the shell name as an argument. Refer to the :django-admin:`shellcompletion` for details.

**After installation you will need to restart your shell or source the appropriate rc file.**

.. warning::

    In production environments it is recommended that your management script be installed as a
    command on your system path. This will produce the most reliable installation. On powershell_
    and fish_ the management script must be available on your path as script installations are
    not supported in these shells.


Enabling Completions in Development Environments
------------------------------------------------

Most shells work best when the manage script is installed as an executable on the system path. This
is not always the case, especially in development environments. In these scenarios completion
installation *may still work*, but you may need to always invoke the script from the same path.


.. _completion_fallbacks:

Integrating with Other CLI Completion Libraries
-----------------------------------------------

When tab completion is requested for a command that is not a :class:`~django_typer.management.TyperCommand`,
django-typer_ will delegate that request to Django's
`autocomplete function <https://github.com/django/django/blob/main/django/core/management/__init__.py#L278>`_
as a fallback. This means that using django-typer_ to install completion scripts will enable
completions for Django BaseCommands in all supported shells.

However, if you are using a separate package to define custom tab completions for your commands
you may use the --fallback parameter to supply a separate fallback hook that will invoke the
appropriate completion function for your commands. If there are other popular completion libraries
please consider `letting us know or submitting a PR
<https://github.com/django-commons/django-typer/issues>`_ to support these libraries as a fallback out of
the box.


*The long-term solution here should be that Django itself manages completion installation and
provides hooks for implementing libraries to provide completions for their own commands.*


.. _define-shellcompletions:

Defining Custom Completions
===========================

To define custom completion logic for your arguments_ and options_ pass the ``shell_completion``
parameter in your type hint annotations. django-typer_ comes with a
:ref:`few provided completers <completers>` for common Django_ types. One of the provided completers
completes Django_ app labels and names. We might build a similar completer that only works for
Django_ app labels like this:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../examples/completers/management/commands/app_labels.py
            :language: python
            :linenos:
            :caption: examples/completers/management/commands/app_labels.py

    .. tab:: Typer-style

        .. literalinclude:: ../../examples/completers/management/commands/app_labels_typer.py
            :language: python
            :linenos:
            :caption: examples/completers/management/commands/app_labels_typer.py

.. tip::

    See the :class:`~django_typer.completers.model.ModelObjectCompleter` for a completer that works
    for many Django_ model field types.


.. _debug-shellcompletions:

Debugging Tab Completers
========================

Debugging tab completion code can be tricky because when invoked in situ in the shell the completer
code is run as a subprocess and it's output is captured by the shell. This means you can't set a
breakpoint and enter into the debugger easily.

To help with this django-typer_ provides a debug mode that will enter into the tab-completion logic
flow. Use the :class:`shellcompletion <django_typer.management.commands.shellcompletion.Command>`
:func:`~django_typer.management.commands.shellcompletion.Command.complete` command, to pass the
command line string that you would like to debug. For example:

.. code-block:: bash

    ./manage.py shellcompletion complete "mycommand --"


Provided Completers
===================


Django Apps
-----------

* completer: :func:`~django_typer.completers.apps.app_labels`
* parser: :func:`~django_typer.parsers.apps.app_config`

.. code-block:: python

    import typing as t
    import typer
    from django.apps import AppConfig
    from django_typer.completers.apps import app_labels
    from django_typer.parsers.apps import app_config

    ...

    def handle(
        self,
        django_app: t.Annotated[
            AppConfig,
            typer.Argument(
                parser=app_config,
                shell_complete=app_labels
            )
        ]
    )

Constant Strings
----------------
* completer: :func:`~django_typer.completers.these_strings`

.. code-block:: python

    import typing as t
    import typer
    from enum import StrEnum
    from django_typer.completers import these_strings

    ...

    class Shells(StrEnum):

        zsh = 'zsh',
        bash = 'bash'
        fish = 'fish',
        powershell = 'pswh'

    def handle(
        self,
        shell: t.Annotated[
            Shells,
            typer.Argument(
                shell_complete=these_strings(list(Shells))
            )
        ]
    )

Database Aliases
----------------

* completer: :func:`~django_typer.completers.db.databases`

.. code-block:: python

    import typing as t
    import typer
    from django_typer.completers.db import databases

    ...

    def handle(
        self,
        database: t.Annotated[
            str,
            typer.Argument(shell_complete=databases())
        ]
    )

Management Commands
-------------------

* completer: :func:`~django_typer.completers.cmd.commands`

.. code-block:: python

    import typing as t
    import typer
    from django_typer.completers.cmd import commands

    ...

    def handle(
        self,
        command: t.Annotated[
            str,
            typer.Argument(shell_complete=commands())
        ]
    )


Paths (Files & Directories)
---------------------------

* completer: :func:`~django_typer.completers.path.paths`

.. code-block:: python

    import typing as t
    import typer
    from pathlib import Path
    from django_typer.completers.path import paths

    ...

    def handle(
        self,
        path: t.Annotated[
            Path,
            typer.Argument(shell_complete=paths)
        ]
    )

Directories
-----------

* completer: :func:`~django_typer.completers.path.directories`

.. code-block:: python

    import typing as t
    import typer
    from pathlib import Path
    from django_typer.completers.path import directories

    ...

    def handle(
        self,
        directory: t.Annotated[
            Path,
            typer.Argument(shell_complete=directories)
        ]
    )

Django Static Files & media
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* static completer: :func:`~django_typer.completers.path.static_paths`
* media completer: :func:`~django_typer.completers.path.media_paths`

Complete paths to static files or media files.

.. code-block:: python

    import typing as t
    import typer
    from pathlib import Path
    from django_typer.completers.path import media_paths

    ...

    def handle(
        self,
        directory: t.Annotated[
            Path,
            typer.Argument(shell_complete=media_paths)
        ]
    )


Import Paths
------------

Complete python.import.paths - uses sys.path. This completer is used for --settings

* completer: :func:`~django_typer.completers.path.import_paths`

.. code-block:: python

    import typing as t
    import typer
    from django_typer.completers.path import import_paths

    ...

    def handle(
        self,
        import_path: t.Annotated[
            str,
            typer.Argument(shell_complete=import_paths)
        ]
    )

Model Objects
-------------

* completer: :class:`~django_typer.completers.model.ModelObjectCompleter`
* parser: :class:`~django_typer.parsers.model.ModelObjectParser`
* convenience: :func:`~django_typer.utils.model_parser_completer`

This completer/parser pairing provides the ability to fetch a model object from one of its fields.
Most field types are supported. Additionally any other field can be set as the help text that some
shells support. Refer to the reference documentation and the
:ref:`polls tutorial <building_commands>` for more information.

.. warning::

    If the model table is large you'll want to make sure the completable field is indexed. When
    your users hit tab, they'll have to wait to the matching query to complete. The queries
    have been optimized to take advantage of indexes for each supported field type.

.. code-block:: python

    import typing as t
    import typer
    from django_typer.utils import model_parser_completer

    ...

    def handle(
        self,
        obj: t.Annotated[
            ModelClass,
            typer.Argument(
                **model_parser_completer(
                    ModelClass,  # may also accept a QuerySet for pre-filtering
                    'field_name',  # the field that should be matched (defaults to id)
                    help_field='other_field'  # optionally provide some additional help text
                )
                help=_("Fetch objects by their field_names.")
            )
        ]
    ):
        ...

QuerySets and Field Values
~~~~~~~~~~~~~~~~~~~~~~~~~~

:class:`~django_typer.parsers.model.ModelObjectParser` can be configured to return queryset
types or the primitive field values instead of a model instance, using the ``return_type``
parameter and the :class:`~django_typer.parsers.model.ReturnType` enumeration:

.. code-block:: python

    from django_typer.management import TyperCommand
    from django_typer.utils import model_parser_completer
    from django_typer.parsers.model import ReturnType
    from django.db.models import QuerySet


    class Command(TyperCommand):
        def handle(
            self,
            query: Annotated[
                QuerySet[ModelClass],
                typer.Argument(
                    **model_parser_completer(
                        ModelClass,
                        lookup_field="field_name",
                        return_type=ReturnType.QUERY_SET,
                    )
                ),
            ],
        ):
            ...


Fields with Choices
~~~~~~~~~~~~~~~~~~~

The above examples using :func:`~django_typer.utils.model_parser_completer` will work for fields
with choices. You may however want to avoid the database lookup given that the choice list is
readily available. To do this you could use :func:`~django_typer.completers.these_strings` in
combination with the :class:`~django_typer.parsers.model.ModelObjectParser`:

.. code-block:: python

    from django_typer.parsers.model import ModelObjectParser, ReturnType

    class Command(TyperCommand):
        def handle(
            self,
            query: Annotated[
                QuerySet[ModelClass],
                typer.Option(
                    parser=ModelObjectParser(
                        ModelClass,
                        "choice_field,
                        return_type=ReturnType.QUERY_SET,
                    ),
                    shell_complete=these_strings(
                        ModelClass.FIELD_CHOICES,
                        allow_duplicates=False,
                    ),
                    help="Fetch objects by their choices for field choice_field.",
                ),
            ] = ModelClass.objects.none(),
        ):
            ...

Completer Chains
----------------

Multiple completers can be chained together in a sequence. All completions can
be returned, or only the first completer that generates matches.

* completer: :func:`~django_typer.completers.chain`

.. code-block:: python

    import typing as t
    import typer
    from django_typer.completers import chain
    from django_typer.completers.path import import_paths
    from django_typer.completers.cmd import commands

    ...

    def handle(
        self,
        command: t.Annotated[
            str,
            typer.Argument(
                # allow commands to be specified by name or import path
                shell_complete=chain(import_paths, commands())
            )
        ]
    )

Settings
--------

A number of completers are provided that complete values involving settings. These include:

* setting: :func:`~django_typer.completers.settings.setting`
* languages: :func:`~django_typer.completers.settings.languages`


Customizing/Adding Shells
==========================

It is possible to customize the shell specific completion scripts or add support for additional
shells. There are two main extension points:

1. Derive a class from
   :class:`~django_typer.shells.DjangoTyperShellCompleter`
   for your shell and register it using
   :func:`~django_typer.shells.register_completion_class`. This class
   will control how suggestions are formatted and returned and how the completion script
   is generated and installed.

   You may also override the classes for the supported shells by registering your own class.
   We recommend using the :ref:`plugins <plugins>` pattern to do this so that your custom
   completers will respect :setting:`INSTALLED_APPS` order.

2. Override the completion script templates for your shell. The completion script templates are
   stored in the ``django_typer/templates``. You may override these templates in your project to
   customize the completion script output
   :doc:`the same way you would an html template <django:howto/overriding-templates>`:

.. list-table::
   :header-rows: 1

   * - Shell
     - Script Template
     - Completer Class
   * - bash_
     - ``shell_complete/bash.sh``
     - :class:`~django_typer.shells.bash.BashComplete`
   * - zsh_
     - ``shell_complete/zsh.sh``
     - :class:`~django_typer.shells.zsh.ZshComplete`
   * - fish_
     - ``shell_complete/fish.fish``
     - :class:`~django_typer.shells.fish.FishComplete`
   * - powershell_
     - ``shell_complete/powershell.ps1``
     - :class:`~django_typer.shells.powershell.PowerShellComplete`,
       :class:`~django_typer.shells.powershell.PwshComplete`
