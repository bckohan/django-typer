"""
Typer_ supports custom parsers for options and arguments. If you would
like to type a parameter with a type that isn't supported by Typer_ you can
`implement your own parser
<https://typer.tiangolo.com/tutorial/parameter-types/custom-types>`_. A parser is any
callable that accepts the string value given on the command line and returns the
parsed value. Use a function for simple parsers, or a class that implements
``__call__`` when the parser needs configuration:

.. code-block:: python

    import typing as t

    import typer
    from django.core.management import CommandError

    from django_typer.management import TyperCommand


    class Interval:
        def __init__(self, unit: str = "s"):
            self.unit = unit
            # django-typer labels the parameter's type in help with this name
            self.__name__ = unit

        def __call__(self, value: str | float) -> float:
            try:
                if isinstance(value, str):
                    value = value.removesuffix(self.unit)
                return float(value)
            except ValueError as err:
                raise CommandError(f"{value} is not a valid interval.") from err


    class Command(TyperCommand):
        def handle(
            self,
            interval: t.Annotated[float, typer.Argument(parser=Interval("ms"))],
        ):
            ...

Parameters of :class:`~django_typer.management.TyperCommand` commands are labeled in
help with the ``__name__`` of their parser (or its ``name`` attribute), so the example
above shows ``<ms>``. Plain Typer_ apps label the parameter from its type annotation
instead.

This package contains a collection of parsers that turn strings into useful
Django types. Pass these parsers to the `parser` argument of ``typer.Option`` and
``typer.Argument``. Parsers are provided for:

- **models, querysets or field values**: Turn a string into a model object instance
    using :class:`~django_typer.parsers.model.ModelObjectParser`.
- **Django apps**: Turn a string into an AppConfig instance using
    :func:`~django_typer.parsers.apps.app_config`.


.. warning::

    If you implement a custom parser, please take care to ensure that it:
        - Handles the case where the value is already the expected type.
        - Raises a :exc:`~django.core.management.CommandError` if the value is invalid.

.. deprecated:: 4.3.0

    ``ParamType`` is deprecated. Typer_ 0.29 removed the vendored Click_ ``ParamType``,
    so django-typer_ provides a minimal stand-in that keeps existing subclasses working.
    Subclassing it emits a :exc:`DeprecationWarning` and it will be removed in 5.0. Write
    parsers as callables instead, as above. ``Context`` and ``Parameter`` are still
    exported for type hints.
"""

from typer._click import Context as Context
from typer._click import Parameter as Parameter

from ._param_type import ParamType as ParamType
