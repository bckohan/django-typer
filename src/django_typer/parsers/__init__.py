"""
Typer_ supports custom parsers for options and arguments. If you would
like to type a parameter with a type that isn't supported by Typer_ you can
`implement your own parser
<https://typer.tiangolo.com/tutorial/parameter-types/custom-types>`_, or
:class:`click.ParamType` in :doc:`click <click:parameter-types>` parlance.

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
        - Returns None if the value is None (already implemented if subclassing
          ParamType).
        - Raises a :exc:`~django.core.management.CommandError` if the value is invalid.
        - Handles the case where the param and context are None.
"""
