.. include:: ./refs.rst

.. _plugins:

===============================
Tutorial: Inheritance & Plugins
===============================

Adding to, or altering the behavior of, commands from upstream Django_ apps is a common use case.
Doing so allows you to keep your CLI_ stable while adding additional behaviors by installing new
apps in :setting:`INSTALLED_APPS`. There are three main extension patterns you may wish to employ:

    1. Override the behavior of a command in an upstream app.
    2. Add additional subcommands or groups to a command in an upstream app.
    3. Hook implementations of custom logic into upstream command extension points.
       (`Inversion of Control <https://en.wikipedia.org/wiki/Inversion_of_control>`_)

The django-typer_ plugin mechanism supports all three of these use cases in a way that respects
the precedence order of apps in the :setting:`INSTALLED_APPS` setting. In this tutorial we walk
through an example of each using a
:ref:`generic backup command <extensions:A Generic Backup Command>`. First we'll see how we
might :ref:`use inheritance (1) <extensions:Inheritance>` to override and change the behavior of
a subcommand. Then we'll see how we can :ref:`add subcommands (2) <extensions:CLI Plugins>` to
an upstream command using plugins. Finally we'll use pluggy_ to implement a hook system that
allows us to :ref:`add custom logic (3) <extensions:Logic Plugins>` to an upstream command.

A Generic Backup Command
-------------------------

Consider the task of backing up a Django website. State is stored in the database, in media files
on disk, potentially in other files, and also in the software stack running on the server. If we
want to provide a general backup command that might be used downstream we cannot know all potential
state that might need backing up. We can use django-typer_ to define a command that can be extended
with additional backup logic. On our base command we'll only provide a database backup routine,
but we anticipate our command being extended so we may also provide default behavior that will
discover and run every backup routine defined on the command if no specific subroutine is invoked.
We can `use the context <https://typer.tiangolo.com/tutorial/commands/context/#getting-the-context>`_
to determine if a subcommand was called in our root initializer callback and we can find
subroutines added by plugins at runtime using
:func:`~django_typer.management.TyperCommand.get_subcommand`. Our command might look like this:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/plugins/backup/management/commands/backup.py
            :language: python
            :caption: backup/management/commands/backup.py
            :linenos:

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/plugins/backup/management/commands/backup_typer.py
            :language: python
            :caption: backup/management/commands/backup.py
            :linenos:


.. typer:: tests.apps.examples.plugins.backup.management.commands.backup.Command:typer_app
    :prog: manage.py backup
    :width: 80
    :show-nested:
    :convert-png: latex
    :theme: dark

|

.. code-block:: console

    $> python manage.py backup list
    Default backup routines:
        database(filename={database}.json, databases=['default'])

Inheritance
-----------

The first option we have is simple inheritance. Lets say the base command is defined in
an app called backup. Now say we have another app that uses media files. This means we'll
want to add a media backup routine to the backup command.

.. note::

    Inheritance also works for commands defined using the Typer-style function based interface.
    Import the root Typer_ app from the upstream command module and pass it as an argument
    to Typer_ when you create the root app in your overriding command module.

Say our app tree looks like this:

.. code-block:: text

    ./
    ├── backup/
    │   ├── __init__.py
    │   ├── apps.py
    │   ├── management/
    │   │   ├── __init__.py
    │   │   └── commands/
    │   │       ├── __init__.py
    │   │       └── backup.py
    └── media/
        ├── __init__.py
        ├── apps.py
        └── management/
            ├── __init__.py
            └── commands/
                ├── __init__.py
                └── backup.py

.. code-block:: python

    INSTALLED_APPS = [
        'media',
        'backup',
        ...
    ]

Our backup.py implementation in the media app might look like this:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/plugins/media1/management/commands/backup.py
            :language: python
            :caption: media/management/commands/backup.py
            :replace:
                    tests.apps.examples.plugins.backup : backup

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/plugins/media1/management/commands/backup_typer.py
            :language: python
            :caption: media/management/commands/backup.py
            :replace:
                    tests.apps.examples.plugins.backup : backup

