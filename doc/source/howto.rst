.. include:: ./refs.rst

======
How-To
======

Define an Argument
------------------

Positional arguments on a command are treated as positional command line arguments by Typer_.
For example to define an integer positional argument we could simply do:

.. code-block::

    def handle(self, int_arg: int):
        ...

You will likely want to add additional meta information to your arguments for Typer_ to render
things like helps and usage strings.  You can do this by annotating the type hint with
the `typer.Argument` class:

.. code-block::

    import typing as t
    from typer import Argument

    # ...

    def handle(self, int_arg: t.Annotated[int, Argument(help="An integer argument")]):
        ...

.. tip::

    Refer to the Typer_ docs on arguments_ for more details.


Define an Option
----------------

Options are like arguments but are not position dependent and instead provided with a preceding
identifier string (e.g. `--name`).

When a default value is provided for a parameter, Typer_ will treat it as an option.  For example:

.. code-block:: python

    def handle(self, flag: bool = False):
        ...

Would be called like this:

.. code-block:: bash

    $ mycommand --flag

If the type hint on the option is something other than a boolean it will accept a value:

.. code-block:: bash

    def handle(self, name: str = "world"):
        ...

Would be called like this:

.. code-block:: bash

    $ mycommand --name=world
    $ mycommand --name world  # this also works

To add meta information, we annotate with the `typer.Option` class:

.. code-block::

    import typing as t
    from typer import Option

    # ...

    def handle(self, name: t.Annotated[str, Option(help="The name of the thing")]):
        ...

.. tip::

    Refer to the Typer_ docs on options_ for more details.


.. _multi_commands:

Define Multiple Subcommands
---------------------------

Commands with a single executable function should simply implement handle(), but if you would
like have multiple subcommands you can define any number of functions decorated with
:func:`~django_typer.management.command` or :func:`~django_typer.management.Typer.command`:

.. tabs::

    .. tab:: Django-style

        .. code-block:: python

            from django_typer.management import TyperCommand, command

            class Command(TyperCommand):

                @command()
                def subcommand1(self):
                    ...

                @command()
                def subcommand2(self):
                    ...

    .. tab:: Typer-style

        .. code-block:: python

            from django_typer.management import Typer

            app = Typer()

            @app.command()
            def subcommand1():
                ...

            @app.command()
            def subcommand2():
                ...

.. note::

    When no handle() method is defined, you cannot invoke a command instance as a callable. instead
    you should invoke subcommands directly:

    .. code-block:: python

        from django_typer.management import get_command

        command = get_command("mycommand")
        command.subcommand1()
        command.subcommand2()

        command() # this will raise an error


.. _default_cmd:

Define Multiple Subcommands w/ a Default
-----------------------------------------

We can also implement a default subcommand by defining a handle() method, and we can rename it to
whatever we want the command to be. For example to define three subcommands but have one as the
default we can do this:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/default_cmd.py
            :language: python
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/default_cmd_typer.py
            :language: python
            :linenos:


.. code-block:: python

    from django_typer.management import get_command

    command = get_command("mycommand")
    assert command.subcommand2() == 'subcommand2'
    assert command.subcommand3() == 'subcommand3'

    # this will invoke handle (i.e. subcommand1)
    assert command() == 'handle'
    command()

    # note - we *cannot* do this:
    command.handle()

    # but we can do this!
    assert command.subcommand1() == 'handle'


Lets look at the help output:

.. typer:: tests.apps.howto.management.commands.default_cmd.Command:typer_app
    :width: 80
    :convert-png: latex

.. _groups:

Define Groups of Commands
-------------------------

Any depth of command tree can be defined. Use the :func:`~django_typer.management.group` or
:meth:`~django_typer.management.Typer.add_typer` decorator to define a group of subcommands:


.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/groups.py
            :language: python
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/groups_typer.py
            :language: python
            :linenos:

The hierarchy of groups and commands from the above example looks like this:

.. image:: /_static/img/howto_groups_app_tree.png
    :align: center

.. _initializer:

Define an Initialization Callback
---------------------------------

You can define an initializer function that takes arguments_ and options_ that will be invoked
before your handle() command or subcommands using the :func:`~django_typer.management.initialize`
decorator. This is like defining a group at the command root and is an extension of the
`typer callback mechanism <https://typer.tiangolo.com/tutorial/commands/callback/>`_.


