.. include:: ./refs.rst

.. _settings:

========
Settings
========

django-typer_ reads a small number of settings from your Django_ settings module. Two of them can
also be given as environment variables of the same name, which is convenient for deployments where
the settings module is shared but a particular invocation needs a different value. The settings
module always wins over the environment.

``DT_MANAGE_SCRIPT``
--------------------
.. setting:: DT_MANAGE_SCRIPT

* **Default:** not set
* **Environment variable:**  ``DT_MANAGE_SCRIPT``

The program name to show in the ``Usage:`` line of command help and to install shell completions
for. When not set the name is detected from the script that was invoked, which is right for
``manage.py`` and for scripts installed on the path. Set it when the detected name is not the one
users type, for example when the script runs through a wrapper such as a just_ recipe or
``poetry run``:

.. code-block:: python
    :caption: settings.py

    DT_MANAGE_SCRIPT = "mycli"

The value is used verbatim. See :ref:`howto:Configure the Manage Script Name` and
:ref:`shell_completion:Completions for Wrapped Invocations`.

``DT_PRINT_RESULT``
-------------------
.. setting:: DT_PRINT_RESULT

* **Default:** ``False``
* **Environment variable:** ``DT_PRINT_RESULT`` (``1``, ``true``, ``yes``
  or ``on`` to enable, case insensitive)

Whether a truthy value returned from a command is written to stdout, as
:class:`~django.core.management.BaseCommand` does. django-typer_ leaves this off: return values
are for callers and output is whatever the command prints. Set it to ``True`` to restore the
Django_ behavior project wide. A command's own ``print_result`` class field, when set, takes
precedence over this setting.

.. code-block:: python
    :caption: settings.py

    DT_PRINT_RESULT = True

See :ref:`howto:Toggle on/off result printing` and :ref:`howto:Exit Codes, Errors and Aborts`.

``DT_RICH_TRACEBACK_CONFIG``
----------------------------
.. setting:: DT_RICH_TRACEBACK_CONFIG

**Default:** ``{"show_locals": False}``

Configures the :doc:`rich <rich:index>` traceback hook django-typer_ installs when rich is
available. The value is a dictionary of keyword arguments for :func:`rich.traceback.install`,
for example ``show_locals``, ``width`` or ``suppress``, plus one django-typer_ specific key:

- ``no_install`` - when ``True`` the hook is not installed, but the rest of the configuration
  still applies to Typer_'s own exception rendering. Use this if your project installs rich
  tracebacks itself.

``True`` selects the defaults. ``False`` or ``None`` switches rich tracebacks off entirely, and
tracebacks are rendered the way Django_ renders them.

.. code-block:: python
    :caption: settings.py

    DT_RICH_TRACEBACK_CONFIG = {"show_locals": True, "width": 120}

The ``--show-locals`` and ``--hide-locals`` command line options override ``show_locals`` for a
single invocation. See :ref:`configure-rich-exception-tracebacks`.