Now you'll see we have another command called media available:

.. typer:: tests.apps.examples.plugins.media1.management.commands.backup.Command:typer_app
    :prog: manage.py backup
    :width: 80
    :convert-png: latex
    :theme: dark

|

Now we have a media backup routine that we can run individually or part of the entire
backup batch:

.. typer:: tests.apps.examples.plugins.media1.management.commands.backup.Command:typer_app:media
    :prog: manage.py backup media
    :width: 80
    :convert-png: latex
    :theme: dark


.. code-block:: bash

    $> python manage.py backup list
    Default backup routines:
        database(filename={database}.json, databases=['default'])
        media(filename=media.tar.gz)
    # backup media only
    $> python manage.py backup media
    Backing up ./media to ./media.tar.gz
    # or backup database and media
    $> python manage.py backup
    Backing up database [default] to: ./default.json
    [.............................................]
    Backing up ./media to ./media.tar.gz


When Does Inheritance Make Sense?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Inheritance is a good choice when you want to tweak the behavior of a specific command and **do not
expect other apps to also modify the same command**. It's also a good choice when you want to offer
a different flavor of a command under a different name.

What if other apps want to alter the same command and we don't know about them, but they may end up
installed along with our app? This is where the plugin pattern will serve us better.


CLI Plugins
-----------

**The plugin pattern allows us to add or override commands and groups on an upstream command
directly without overriding it or changing its name. This allows downstream apps that know
nothing about each other to add their own behavior to the same command. If there are conflicts
they are resolved in INSTALLED_APPS order.**

To do this we have to abandon the class based interface and place our plugins in a module other
than ``commands``. Let us suppose we are developing a site that uses the backup and media app from
upstream and we've implemented most of our custom site functionality in a new app called my_app.
Because we're now mostly working at the level of our particular site we may want to add more custom
backup logic. For instance, lets say we know our site will always run on sqlite and we prefer
to just copy the file to backup our database. It is also useful for us to capture the python stack
(e.g. requirements.txt) running on our server. To do that we can use the plugin pattern to add our
environment backup routine and override the database routine from the upstream backup app. Our app
tree now might look like this:

.. code-block:: text

    ./
    ├── backup/
    │   ├── __init__.py
    │   ├── apps.py
    │   ├── management/
    │   │   ├── __init__.py
    │   │   └── commands/
    │   │       ├── __init__.py
    │   │       └── backup.py
    ├── media/
    │   ├── __init__.py
    │   ├── apps.py
    │   └── management/
    │       ├── __init__.py
    │       ├── commands/
    │       └── plugins/
    │           └── __init__.py
    │           └── backup.py
    └── my_app/
        ├── __init__.py
        ├── apps.py
        └── management/
            ├── __init__.py
            ├── commands/
            └── plugins/
                └── __init__.py
                └── backup.py


Note that we've added a ``plugins`` directory to the management directory of the ``media`` and
``my_app`` apps. This is where we'll place our command extensions. We must register our plugins
directory in the ``apps.py`` file of the media and my_app apps like this:

.. code-block:: python

    from django.apps import AppConfig
    from django_typer.utils import register_command_plugins

    class MyAppConfig(AppConfig):
        name = 'my_app'

        def ready(self):
            from .management import plugins

            register_command_plugins(plugins)

.. note::

    Because we explicitly register our plugins we can call the package whatever we want.
    django-typer does not require it to be named ``plugins``. It is also important to
    do this inside ready() because conflicts are resolved in the order in which the extension
    modules are registered and ready() methods are called in :setting:`INSTALLED_APPS` order.

For plugins to work, we'll need to re-implement media from above as a composed extension
like this:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/plugins/media2/management/plugins/backup.py
            :language: python
            :caption: media/management/plugins/backup.py
            :replace:
                    tests.apps.examples.plugins.backup : backup

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/plugins/media2/management/plugins/backup_typer.py
            :language: python
            :caption: media/management/plugins/backup.py
            :replace:
                    tests.apps.examples.plugins.backup : backup



