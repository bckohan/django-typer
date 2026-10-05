import typing as t
from datetime import date, datetime, time
from enum import Enum
from uuid import UUID

from django.core.management import CommandError
from django.db import models
from typer._click import Context, Parameter
from typer._click.types import ParamType

from django_typer.completers.model import ModelObjectCompleter


class ReturnType(Enum):
    MODEL_INSTANCE = 0
    """Return the model instance with the matching field value."""

    FIELD_VALUE = 1
    """Return the value of the field that was matched."""

    QUERY_SET = 2
    """Return a queryset of model instances that match the field value."""


class ModelObjectParser(ParamType):
    """
    A parser that will turn strings into model object instances based on the
    configured lookup field and model class.

    .. code-block:: python

        from django_typer.parsers.model import ModelObjectParser

        class Command(TyperCommand):
            def handle(
                self,
                django_apps: Annotated[
                    t.List[MyModel],
                    typer.Argument(
                        parser=ModelObjectParser(MyModel, lookup_field="name"),
                        help=_("One or more application labels."),
                    ),
                ],
            ):

    .. note::

        Typer_ does not respect the shell_complete functions on ParamTypes passed as
        parsers. To add shell_completion see
        :class:`~django_typer.completers.ModelObjectCompleter` or the
        :func:`~django_typer.utils.model_parser_completer` convenience function.

    :param model_cls: The model class to use for lookup.
    :param lookup_field: The field to use for lookup. Defaults to 'pk'.
    :param on_error: A callable that will be called if the lookup fails, either
        because the value could not be coerced to the field type or because no
        matching row exists. The callable should accept three arguments: the
        model class, the value that failed to lookup, and the exception that was
        raised. Whatever it returns becomes the parsed value. If not provided, a
        CommandError will be raised.
    :param return_type: The model object parser can return types other than the model
        instance (default) - use the ReturnType enumeration to return other types
        from the parser including QuerySets or the primitive values of the model fields.
    :param return_lookup_on_miss: If True and no row matches, return the lookup value
        instead of raising an error or calling ``on_error``. The value is returned
        after coercion to the field type (e.g. a ``UUID`` for a ``UUIDField``), so
        the caller receives a valid key it can use to create the missing row. Values
        that fail coercion are still errors. Only meaningful when ``return_type`` is
        :attr:`ReturnType.MODEL_INSTANCE`. Typer_ rejects unions of two or more
        concrete types (``User | str``), though ``| None`` is fine, so keep the
        parameter annotated with the model class and check the type of the value
        at runtime:

    .. code-block:: python

        def handle(
            self,
            user: t.Annotated[
                User,
                typer.Argument(
                    parser=ModelObjectParser(
                        User, lookup_field="email", return_lookup_on_miss=True
                    )
                ),
            ],
        ):
            if isinstance(user, str):
                user = User.objects.create(email=user)
    """

    error_handler = t.Callable[[type[models.Model], str, Exception], t.Any]

    model_cls: type[models.Model]
    lookup_field: str
    case_insensitive: bool = False
    on_error: error_handler | None = None
    return_type: ReturnType = ReturnType.MODEL_INSTANCE
    return_lookup_on_miss: bool = False

    _lookup: str = ""
    _field: models.Field
    _completer: ModelObjectCompleter

    __name__: str = "model"  # typer internals expect this

    def _get_metavar(self) -> str:
        if isinstance(self._field, models.IntegerField):
            return "int"
        elif isinstance(self._field, models.EmailField):
            return "email"
        elif isinstance(self._field, models.URLField):
            return "url"
        elif isinstance(self._field, models.GenericIPAddressField):
            return "IPv4|IPv6"
        elif isinstance(self._field, models.UUIDField):
            return "uuid"
        elif isinstance(self._field, (models.FloatField, models.DecimalField)):
            return "float"
        elif isinstance(self._field, (models.FileField, models.FilePathField)):
            return "path"
        elif isinstance(self._field, models.DateTimeField):
            return "ISO 8601"
        elif isinstance(self._field, models.DateField):
            return "YYYY-MM-DD"
        elif isinstance(self._field, models.TimeField):
            return "HH:MM:SS.sss"
        elif isinstance(self._field, models.DurationField):
            return "ISO 8601"
        return "txt"

    def __init__(
        self,
        model_cls: type[models.Model],
        lookup_field: str | None = None,
        case_insensitive: bool = case_insensitive,
        on_error: error_handler | None = on_error,
        return_type: ReturnType = return_type,
        return_lookup_on_miss: bool = return_lookup_on_miss,
    ):
        from django.contrib.contenttypes.fields import GenericForeignKey

        self.model_cls = model_cls
        self.lookup_field = str(
            lookup_field or getattr(self.model_cls._meta.pk, "name", "id")
        )
        self.on_error = on_error
        self.return_type = return_type
        self.return_lookup_on_miss = return_lookup_on_miss
        self.case_insensitive = case_insensitive
        field = self.model_cls._meta.get_field(self.lookup_field)
        assert not isinstance(field, (models.ForeignObjectRel, GenericForeignKey)), (
            f"{field.__class__.__name__} is not a supported lookup field."
        )
        self._field = field
        if self.case_insensitive and "iexact" in self._field.get_lookups():
            self._lookup = "__iexact"
        self.__name__ = self._get_metavar()

    def convert(self, value: t.Any, param: Parameter | None, ctx: Context | None):
        """
        Invoke the parsing action on the given string. If the value is
        already a model instance of the expected type the value will
        be returned. Otherwise the value will be treated as a value to query
        against the lookup_field. If no model object is found the lookup value
        is returned when ``return_lookup_on_miss`` is set, otherwise the error
        handler is invoked if one was provided.

        :param value: The value to parse.
        :param param: The parameter that the value is associated with.
        :param ctx: The context of the command.
        :raises CommandError: If the lookup fails and no error handler is
            provided.
        """
        original = value
        try:
            if not isinstance(value, str):
                return value
            elif isinstance(self._field, models.UUIDField):
                uuid = ""
                for char in value:
                    if char.isalnum():
                        uuid += char
                value = UUID(uuid)
            elif isinstance(self._field, models.DateTimeField):
                value = datetime.fromisoformat(value)
            elif isinstance(self._field, models.DateField):
                value = date.fromisoformat(value)
            elif isinstance(self._field, models.TimeField):
                value = time.fromisoformat(value)
            elif isinstance(self._field, models.DurationField):
                from django_typer.utils import parse_iso_duration

                parsed, ambiguous = parse_iso_duration(value)
                if ambiguous:
                    raise ValueError(f"Invalid duration: {value}")
                value = parsed
            if self.return_type is ReturnType.QUERY_SET:
                return self.model_cls.objects.filter(
                    **{f"{self.lookup_field}{self._lookup}": value}
                )
            elif self.return_type is ReturnType.FIELD_VALUE:
                return value
            return self.model_cls.objects.get(
                **{f"{self.lookup_field}{self._lookup}": value}
            )
        except ValueError as err:
            if self.on_error:
                return self.on_error(self.model_cls, original, err)
            raise CommandError(
                f"{original} is not a valid {self._field.__class__.__name__}"
            ) from err
        except self.model_cls.DoesNotExist as err:
            if self.return_lookup_on_miss:
                return value
            if self.on_error:
                return self.on_error(self.model_cls, original, err)
            raise CommandError(
                f"{self.model_cls.__name__}.{self.lookup_field}='{original}' does not "
                "exist!"
            ) from err
