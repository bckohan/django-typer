import typing as t

from typer import BadParameter
from typer._click import Context, Parameter


class ParamType:
    """
    A minimal stand-in for Click_'s ``ParamType``, provided for backwards compatibility.

    Typer_ 0.29 removed the vendored Click_ ``ParamType``. Typer_ now calls parsers with
    the string value only, so any callable works as a parser. Subclasses of this class
    keep working: calling an instance invokes :meth:`convert` with ``param`` and ``ctx``
    set to None, exactly as earlier Typer_ versions did for parsers.

    .. deprecated:: 4.3.0

        Write parsers as plain callables or classes that implement ``__call__``, see
        :mod:`django_typer.parsers`. This class will be removed in 5.0.
    """

    name: str = "text"

    def __call__(
        self,
        value: t.Any,
        param: Parameter | None = None,
        ctx: Context | None = None,
    ) -> t.Any:
        if value is not None:
            return self.convert(value, param, ctx)
        return None

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        """
        Convert the value to the correct type. Override this in subclasses.

        :param value: The value to convert.
        :param param: The parameter the value is for, may be None.
        :param ctx: The active context, may be None.
        """
        return value

    def fail(
        self,
        message: str,
        param: Parameter | None = None,
        ctx: Context | None = None,
    ) -> t.NoReturn:
        """
        Raise a :class:`typer.BadParameter` with the given message.
        """
        # typer annotates param with its private parameter class
        raise BadParameter(message, ctx=ctx, param=t.cast(t.Any, param))