And our my_app extension might look like this:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/plugins/my_app/management/plugins/backup.py
            :language: python
            :caption: my_app/management/plugins/backup.py
            :replace:
                    tests.apps.examples.plugins.backup : backup

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/plugins/my_app/management/plugins/backup_typer.py
            :language: python
            :caption: my_app/management/plugins/backup.py
            :replace:
                    tests.apps.examples.plugins.backup : backup

Note that we now have a new environment command available:

.. typer:: backup_example:app
    :prog: manage.py backup
    :width: 80
    :convert-png: latex
    :theme: dark

.. typer:: backup_example:app:environment
    :prog: manage.py backup environment
    :width: 80
    :convert-png: latex
    :theme: dark

|

And the command line parameters to database have been removed:

.. typer:: backup_example:app:database
    :prog: manage.py backup database
    :width: 80
    :convert-png: latex
    :theme: dark

|

.. note::

    The extension code is lazily loaded. This means plugins are resolved on command classes
    the first time an instance of the class is instantiated. This avoids unnecessary code
    execution but does mean that if you are working directly with the ``typer_app`` attribute
    on a :class:`~django_typer.management.TyperCommand` you will need to make sure at least one
    instance has been instantiated.


Overriding Groups
~~~~~~~~~~~~~~~~~

Some commands might have deep nesting of subcommands and groups. If you want to override a
group or subcommand of a group down a chain of commands you would need to access the
:class:`~django_typer.Typer` instance of the group you want to override or extend:

.. tabs::

    .. tab:: Django-style

        .. code-block:: python

            from somewhere.upstream.management.commands.command import Command

            # add a command to grp2 which is a subgroup of grp1
            @Command.grp1.grp2.command()
            def my_command():  # remember self is optional
                pass

            # add a subgroup to grp2 which is a subgroup of grp1
            @Command.grp1.grp2.group()
            def grp3():
                pass

    .. tab:: Typer-style

        .. code-block:: python

            from somewhere.upstream.management.commands.command import app

            # add a command to grp2 which is a subgroup of grp1
            @app.grp1.grp2.command()
            def my_command():  # remember self is optional
                pass

            # add a subgroup to grp2 which is a subgroup of grp1
            @app.grp1.grp2.group()
            def grp3():
                pass

You may even override the initializer of a predefined group:

.. tabs::

    .. tab:: Django-style

        .. code-block:: python

            from somewhere.upstream.management.commands.command import Command

            # override the initializer (typer callback) of grp1 on Command,
            # this will not alter the child groups of grp1 (grp2, grp3, etc.)
            @Command.grp1.initialize()
            def grp1_init(self):
                pass

            @Command.group()
            def grp1(self):
                """
                This would override grp1 entirely and remove all subcommands
                and groups.
                """

    .. tab:: Typer-style

        .. code-block:: python

            from somewhere.upstream.management.commands.command import app

            # override the initializer (typer callback) of grp1 on app,
            # this will not alter the child groups of grp1 (grp2, grp3, etc.)
            @app.grp1.initialize()
            def grp1_init():
                pass

            @app.group()
            def grp1():
                """
                This would override grp1 entirely and remove all subcommands
                and groups.
                """

.. tip::

    If a group or command has not been directly defined on a Command class, django-typer will do
    a `breadth first search <https://en.wikipedia.org/wiki/Breadth-first_search>`_ of the command
    tree and fetch the first group or subcommand that matches the name of the attribute. This
    means that you do not necessarily have to walk the command hierarchy
    (i.e. ``Command.grp1.grp2.grp3.cmd``), if there is only one cmd you can simply write
    ``Command.cmd``. However, using the strict hierarchy will be robust to future changes.

When Do CLI Plugins Make Sense?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Plugins can be used to group like behavior together under a common root command. This can be
thought of as a way to namespace CLI tools or easily share significant code between tools that have
common initialization logic. Moreover it allows you to do this safely and in a way that can be
deterministically controlled in settings. Most use cases are not this complex and even our backup
example could probably better be implemented as a
`batch of commands <https://github.com/bckohan/django-routines>`_.

