.. include:: ./refs.rst

Architecture
------------

The principal design challenge of django-typer_ is to manage the Typer_ app trees associated with
each Django management command class and to keep these trees separate when classes are inherited
and allow them to be edited directly when commands are extended through the plugin pattern. There
are also incurred complexities with adding default django options where appropriate and supporting
command callbacks as methods or static functions. Supporting dynamic command/group access through
attributes on command instances also requires careful usage of advanced Python features.

The Typer_ app tree defines the layers of groups and commands that define the CLI. Each
:class:`~django_typer.TyperCommand` maintains its own app tree defined by a root
:class:`~django_typer.Typer` node. When other classes inherit from a base command class, that app
tree is copied and the new class can modify it without affecting the base class's tree. We extend
Typer_'s Typer type with our own :class:`~django_typer.Typer` class that adds additional
bookkeeping and attribute resolution features we need.

django-typer_ must behave intuitively as expected and therefore it must support all of the
following:

* Inherited classes can extend and override groups and commands defined on the base class without
  affecting the base class so that the base class may still be imported and used directly as it
  was originally designed.
* Extensions defined using the plugin pattern must be able to modify the app trees of the
  commands they plugin to directly.
* The group/command tree on instantiated commands must be walkable using attributes from the
  command instance itself to support subgroup name overloads.
* Common django options should appear on a common initializer for compound commands with multiple
  groups or commands and should appear directly on the command for non-compound commands.

During all of this, the correct self must be passed if the function accepts it, but all of the
registered functions are not registered as methods because they enter the Typer_ app tree as
regular functions. This means another thing django-typer_ must do is decide if a function is a
method and if so, bind it to the correct class and pass the correct self instance. The method
test is :func:`~django_typer.utils.is_method` and simply checks to see if the function accepts
a first positional argument named `self`.

django-typer_ uses metaclasses to build the typer app tree when :class:`~django_typer.TyperCommand`
classes are instantiated. The logic flow proceeds this way:

- Class definition is read and @initialize/@callback, @group, @command decorators label and store
  typer config and registration logic onto the function objects for processing later once the root
  Typer_ app is created.
- Metaclass __new__ creates the root Typer_ app for the class and redirects the implementation of
  handle if it exists. It then walks the classes in MRO order and runs the cached command/group
  registration logic for commands and groups defined directly on each class. Commands and groups
  defined dynamically (i.e. registered after Command class definition in plugins) *are not*
  included during this registration because they do not appear as attributes on the base classes.
  This keeps inheritance pure while allowing plugins to not interfere. The exception to this is
  when using the Typer-style interface where all commands and groups are registered dynamically.
  A :class:`~django_typer.Typer` instance is passed as an argument to the
  :class:`~django_typer.Typer` constructor and when this happens, the commands and groups will
  be copied.
- Metaclass __init__ sets the newly created Command class into the typer app tree and determines
  if a common initializer needs to be added containing the default unsupressed django options.
- Command __init__ loads any registered plugins (this is a one time opperation that will happen
  when the first Command of a given type is instantiated). It also determines if the addition
  of any plugins should necessitate the addition of a common initializer and makes some last
  attempts to pick the correct help from __doc__ if no help is present.

Below you can see that the backup inhertiance example :class:`~django_typer.Typer` tree. Each
command class has its own completely separate tree.

.. image:: /_static/img/inheritance_tree.png
    :align: center

|

Contrast this with the backup plugin example where after the plugins are loaded the same command
tree has been altered. Note that after the plugins have been applied two database commands are
present. This is ok, the ones added last will be used.

.. image:: /_static/img/plugin_tree.png
    :align: center

|

.. code-block:: python

    class Command(TyperCommand):

        # command() runs before the Typer_ app is created, therefore we
        # have to cache it and run it later during class creation
        @command()
        def cmd1(self):
            pass

        @group()
        def grp1(self):
            pass

        @grp1.group(self):
        def grp2(self):
            pass


.. code-block:: python

    class Command(UpstreamCommand):

      # This must *not* alter the grp1 app on the base
      # app tree but instead create a new one on this
      # commands app tree when it is created
      @UpstreamCommand.grp1.command()
      def cmd3(self):
          pass

      # this gets interesting though, because these should be
      # equivalent:
      @UpstreamCommand.grp2.command()
      def cmd4(self):
          pass

      # we use custom __getattr__ methods on TyperCommand and Typer to
      # dynamically run BFS search for command and groups if the members
      # are not present on the command definition.
      @UpstreamCommand.grp1.grp2.command()
      def cmd4(self):
          pass


.. code-block:: python

  # extensions called at module scope should modify the app tree of the
  # command directly
  @UpstreamCommand.grp1.command()
  def cmd4(self):
      pass


.. code-block:: python

  app = Typer()

  # similar to extensions these calls should modify the app tree directly
  # the Command class exists after the first Typer() call and app is a reference
  # directly to Command.typer_app
  @app.callback()
  def init():
    pass


  @app.command()
  def main():
      pass

  grp2 = Typer()
  app.add_typer(grp2)

  @grp2.callback(name="grp1")
  def init_grp1():
      pass

  @grp2.command()
  def cmd2():
      pass