.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/initializer.py
            :language: python
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/initializer_typer.py
            :language: python
            :linenos:

.. code-block:: console

    $> ./manage initializer --common-option subcommand1
    True
    $> ./manage.py initializer --no-common-option subcommand2
    False

.. code-block:: python

    from django_typer.management import get_command

    command = get_command("initializer")
    command.init(common_option=True)
    assert command.subcommand1()
    command.init(False)
    assert not command.subcommand2()


.. _howto_finalizers:

Collect Results with @finalize
------------------------------

Typer_ and :doc:`Click <click:commands>` have a ``results_callback`` mechanism on ``MultiCommands``
that allow a function hook to be registered to operate on the results of subroutines before the
command exits. You may use this same ``results_callback`` mechanism directly through the Typer_
interface, but django-typer_ offers a more convenient class-aware way to do this with the
:func:`~django_typer.management.finalize` decorator.

For example lets say we have two subcommands that return strings, we could turn them into a csv
string by registering a callback with :func:`~django_typer.management.finalize`:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/finalize.py

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/finalize_typer.py


    .. tab:: Typer-style w/finalize

        .. literalinclude:: ../../tests/apps/howto/management/commands/finalize_typer_ext.py


.. code-block:: console

        $> ./manage.py finalizer cmd1 cmd1 cmd2
        result1, result2, result3

.. tip::

    @finalize() wrapped callbacks will be passed the CLI parameters on the current context
    if the function signature accepts them. While convenient, we recommend using command state to
    track these parameters instead. This will be more amenable to direct invocations of command
    object functions.

Use @finalize on groups
~~~~~~~~~~~~~~~~~~~~~~~

Finalizers are hierarchical. The :func:`~django_typer.management.finalize` decorator is available
for use on subgroups. When used on a group, the callback will be invoked after the group's
subcommands have been executed and the return value of the finalizer will be passed up to any
finalizers at higher levels in the command hierarchy.

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/finalize_group.py

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/finalize_group_typer.py

    .. tab:: Typer-style w/finalize

        .. literalinclude:: ../../tests/apps/howto/management/commands/finalize_group_typer_ext.py

.. code-block:: console

        $> ./manage.py finalizer cmd1 cmd1 cmd2 grp cmd4 cmd3
        result1, result2, result3, RESULT4, RESULT3

.. tip::

    Finalizers can be overridden just like groups and initializers using the
    :ref:`plugin pattern. <plugins>`


Call Commands from Code
-----------------------

There are two options for invoking a :class:`~django_typer.management.TyperCommand` from code
without spawning off a subprocess. The first is to use Django_'s builtin
:func:`~django.core.management.call_command` function. This function will work exactly as it does
for normal :class:`~django.core.management.BaseCommand` derived commands. django-typer_ however adds
another mechanism that can be more efficient, especially if your options and arguments are already
of the correct type and require no parsing:

Say we have this command, called ``mycommand``:

.. code-block:: python

    from django_typer.management import TyperCommand, command

    class Command(TyperCommand):

        def handle(self, count: int=5):
            return count


.. code-block:: python

    from django.core.management import call_command
    from django_typer.management import get_command

    # we can use use call_command like with any Django command
    call_command("mycommand", count=10)
    call_command("mycommand", '--count=10')  # this will work too

    # or we can use the get_command function to get a command instance and invoke it directly
    mycommand = get_command("mycommand")
    mycommand(count=10)
    mycommand(10) # this will work too

    # return values are also available
    assert mycommand(10) == 10


The rule of thumb is this:

    - Use :func:`~django.core.management.call_command` if your options and arguments need parsing.
    - Use :func:`~django_typer.management.get_command` and invoke the command functions directly if
      your options and arguments are already of the correct type.

If the second argument is a type, static type checking will assume the return value of get_command
to be of that type:

.. code-block:: python

    from django_typer.management import get_command
    from myapp.management.commands.math import Command as Math

    math = get_command("math", Math)
    math.add(10, 5)  # type checkers will resolve add parameters correctly

You may also fetch a subcommand function directly by passing its path:

.. code-block:: python

    get_command("math", "add")(10, 5)

.. tip::

    Also refer to the :func:`~django_typer.management.get_command` docs and :ref:`here <default_cmd>`
    and :ref:`here <multi_commands>` for the nuances of calling commands when handle() is and is
    not implemented.


