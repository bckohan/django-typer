.. include:: ./refs.rst

.. _building_commands:

===========================
Tutorial: Building Commands
===========================

Using the :class:`~django_typer.management.TyperCommand` class is very similar to using the
:class:`~django.core.management.BaseCommand` class. The main difference is that we use Typer_'s
decorators, classes and type annotations to define the command's command line interface instead of
:mod:`argparse` as :class:`~django.core.management.BaseCommand` expects.

Upstream Libraries
------------------

.. only:: html

    .. image:: /_static/img/django_typer_upstream.svg
        :align: right

.. only:: latex

    .. image:: /_static/img/django_typer_upstream.pdf
        :align: right

django-typer_ merges the Django_ :class:`~django.core.management.BaseCommand` interface with the
Typer_ interface and Typer_ itself is built on top of :doc:`click <click:quickstart>`. This means
when using django-typer_ you will encounter interfaces and concepts from *all three* of these
upstream libraries:

* :class:`~django.core.management.BaseCommand`

    Django_ has a good tutorial for understanding how commands are organized and built in Django_.
    If you are unfamiliar with using :class:`~django.core.management.BaseCommand` please first work
    through the :mod:`polls Tutorial in the Django documentation <django.core.management>`.

* Typer_

    This tutorial can be completed without working through the `Typer tutorials
    <https://typer.tiangolo.com/tutorial/>`_, but familiarizing yourself with Typer_ will make this
    easier and will also be helpful when you want to define CLIs outside of Django_! We use the
    Typer_ interface to define Arguments_ and Options_ so please refer to the Typer_ documentation
    for any questions about how to define these.

* :doc:`click <click:quickstart>`

    The :doc:`click <click:quickstart>` interfaces and concepts are relatively hidden by Typer_, but
    occasionally you may need to refer to the :doc:`click <click:quickstart>` documentation when you
    want to implement more complex behaviors like passing
    :class:`context parameters <click.Context>`. It is not necessary to familiarize yourself with
    :doc:`click <click:quickstart>` to use django-typer_, but you should know that it exists and is
    the engine behind much of this functionality.


Install django-typer_
---------------------

1. Install the latest release off PyPI_ :

    .. code:: bash

        pip install "django-typer"


2. Add ``django_typer`` to your :setting:`INSTALLED_APPS` setting:

    .. code:: python

        INSTALLED_APPS = [
            ...
            'django_typer',
        ]

    .. note::

        Adding django_typer to :setting:`INSTALLED_APPS`` is not strictly necessary if you do not
        wish to use shell tab completions or configure
        :doc:`rich traceback rendering <rich:traceback>`. Refer to the
        :ref:`how-to <configure-rich-exception-tracebacks>` if you would like to disable it.

Convert the closepoll command to a :class:`~django_typer.management.TyperCommand`
---------------------------------------------------------------------------------

Recall our closepoll command from the
:mod:`polls Tutorial in the Django documentation <django.core.management>` looks like this:

.. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_django.py
    :language: python
    :linenos:
    :replace:
        tests.apps.examples.polls : polls

Inherit from :class:`~django_typer.management.TyperCommand`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We first need to change the inheritance to :class:`~django_typer.management.TyperCommand` and then
move the argument and option definitions from add_arguments into the method signature of handle. A
minimal conversion may look like this:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_t1.py
            :language: python
            :linenos:
            :replace:
                tests.apps.examples.polls.models : polls.models

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_t1_typer.py
            :language: python
            :linenos:
            :replace:
                tests.apps.examples.polls.models : polls.models

You'll note that we've removed add_arguments entirely and specified the arguments and options as
parameters to the handle method. django-typer_ will interpret the parameters on the handle() method
as the command line interface for the command. If we have :doc:`rich <rich:index>` installed the
help for our new closepoll command will look like this:


.. typer:: tests.apps.examples.polls.management.commands.closepoll_t1.Command:typer_app
    :prog: manage.py closepoll
    :width: 80
    :show-nested:
    :convert-png: latex
    :theme: dark

|

.. note::

    :class:`~django_typer.management.TyperCommand` adds the standard set of default options to the
    command line interface, with the exception of verbosity.


Add Helps with Type annotations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Typer_ allows us to use `Annotated types
<https://docs.python.org/3/library/typing.html#typing.Annotated>`_ to add additional controls to how
the command line interface behaves. The most common use case for this is to add help text to the
command line interface. We will annotate our parameter type hints with one of two Typer_ parameter
types, either Argument or Option. Arguments_ are positional parameters and Options_ are named
parameters (i.e. `--delete`). In our polls example, the poll_ids are arguments and the delete flag
is an option. Here is what that would look like:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_t2.py
            :language: python
            :lines: 11-23
            :replace:
                tests.apps.examples.polls.models : polls.models

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_t2_typer.py
            :language: python
            :lines: 13-23
            :replace:
                tests.apps.examples.polls.models : polls.models

