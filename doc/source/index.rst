.. include:: ./refs.rst
.. role:: big

============
Django Typer
============

|MIT license| |Ruff| |PyPI version fury.io| |PyPI pyversions| |PyPi djversions| |PyPI status|
|Documentation Status| |Code Cov| |Test Status| |Lint Status|


|Django Packages| |OpenSSF Scorecard| |OpenSSF Best Practices|

.. |MIT license| image:: https://img.shields.io/badge/License-MIT-blue.svg
   :target: https://lbesson.mit-license.org/

.. |Ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://docs.astral.sh/ruff

.. |PyPI version fury.io| image:: https://badge.fury.io/py/django-typer.svg
   :target: https://pypi.python.org/pypi/django-typer/

.. |PyPI pyversions| image:: https://img.shields.io/pypi/pyversions/django-typer.svg
   :target: https://pypi.python.org/pypi/django-typer/

.. |PyPI djversions| image:: https://img.shields.io/pypi/djversions/django-typer.svg
   :target: https://pypi.org/project/django-typer/

.. |PyPI status| image:: https://img.shields.io/pypi/status/django-typer.svg
   :target: https://pypi.python.org/pypi/django-typer

.. |Documentation Status| image:: https://readthedocs.org/projects/django-typer/badge/?version=latest
   :target: http://django-typer.readthedocs.io/?badge=latest/

.. |Code Cov| image:: https://codecov.io/gh/django-commons/django-typer/branch/main/graph/badge.svg?token=0IZOKN2DYL
   :target: https://codecov.io/gh/django-commons/django-typer

.. |Test Status| image:: https://github.com/django-commons/django-typer/actions/workflows/test.yml/badge.svg?branch=main
   :target: https://github.com/django-commons/django-typer/actions/workflows/test.yml

.. |Lint Status| image:: https://github.com/django-commons/django-typer/actions/workflows/lint.yml/badge.svg
   :target: https://github.com/django-commons/django-typer/actions/workflows/lint.yml

.. |Django Packages| image:: https://img.shields.io/badge/Published%20on-Django%20Packages-0c3c26
   :target: https://djangopackages.org/packages/p/django-typer/

.. |OpenSSF Scorecard| image:: https://api.securityscorecards.dev/projects/github.com/django-commons/django-typer/badge
   :target: https://securityscorecards.dev/viewer/?uri=github.com/django-commons/django-typer

.. |OpenSSF Best Practices| image:: https://www.bestpractices.dev/projects/12046/badge
   :target: https://www.bestpractices.dev/projects/12046


Use static typing to define the CLI for your Django_ management commands with Typer_. Optionally
use the provided :class:`~django_typer.management.TyperCommand` class that inherits from
:class:`~django.core.management.BaseCommand`. This class maps the Typer_ interface onto a class
based interface that Django developers will be familiar with. All of the
:class:`~django.core.management.BaseCommand` functionality is inherited, so that
:class:`~django_typer.management.TyperCommand` can be a drop in replacement.

**django-typer makes it easy to:**

    * Define your command CLI interface in a clear, DRY and safe way using type hints
    * Create subcommands and hierarchical groups of commands.
    * Use the full power of Typer_'s parameter types to validate and parse command line inputs.
    * Create beautiful and information dense help outputs.
    * Configure the rendering of exception stack traces using :doc:`rich <rich:index>`.
    * :ref:`Install shell tab-completion support <shellcompletions>` for bash_, zsh_, fish_ and
      powershell_.
    * :ref:`Create custom and portable shell tab-completions for your CLI parameters.
      <define-shellcompletions>`
    * Port existing commands (:class:`~django_typer.management.TyperCommand` is interface compatible
      with :class:`~django.core.management.BaseCommand`).
    * Use either a Django-style class-based interface or the Typer-style interface to define
      commands.
    * Add plugins to upstream commands.