.. _default_options:

Change Default Django Options
-----------------------------

:class:`~django_typer.management.TyperCommand` classes preserve all of the functionality of
:class:`~django.core.management.BaseCommand` derivatives. This means that you can still use class
members like :attr:`~django.core.management.BaseCommand.suppressed_base_arguments` to suppress
default options.

By default :class:`~django_typer.management.TyperCommand` suppresses :option:`--verbosity`. You can
add it back by setting :attr:`~django.core.management.BaseCommand.suppressed_base_arguments` to an
empty list. If you want to use verbosity you can simply redefine it or use one of django-typer_'s
:ref:`provided type hints <types>` for the default :class:`~django.core.management.BaseCommand`
options:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/default_options.py
            :language: python
            :linenos:


    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/default_options_typer.py
            :language: python
            :linenos:

.. _configure:

Configure Typer_ Options
------------------------

Typer_ apps can be configured using a number of parameters. These parameters are usually passed
to the :class:`~django_typer.management.Typer` class constructor when the application is created.
django-typer_ provides a way to pass these options upstream to Typer_ by supplying them as keyword
arguments to the :class:`~django_typer.management.TyperCommand` class inheritance:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/configure.py
            :language: python
            :linenos:
            :caption: configure.py

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/configure_typer.py
            :language: python
            :linenos:
            :caption: configure.py

.. code-block:: console

    $> ./manage.py configure cmd1 cmd2
    cmd1
    cmd2

    $> ./manage.py configure cmd2 cmd1
    cmd2
    cmd1

.. tip::

    See :class:`~django_typer.management.TyperCommandMeta` or
    :class:`~django_typer.management.Typer` for a list of available parameters. Also refer to the
    `Typer docs <https://typer.tiangolo.com>`_ for more details.


Define Shell Tab Completions for Parameters
-------------------------------------------

See the section on :ref:`defining shell completions.<define-shellcompletions>`


Debug Shell Tab Completers
--------------------------

See the section on :ref:`debugging shell completers.<debug-shellcompletions>`


Inherit/Override Commands
-------------------------

You can extend typer commands by subclassing them. All of the normal inheritance rules apply. You
can either subclass an existing command from an upstream app and leave its module the same name to
override the command or you can subclass and rename the module to provide an adapted version of the
upstream command with a different name. For example:

Say we have a command that looks like:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/upstream.py
            :language: python
            :linenos:
            :caption: management/commands/upstream.py

        We can inherit and override or add additional commands and groups like so:

        .. literalinclude:: ../../tests/apps/howto/management/commands/downstream.py
            :language: python
            :linenos:
            :caption: management/commands/downstream.py

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/upstream_typer.py
            :language: python
            :linenos:
            :caption: management/commands/upstream.py

        We can inherit and override or add additional commands and groups like so:

        .. literalinclude:: ../../tests/apps/howto/management/commands/downstream_typer.py
            :language: python
            :linenos:
            :caption: management/commands/downstream.py
            :replace:
                from .upstream_typer : from .upstream


Notice that if we are adding to a group from the parent class, we have to use the group directly
(i.e. @ParentClass.group_name). Since we named our command downstream it does not override
upstream. upstream is not affected and may be invoked in the same way as if downstream was not
present.

.. note::

    For more information on extension patterns see the tutorial on
    :ref:`Extending Commands <plugins>`.


Plugin to Existing Commands
---------------------------

You may add additional subcommands and command groups to existing commands by using django-typer_'s
plugin pattern. This allows apps that do not know anything about each other to attach additional
CLI behavior to an upstream command and can be convenient for grouping loosely related behavior
into a single command namespace.

To use our example from above, lets add and override the same behavior of upstream we did in
downstream using this pattern instead:

First in other_app we need to create a new package under management. It can be called anything, but
for clarity lets call it plugins:

.. code-block:: text

    site/
    ├── my_app/
    │   ├── __init__.py
    │   ├── apps.py
    │   ├── management/
    │   │   ├── __init__.py
    │   │   └── commands/
    │   │       ├── __init__.py
    │   │       └── upstream.py
    └── other_app/
        ├── __init__.py
        ├── apps.py
        └── management/
            ├── __init__.py
            ├── plugins/
            │   ├── __init__.py
            │   └── upstream.py <---- put your plugins to upstream here
            └── commands/
                └── __init__.py