See that our help text now shows up in the command line interface. Also note, that
:doc:`lazy translations <django:topics/i18n/translation>` work for the help strings. Typer_ also
allows us to specify our help text in the docstrings of the command function or class, in this case
either Command or :meth:`~django.core.management.BaseCommand.handle` - but docstrings are not
available to the translation system. If translation is not necessary and your help text is extensive
or contains markup the docstring may be the more appropriate place to put it.

.. typer:: tests.apps.examples.polls.management.commands.closepoll_t2.Command:typer_app
    :prog: manage.py closepoll
    :width: 80
    :show-nested:
    :convert-png: latex
    :theme: dark

|

Defining custom and reusable parameter types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We may have other commands that need to operate on Poll objects from given poll ids. We could
duplicate our for loop that loads Poll objects from ids, but that wouldn't be very DRY_. Instead,
Typer_ allows us to define custom parsers for arbitrary parameter types. Lets see what that would
look like if we used the Poll class as our type hint:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_t3.py
            :language: python
            :lines: 11-52

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_t3_typer.py
            :language: python
            :lines: 11-54

.. typer:: tests.apps.examples.polls.management.commands.closepoll_t3.Command:typer_app
    :prog: manage.py closepoll
    :width: 80
    :show-nested:
    :convert-png: latex
    :theme: dark

|

django-typer_ offers some built-in :mod:`~django_typer.parsers` that can be used for
common Django_ types. For example, the :class:`~django_typer.parsers.model.ModelObjectParser` can
be used to fetch a model object from a given field. By default it will use the primary key,
so we could rewrite the relevant lines above like so:

.. code-block:: python

    from django_typer.parsers.model import ModelObjectParser

    # ...

    t.Annotated[
        t.List[Poll],
        Argument(
            parser=ModelObjectParser(Poll),
            help=_("The database IDs of the poll(s) to close.")
        )
    ]

    # ...

Add shell tab-completion suggestions for polls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It's very annoying to have to know the database primary key of the poll to close it. django-typer_ makes it
easy to add tab completion suggestions! You can always `implement your own completer functions
<https://click.palletsprojects.com/en/8.1.x/shell-completion/#custom-type-completion>`_, but as
with, :mod:`~django_typer.parsers`, there are some out-of-the-box :mod:`~django_typer.completers`
that make this easy. Let's see what the relevant updates to our closepoll command would look like:

.. code-block:: python

    from django_typer.parsers.model import ModelObjectParser
    from django_typer.completers.model import ModelObjectCompleter

    # ...

    t.Annotated[
        t.List[Poll],
        Argument(
            parser=ModelObjectParser(Poll),
            shell_complete=ModelObjectCompleter(Poll, help_field='question_text'),
            help=_("The database IDs of the poll(s) to close.")
        )
    ]

    # ...

.. note::

    For tab-completions to work you will need to
    :ref:`install the shell completion scripts for your shell <shellcompletions>`.


Putting it all together
~~~~~~~~~~~~~~~~~~~~~~~

When we're using a :class:`~django_typer.parsers.model.ModelObjectParser` and
:class:`~django_typer.completers.model.ModelObjectCompleter` we can use the
:func:`~django_typer.utils.model_parser_completer` convenience function to reduce the amount
of boiler plate. Let's put everything together and see what our full-featured refactored
closepoll command looks like:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_t6.py
            :language: python
            :linenos:
            :replace:
                tests.apps.examples.polls.models : polls.models

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/polls/management/commands/closepoll_t6_typer.py
            :language: python
            :linenos:
            :replace:
                tests.apps.examples.polls.models : polls.models


.. only:: html

    .. image:: /_static/img/closepoll_example.gif
        :align: center

.. only:: latex

    .. image:: /_static/img/closepoll_example.png
        :align: center