Django apps are great for forcing separation of concerns on your code base. In large self contained
projects its often a good idea to break your code into apps that are as self contained as possible.
Plugins can be a good way to organize commands in a code base that follows this pattern. It
also allows for deployments that install a subset of those apps and is therefore a good way to
organize commands in code bases that serve as a framework for a particular kind of site or that
support selecting the features to install by the inclusion or exclusion of specific apps.


Logic Plugins
-------------

`Inversion of Control (IoC) <https://en.wikipedia.org/wiki/Inversion_of_control>`_ is a design
pattern that allows you to inject custom logic into a framework or library. The framework defines
the general execution flow with extension points along the way that downstream applications can
provide the implementations for. Django uses IoC all over the place. Extension points are often
called ``hooks``. **You may use a third party library to manage hooks or implement your own
mechanism but you will always need to register hook implementations. The same plugin mechanism we
used in the** :ref:`last section <extensions:CLI Plugins>` **provides a natural place to do this.**

Some Django_ apps may keep state in files in places on the filesystem unknown to other parts of
your code base. In this section we'll use pluggy_ to define a hook for other apps to implement to
backup their own files. Let's:

1. Create a new app ``backup_files`` and inherit from our the extended media backup command we
   created in the :ref:`inheritance section <extensions:Inheritance>`.
2. Define a pluggy_ interface for backing up arbitrary files
3. Add a ``files`` command to our backup command that will call all registered
   hooks to backup their own files.

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/plugins/backup_files/management/commands/backup.py
            :language: python
            :caption: backup_files/management/commands/backup.py
            :linenos:
            :replace:
                tests.apps.examples.plugins.media1: media

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/plugins/backup_files/management/commands/backup_typer.py
            :language: python
            :caption: backup_files/management/commands/backup.py
            :linenos:
            :replace:
                tests.apps.examples.plugins.media1: media

Now lets define two new apps, files1 and files2 that will provide and register implementations of
the backup_files hook:

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/plugins/files1/management/plugins/backup.py
            :language: python
            :caption: files1/management/plugins/backup.py
            :linenos:
            :replace:
                tests.apps.examples.plugins.backup_files: backup_files

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/plugins/files1/management/plugins/backup_typer.py
            :language: python
            :caption: files1/management/plugins/backup.py
            :linenos:
            :replace:
                tests.apps.examples.plugins.backup_files: backup_files

.. tabs::

    .. tab:: Django-style

        .. literalinclude:: ../../tests/apps/examples/plugins/files2/management/plugins/backup.py
            :language: python
            :caption: files2/management/plugins/backup.py
            :linenos:
            :replace:
                tests.apps.examples.plugins.backup_files: backup_files

    .. tab:: Typer-style

        .. literalinclude:: ../../tests/apps/examples/plugins/files2/management/plugins/backup_typer.py
            :language: python
            :caption: files2/management/plugins/backup.py
            :linenos:
            :replace:
                tests.apps.examples.plugins.backup_files: backup_files

Both ``files1`` and ``files2`` will need to register their plugin packages in their ``apps.py``
file:

.. literalinclude:: ../../tests/apps/examples/plugins/files1/apps.py
    :language: python
    :caption: files1/apps.py
    :linenos:
    :replace:
        tests.apps.examples.plugins.files1: files1

Now when we run we see:

.. code-block:: bash

    $> python manage.py backup
    Backing up database [default] to: ./default.json
    [.............................................]
    Backing up ./media to ./media.tar.gz
    Backed up files to ./files2.zip
    Backed up files to ./files1.tar.gz


When Do Logic Plugins Make Sense?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:ref:`CLI plugins make sense <extensions:When Do CLI Plugins Make Sense?>` when you want to add
additional commands or under a common namespace or to override the entire behavior of a command.
Logical plugins make more sense in the weeds of a particular subroutine. Our example above has
the following qualities which makes it a good candidate:

1. The logic makes sense under a common root name (e.g. ``./manage.py backup files``).
2. Multiple apps may need to execute their own version of the logic to complete the operation.
3. The logic is amenable to a common interface that all plugins can implement.
