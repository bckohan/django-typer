import typing as t
import warnings

from typer import BadParameter
from typer._click import Context, Parameter
from typer._click.shell_completion import CompletionItem


class ParamType:
    """
    A minimal stand-in for Click_'s ``ParamType``, provided for backwards compatibility.

    Typer_ 0.29 removed the vendored Click_ ``ParamType``. Typer_ now calls parsers with
    the string value only, so any callable works as a parser. Subclasses of this class
    keep working: calling an instance invokes :meth:`convert` with ``param`` and ``ctx``
    set to None, exactly as earlier Typer_ versions did for parsers. The rest of the
    Click_ interface is present with its default behavior, but Typer_ only ever calls
    the parser: overrides of methods other than :meth:`convert` have no effect.

    .. deprecated:: 4.3.0

        Write parsers as plain callables or classes that implement ``__call__``, see
        :mod:`django_typer.parsers`. This class will be removed in 5.0.
    """

    name: str = "text"

    # The remainder of Click's ParamType interface, kept so subclasses that
    # reference it do not break. Typer does not consult any of it.
    is_composite: t.ClassVar[bool] = False
    arity: t.ClassVar[int] = 1
    envvar_list_splitter: t.ClassVar[str | None] = None

    @staticmethod
    def _deprecated(stacklevel: int) -> None:
        warnings.warn(
            "django_typer.parsers.ParamType is deprecated and will be removed in 5.0. "
            "Implement parsers as callables instead.",
            DeprecationWarning,
            stacklevel=stacklevel,
        )

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        # only warn where ParamType itself is named as a base
        if ParamType in cls.__bases__:
            cls._deprecated(stacklevel=3)

    def __init__(self) -> None:
        if type(self) is ParamType:
            self._deprecated(stacklevel=3)

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

    def to_info_dict(self) -> dict[str, t.Any]:
        """
        Describe this type, as Click_'s ``ParamType`` did. Typer_ does not use this.
        """
        param_type = type(self).__name__.partition("ParamType")[0]
        param_type = param_type.partition("ParameterType")[0]
        return {"param_type": param_type, "name": self.name}

    def get_metavar(self, param: Parameter, ctx: Context) -> str | None:
        """
        Typer_ does not use this, the help label is taken from :attr:`name`.
        """
        return None

    def get_missing_message(self, param: Parameter, ctx: Context | None) -> str | None:
        """
        Typer_ does not use this.
        """
        return None

    def split_envvar_value(self, rv: str) -> t.Sequence[str]:
        """
        Split an environment variable value on :attr:`envvar_list_splitter`, or
        whitespace if it is None. Typer_ does not use this.
        """
        return (rv or "").split(self.envvar_list_splitter)

    def shell_complete(
        self, ctx: Context, param: Parameter, incomplete: str
    ) -> list[CompletionItem]:
        """
        Typer_ does not use this, pass a completer to ``shell_complete`` on the
        parameter instead.
        """
        return []