.. warning::

    **Imports from** ``django_typer`` **have been deprecated and will be removed in 3.0!** Imports
    have moved to ``django_typer.management``:

    .. code-block::

        # old way
        from django_typer import TyperCommand, command, group, initialize, Typer

        # new way!
        from django_typer.management import TyperCommand, command, group, initialize, Typer

:big:`Installation`

1. Clone django-typer from GitHub_ or install a release off PyPI_ :

    .. code:: bash

        pip install django-typer

    :doc:`rich <rich:index>` is a powerful library for rich text and beautiful formatting in the terminal.
    It is not required, but highly recommended for the best experience:

    .. code:: bash

        pip install "django-typer[rich]"


2. Optionally add ``django_typer`` to your :setting:`INSTALLED_APPS` setting:

    .. code:: python

        INSTALLED_APPS = [
            ...
            'django_typer',
        ]

   *You only need to install django_typer as an app if you want to use the shellcompletion command
   to enable tab-completion or if you would like django-typer to install*
   :ref:`rich traceback rendering <configure-rich-exception-tracebacks>` *for you - which it does
   by default if rich is also installed.*

.. note::

    This documentation shows all examples using both the function oriented Typer-style interface
    and the class based Django-style interface in separate tabs. Each interface is functionally
    equivalent so the choice of which to use is a matter of preference and familiarity. All
    django-typer commands are instances of :class:`~django_typer.management.TyperCommand`,
    including commands defined in the Typer-style interface. **This means you may always specify a
    self argument to receive the instance of the command in your functions.**

:big:`Basic Example`

:class:`~django_typer.management.TyperCommand` is a drop in extension to
:class:`~django.core.management.BaseCommand`. All of the documented features of
:class:`~django.core.management.BaseCommand` work the same way! Or, you may also use an interface
identical to Typer_'s. Simply import Typer_ from django_typer instead of typer.

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/basic/management/commands/basic.py
            :language: python
            :caption: management/commands/basic.py
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/typer/management/commands/basic.py
            :language: python
            :caption: management/commands/basic.py
            :linenos:


.. typer:: tests.apps.examples.basic.management.commands.basic.Command:typer_app
    :prog: ./manage.py basic
    :width: 80
    :convert-png: latex
    :theme: dark

|

:big:`Multiple Subcommands Example`

Commands with multiple subcommands can be defined:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/basic/management/commands/multi.py
            :language: python
            :caption: management/commands/multi.py
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/typer/management/commands/multi.py
            :language: python
            :caption: management/commands/multi.py
            :linenos:


.. typer:: tests.apps.examples.basic.management.commands.multi.Command:typer_app
    :prog: ./manage.py multi
    :width: 80
    :show-nested:
    :convert-png: latex
    :theme: dark

|

:big:`Grouping and Hierarchies Example`

Or more complex groups and subcommand hierarchies can be defined. For example this command
defines a group of commands called math, with subcommands divide and multiply. The group
has a common initializer that optionally sets a float precision value. We would invoke this
command like so:

.. code:: bash

    ./manage.py hierarchy math --precision 5 divide 10 2.1
    4.76190
    ./manage.py hierarchy math multiply 10 2
    20.00

Any number of groups and subcommands and subgroups of other groups can be defined allowing for
arbitrarily complex command hierarchies. The Typer-style interface builds a
:class:`~django_typer.management.TyperCommand` class for us **that allows you to optionally accept
the self argument in your commands.**

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/basic/management/commands/hierarchy.py
            :language: python
            :caption: management/commands/hierarchy.py
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/typer/management/commands/hierarchy.py
            :language: python
            :caption: management/commands/hierarchy.py
            :linenos:

.. typer:: tests.apps.examples.basic.management.commands.hierarchy.Command:typer_app
    :prog: ./manage.py hierarchy
    :width: 80
    :show-nested:
    :convert-png: latex
    :theme: dark

|

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorial
   extensions
   shell_completion
   howto
   performance
   showcase
   reference/index
   changelog