Now we need to make sure our plugins are loaded. We do this by using the provided
:func:`~django_typer.utils.register_command_plugins` convenience function in
our app's ready() method:

.. code-block:: python
    :caption: other_app/apps.py

    from django.apps import AppConfig
    from django_typer.utils import register_command_plugins


    class OtherAppConfig(AppConfig):
        name = "other_app"

        def ready(self):
            from .management import plugins

            register_command_plugins(extensions)


Now we can add our plugins:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/plugins/upstream2.py
            :language: python
            :linenos:
            :caption: management/plugins/upstream.py
            :replace:
                from ..commands.upstream2 : from my_app.management.commands.upstream

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/plugins/upstream2_typer.py
            :language: python
            :linenos:
            :caption: management/plugins/upstream.py
            :replace:
                from ..commands.upstream2_typer : from my_app.management.commands.upstream

The main difference here from normal inheritance is that we do not declare a new class, instead we
use the classmethod decorators on the class of the command we are extending. These extension
functions will also be added to the class. The self argument is always optional in django-typer_
and if it is not provided the function will be treated as a
`staticmethod <https://docs.python.org/3/library/functions.html#staticmethod>`_.

.. note::

    **Conflicting extensions are resolved in** :setting:`INSTALLED_APPS` **order.** For a detailed
    discussion about the utility of this pattern, see the tutorial on
    :ref:`Extending Commands <plugins>`.

.. warning::

    Take care not to import any extension code during or before Django's bootstrap procedure. This
    may result in conflict override behavior that does not honor :setting:`INSTALLED_APPS` order.

.. _configure-rich-exception-tracebacks:

Configure :doc:`rich <rich:index>` Stack Traces
-----------------------------------------------

When :doc:`rich <rich:index>` is installed it may be
:doc:`configured to display rendered stack traces <rich:traceback>` for unhandled exceptions.
These stack traces are information dense and can be very helpful for debugging. By default, if
:doc:`rich <rich:index>` is installed django-typer_ will configure it to render stack traces. You
can disable this behavior by setting the ``DT_RICH_TRACEBACK_CONFIG`` config to ``False``. You may
also set ``DT_RICH_TRACEBACK_CONFIG`` to a dictionary holding the parameters to pass to
:func:`rich.traceback.install`.

This provides a common hook for configuring :doc:`rich <rich:index>` that you can control on a
per-deployment basis:

.. code-block::
    :caption: settings.py

    # refer to the rich docs for details
    DT_RICH_TRACEBACK_CONFIG = {
        "console": rich.console.Console(), # create a custom Console object for rendering
        "width": 100,                      # default is 100
        "extra_lines": 3,                  # default is 3
        "theme": None,                     # predefined themes
        "word_wrap": False,                # default is False
        "show_locals": True,               # default is False
        "locals_max_length": 10            # default is 10
        "locals_max_string": 80            # default is 80
        "locals_hide_dunder": True,        # default is True
        "locals_hide_sunder": False,       # default is None
        "indent_guides": True,             # default is True
        "suppress": [],                    # suppress frames from these module import paths
        "max_frames": 100                  # default is 100
    }

    # or turn off rich traceback rendering
    DT_RICH_TRACEBACK_CONFIG = False

.. tip::

    There are traceback configuration options that can be supplied as configuration parameters to
    the Typer_ application. It is best to not set these and allow users to configure tracebacks
    via the ``DT_RICH_TRACEBACK_CONFIG`` setting.

Add Help Text to Commands
-------------------------

There are multiple places to add help text to your commands. There is however a precedence order,
and while lazy translation is supported in help texts, if you use docstrings as the helps they will
not be translated.

The precedence order, for a simple command is as follows:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/help.py
            :language: python
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/help_typer.py
            :language: python
            :linenos:


The rule for how helps are resolved when inheriting from other commands is that higher precedence
helps in base classes will be chosen over lower priority helps in deriving classes. However, if
you would like to use a docstring as the help in a derived class instead of the high priority
help in a base class you can set the equivalent priority help in the deriving class to a falsy
value:

.. code-block:: python

    class Command(TyperCommand, help=_("High precedence help defined in base class.")):
        ...

    ...

    from upstream.management.commands.command import Command as BaseCommand
    class Command(BaseCommand, help=None):
        """
        Docstring will be used as help.
        """

Order Commands in Help Text
---------------------------

**By default commands are listed in the order they appear in the class**. You can override
this by
`using a custom click group <https://click.palletsprojects.com/en/latest/commands/#custom-groups>`_.

For example, to change the order of commands to be in alphabetical order you could define a custom
group and override the ``list_commands`` method. Custom group and command classes may be provided
like below, but they must extend from django-typer's classes:

* For groups: :class:`~django_typer.management.DTGroup`
* For commands: :class:`~django_typer.management.DTCommand`

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/order.py

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/order_typer.py

.. tabs::

    .. tab:: Default Order

        .. typer:: tests.apps.howto.management.commands.order_default.Command:typer_app
            :prog: manage.py order
            :width: 80
            :convert-png: latex

        .. typer:: tests.apps.howto.management.commands.order_default.Command:typer_app:d
            :prog: manage.py order d
            :convert-png: latex
            :width: 80

    .. tab:: Alphabetized

        .. typer:: tests.apps.howto.management.commands.order.Command:typer_app
            :prog: manage.py order
            :convert-png: latex
            :width: 80

        .. typer:: tests.apps.howto.management.commands.order.Command:typer_app:d
            :prog: manage.py order d
            :width: 80
            :convert-png: latex

Document Commands w/Sphinx
--------------------------

sphinxcontrib-typer_ can be used to render your rich helps to Sphinx docs and is used extensively
in this documentation.

For example, to document a :class:`~django_typer.management.TyperCommand` with sphinxcontrib-typer,
you would do something like this:

.. code-block:: rst

    .. typer:: django_typer.management.commands.shellcompletion.Command:typer_app
        :prog: ./manage.py shellcompletion
        :show-nested:
        :width: 80

The Typer_ application object is a property of the command class and is named `typer_app`. The typer
directive simply needs to be given the fully qualified import path of the application object.

Or we could render the helps for individual subcommands as well:

.. code-block:: rst

    .. typer:: django_typer.management.commands.shellcompletion.Command:typer_app:install
        :prog: ./manage.py shellcompletion
        :width: 80

You'll also need to make sure that Django is bootstrapped in your conf.py file:

.. code-block:: python
    :caption: conf.py

    import django

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'path.to.your.settings')
    django.setup()

.. _printing:

print, self.stdout and typer.echo
---------------------------------

There are no unbreakable rules about how you should print output from your commands.
You could use loggers, normal print statements or the :class:`~django.core.management.BaseCommand`
stdout and stderr output wrappers. Django advises the use of ``self.stdout.write`` because the
stdout and stderr streams can be configured by calls to :func:`~django.core.management.call_command`
or :func:`~django_typer.management.get_command` which allows you to easily grab output from your
commands for testing. Using the command's configured stdout and stderr output wrappers also means
output will respect the :option:`--force-color` and :option:`--no-color` parameters.

Typer_ and :doc:`click <click:utils>` provide `echo and secho
<https://typer.tiangolo.com/tutorial/printing/>`_ functions that automatically handle byte to string
conversions and offer simple styling support. :class:`~django_typer.management.TyperCommand`
provides :meth:`~django_typer.management.TyperCommand.echo` and
:meth:`~django_typer.management.TyperCommand.secho` wrapper functions for the Typer_ echo/secho
functions. If you wish to use Typer_'s echo you should use these wrapper functions because they
honor the command's :option:`--force-color` and :option:`--no-color` flags and the configured
stdout/stderr streams:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/printing.py
            :language: python
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/printing_typer.py
            :language: python
            :linenos:


Toggle on/off result printing
-----------------------------

Django's :class:`~django.core.management.BaseCommand` will print any truthy values returned from the
:meth:`~django.core.management.BaseCommand.handle` method. This may not always be desired behavior.
By default :class:`~django_typer.management.TyperCommand` will do the same, but you may toggle this
behavior off by setting the class field ``print_result`` to False.


.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/print_result.py
            :language: python
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/howto/management/commands/print_result_typer.py
            :language: python
            :linenos:

.. warning::

    We may switch the default behavior to not print in the future, so if you want guaranteed forward
    compatible behavior you should set this field.
