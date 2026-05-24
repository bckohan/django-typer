import inspect
import sys
import typing as t
from collections import deque
from copy import copy, deepcopy
from functools import cached_property, lru_cache
from importlib import import_module
from pathlib import Path
from types import MethodType, SimpleNamespace

import click
from click.shell_completion import CompletionItem
from django.core.management import get_commands
from django.core.management.base import BaseCommand, CommandError
from django.core.management.base import OutputWrapper as BaseOutputWrapper
from django.core.management.color import Style as ColorStyle
from django.utils.functional import Promise, classproperty

from django_typer import patch

patch.apply()

import typer  # noqa: E402
import typer.core  # noqa: E402
from typer.core import TyperCommand as CoreTyperCommand  # noqa: E402
from typer.core import TyperGroup as CoreTyperGroup  # noqa: E402
from typer.main import get_command as get_typer_command  # noqa: E402
from typer.main import get_params_convertors_ctx_param_name_from_function  # noqa: E402
from typer.models import Context as TyperContext  # noqa: E402
from typer.models import Default, DefaultPlaceholder  # noqa: E402

from ..config import show_locals, traceback_config, use_rich_tracebacks  # noqa: E402
from ..types import (  # noqa: E402
    ForceColor,
    HideLocals,
    NoColor,
    PythonPath,
    Settings,
    ShowLocals,
    SkipChecks,
    Traceback,
    Verbosity,
    Version,
)
from ..utils import (  # noqa: E402
    _command_context,
    _load_command_plugins,
    accepted_kwargs,
    called_from_command_definition,
    called_from_module,
    get_current_command,
    get_usage_script,
    is_method,
    rich_installed,
    with_typehint,
)

DEFAULT_MARKUP_MODE = getattr(typer.core, "DEFAULT_MARKUP_MODE", None)


__all__ = [
    "TyperCommand",
    "CommandNode",
    "BoundProxy",
    "Typer",
    "DjangoTyperMixin",
    "DTCommand",
    "DTGroup",
    "Context",
    "initialize",
    "finalize",
    "callback",
    "command",
    "group",
    "get_command",
]

P = t.ParamSpec("P")
P2 = t.ParamSpec("P2")
R = t.TypeVar("R")
R2 = t.TypeVar("R2")
C = t.TypeVar("C", bound=BaseCommand)
TC = t.TypeVar("TC", bound="TyperCommand")

_CACHE_KEY = "_register_typer"


@t.overload  # pragma: no cover
def get_command(
    command_name: str,
    stdout: t.Optional[t.IO[str]] = None,
    stderr: t.Optional[t.IO[str]] = None,
    no_color: bool = False,
    force_color: bool = False,
    **kwargs: t.Any,
) -> BaseCommand: ...


@t.overload  # pragma: no cover
# mypy seems to break on this one, but this is correct
def get_command(
    command_name: str,
    cmd_type: t.Type[C],
    stdout: t.Optional[t.IO[str]] = None,
    stderr: t.Optional[t.IO[str]] = None,
    no_color: bool = False,
    force_color: bool = False,
    **kwargs: t.Any,
) -> C: ...


@t.overload  # pragma: no cover
def get_command(
    command_name: str,
    path0: str,
    *path: str,
    stdout: t.Optional[t.IO[str]] = None,
    stderr: t.Optional[t.IO[str]] = None,
    no_color: bool = False,
    force_color: bool = False,
    **kwargs: t.Any,
) -> MethodType: ...


def get_command(
    command_name,
    *path,
    stdout=None,
    stderr=None,
    no_color: bool = False,
    force_color: bool = False,
    **kwargs: t.Any,
):
    """
    Get a Django_ command by its name and instantiate it with the provided options. This
    will work for subclasses of :class:`~django.core.management.BaseCommand` as well as
    for :class:`~django_typer.management.TyperCommand` subclasses. If subcommands are
    listed for a :class:`~django_typer.management.TyperCommand`, the method that
    corresponds to the command name will be returned. This method may then be invoked
    directly. If no subcommands are listed the command instance will be returned.

    Using ``get_command`` to fetch a command instance and then invoking the instance as
    a callable is the preferred way to execute
    :class:`~django_typer.management.TyperCommand` commands from code. The arguments and
    options passed to the __call__ method of the command should be fully resolved to
    their expected parameter types before being passed to the command. The
    :func:`~django.core.management.call_command` interface also works, but arguments
    must be unparsed strings and options may be either strings or resolved parameter
    types. The following is more efficient than
    :func:`~django.core.management.call_command`.

    .. code-block:: python

        basic = get_command('basic')
        result = basic(
            arg1,
            arg2,
            arg3=0.5,
            arg4=1
        )

    Subcommands may be retrieved by passing the subcommand names as additional
    arguments:

    .. code-block:: python

        divide = get_command('hierarchy', 'math', 'divide')
        result = divide(10, 2)

    When fetching an entire :class:`~django_typer.management.TyperCommand` (i.e. no
    group or subcommand path), you may supply the type of the expected TyperCommand as
    the second argument. This will allow the type system to infer the correct return
    type:

    .. code-block:: python

        from myapp.management.commands import Command as Hierarchy
        hierarchy: Hierarchy = get_command('hierarchy', Hierarchy)

    .. note::

        If get_command fetches a :class:`~django.core.management.BaseCommand` that does
        not implement __call__ get_command will make the command callable by adding a
        __call__ method that calls the
        :meth:`~django.core.management.BaseCommand.handle` method of the
        :class:`~django.core.management.BaseCommand`. This allows you to call the
        command like ``get_command("command")()`` with confidence.

    :param command_name: the name of the command to get
    :param path: the path walking down the group/command tree
    :param stdout: the stdout stream to use
    :param stderr: the stderr stream to use
    :param no_color: whether to disable color
    :param force_color: whether to force color
    :param kwargs: t.Any other parameters to pass through to the command constructor
    :raises CommandError: if the command is not found
    :raises LookupError: if the subcommand is not found
    """
    try:
        module = import_module(
            f"{get_commands()[command_name]}.management.commands.{command_name}"
        )
    except (KeyError, ModuleNotFoundError) as err:
        raise CommandError(f"Unknown command: {command_name}") from err
    cmd: BaseCommand = module.Command(
        stdout=stdout,
        stderr=stderr,
        no_color=no_color,
        force_color=force_color,
        **kwargs,
    )
    if path and (isinstance(path[0], str) or len(path) > 1):
        return t.cast(TyperCommand, cmd).get_subcommand(*path).callback

    if not hasattr(cmd, "__call__"):
        setattr(
            cmd.__class__,
            "__call__",
            lambda self, *args, **options: self.handle(*args, **options),
        )

    return cmd


def _common_options(  # pyright: ignore[reportRedeclaration]
    version: Version = False,
    verbosity: Verbosity = 1,
    settings: Settings = "",
    pythonpath: PythonPath = None,
    traceback: Traceback = False,
    show_locals: ShowLocals = False,
    hide_locals: HideLocals = False,
    no_color: NoColor = False,
    force_color: ForceColor = False,
    skip_checks: SkipChecks = False,
) -> None:
    """
    Common django options.
    """


# cache common params to avoid this extra work on every command
# we cant resolve these at module scope because translations break it
_common_params: t.Sequence[t.Union[click.Argument, click.Option]] = []


def _normalize_suppressed_arguments(
    command: t.Union[t.Type["TyperCommand"], "TyperCommand"],
) -> t.Set[str]:
    suppressed = set()
    if command.suppressed_base_arguments:
        suppressed = set(
            [
                arg.lstrip("--").replace("-", "_")
                for arg in command.suppressed_base_arguments
            ]
        )
    if not rich_installed or not use_rich_tracebacks():
        suppressed.update({"show_locals", "hide_locals"})
    else:
        suppressed.add(
            "show_locals"
            if show_locals() or command.typer_app.pretty_exceptions_show_locals
            else "hide_locals"
        )
    return suppressed


def _get_common_params(
    command: t.Type["TyperCommand"],
) -> t.Sequence[t.Union[click.Argument, click.Option]]:
    """Use typer to convert the common options to click options"""
    global _common_params
    if not _common_params:
        _common_params = get_params_convertors_ctx_param_name_from_function(
            _common_options
        )[0]
    suppressed = _normalize_suppressed_arguments(command)
    return [
        param for param in _common_params if param.name and param.name not in suppressed
    ]


COMMON_DEFAULTS = {
    key: value.default
    for key, value in inspect.signature(_common_options).parameters.items()
}


def _remove_suppressed(
    command: "TyperCommand", params: t.Dict[str, t.Any], manual: t.Set[str] = set()
) -> t.Dict[str, t.Any]:
    suppressed = _normalize_suppressed_arguments(command)
    return {k: v for k, v in params.items() if k not in suppressed or k in manual}


class _ParsedArgs(SimpleNamespace):
    """
    Emulate the argparse.Namespace class so that we can pass the parsed arguments
    into the BaseCommand infrastructure in the way it expects.
    """

    def __init__(self, args: t.Sequence[t.Any], **kwargs: t.Any):
        super().__init__(**kwargs)
        self.args = args
        self.traceback = kwargs.get("traceback", TyperCommand._traceback)
        if not hasattr(self, "pythonpath"):
            self.pythonpath = None
        if not hasattr(self, "settings"):
            self.settings = None

    def _get_kwargs(self):
        return vars(self)


class Context(TyperContext):
    """
    An extension of the
    :class:`click.Context` class that adds a reference to the
    :class:`~django_typer.management.TyperCommand` instance so that the Django_ command
    can be accessed from within :doc:`click <click:click-concepts>` and Typer_ callbacks that take a context. This
    context also keeps track of parameters that were supplied to
    :func:`~django.core.management.call_command`.
    """

    django_command: "TyperCommand"
    children: t.List["Context"]
    _supplied_params: t.Dict[str, t.Any]

    parent: "Context"

    class ParamDict(dict):
        """
        An extension of dict we use to block updates to parameters that were supplied
        when the command was invoked via :func:`~django.core.management.call_command`.
        This complexity is introduced by the hybrid parsing and option passing inherent
        to :func:`~django.core.management.call_command`.
        """

        supplied: t.Sequence[str]

        def __init__(self, *args, supplied: t.Sequence[str]):
            super().__init__(*args)
            self.supplied = supplied

        def __setitem__(self, key, value):
            if key not in self.supplied:
                super().__setitem__(key, value)

    @property
    def supplied_params(self) -> t.Dict[str, t.Any]:
        """
        Get the parameters that were supplied when the command was invoked via
        :func:`~django.core.management.call_command`, only the root context has these.
        """
        if self.parent:
            return self.parent.supplied_params
        return getattr(self, "_supplied_params", {})

    def __init__(
        self,
        command: click.Command,
        parent: t.Optional["Context"] = None,
        django_command: t.Optional["TyperCommand"] = None,
        supplied_params: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs: t.Any,
    ):
        super().__init__(command, parent=parent, **kwargs)
        if django_command:
            self.django_command = django_command
            if supplied_params:
                # if we're at the top level, default django parameters that
                # were suppressed may have been injected into execute() and
                # wound up here. We remove them to keep the interface honest
                supplied_params = _remove_suppressed(
                    self.django_command,
                    supplied_params,
                    {
                        param.name
                        for param in get_typer_command(
                            self.django_command.typer_app
                        ).params
                        if param.name
                    },
                )
        else:
            assert parent
            self.django_command = parent.django_command

        if supplied_params:
            self._supplied_params = supplied_params

        self.params = self.ParamDict(
            {**self.params, **self.supplied_params},
            supplied=list(self.supplied_params.keys()),
        )
        self.children = []
        if parent:
            parent.children.append(self)


class DjangoTyperMixin(with_typehint(CoreTyperGroup)):  # type: ignore[misc]
    """
    A mixin we use to add additional needed contextual awareness to click Commands
    and Groups.
    """

    context_class: t.Type[click.Context] = Context
    django_command: t.Type["TyperCommand"]
    _callback: t.Optional[t.Callable[..., t.Any]] = None
    _callback_is_method: t.Optional[bool] = None
    common_init: bool = False

    @property
    def no_callback(self) -> bool:
        """Returns false if no callback was registered at the root django command."""
        return bool(
            getattr(self, "django_command", None)
            and not self.django_command.typer_app.registered_callback
        )

    @property
    def is_method(self) -> t.Optional[bool]:
        if self._callback_is_method is None:
            self._callback_is_method = is_method(self._callback)
        return self._callback_is_method

    class Converter:
        """
        Because of the way the BaseCommand forces parsing to be done in a separate
        first step, type casting of input strings to the correct types will have
        sometimes happened already. We use this class to avoid double type casting.

        An alternative approach might be to flag converted values - but there does
        not seem to be a good approach to do this given how deep in the click
        infrastructure the conversion happens.
        """

    def get_params(self, ctx: click.Context) -> t.List[click.Parameter]:
        """
        We override get_params to check to make sure that prompt_required is not set for
        parameters that have already been prompted for during the initial parse phase.
        We have to do this because of we're stuffing the click infrastructure into the
        django infrastructure and the django infrastructure forces a two step parse
        process whereas click does not easily support separating these.

        There may be a more sound approach than this?
        """
        modified = []
        params = super().get_params(ctx)
        for param in params:
            if (
                getattr(param, "prompt", None)
                and getattr(param, "prompt_required", False)
                and getattr(ctx, "supplied_params", {}).get(param.name, None)
            ):
                param = copy(param)
                setattr(param, "prompt_required", False)
                param.required = False
            modified.append(param)
        return modified

    def shell_complete(
        self, ctx: click.Context, incomplete: str
    ) -> t.List[CompletionItem]:
        """
        By default if the incomplete string is a space and there are no completions
        the click infrastructure will return _files. We'd rather return parameters
        for the command if there are any available.
        """
        completions = super().shell_complete(ctx, incomplete)
        if not completions and (incomplete.isspace() or not incomplete):
            completions = super().shell_complete(
                ctx, min(getattr(ctx, "_opt_prefixes", [""]))
            )
        return completions

    def common_params(self) -> t.Sequence[t.Union[click.Argument, click.Option]]:
        """
        Add the common parameters to this group only if this group is the root
        command's user specified initialize callback.
        """
        return (
            _get_common_params(self.django_command)
            if self.common_init or self.no_callback
            else []
        )

    def __init__(
        self,
        *args,
        callback: t.Optional[t.Callable[..., t.Any]],
        params: t.Optional[t.List[click.Parameter]] = None,
        **kwargs: t.Any,
    ):
        params = params or []
        self._callback = callback
        expected = [
            param.name for param in params[1 if self.is_method else 0 :] if param.name
        ]

        def call_with_self(*args, **kwargs):
            if not callback:
                return
            ctx = t.cast(Context, click.get_current_context())
            return callback(
                *args,
                **{
                    # we could call param.process_value() here to allow named
                    # parameters to be passed as their unparsed string values,
                    # we don't because this forces some weird idempotency on custom
                    # parsers that might make errors more frequent for users and also
                    # this would be inconsistent with call_command behavior for
                    # BaseCommands which expect the parsed values to be passed by name.
                    # Unparsed values can always be passed as argument strings.
                    param: val
                    for param, val in kwargs.items()
                    if param in expected
                },
                **(
                    {str(params[0].name): getattr(ctx, "django_command", None)}
                    if self.is_method
                    else {}
                ),
            )

        super().__init__(
            *args,
            params=[
                *(params[1:] if self.is_method else params),
                *[
                    param
                    for param in self.common_params()
                    if param.name not in expected
                ],
            ],
            callback=call_with_self,
            **kwargs,
        )


class DTCommand(DjangoTyperMixin, CoreTyperCommand):
    """
    This class extends the ``TyperCommand`` class to work with the django-typer
    interfaces. If you need to add functionality to the command class - you should
    inherit from this class. You can then pass your custom class to the
    :func:`~django_typer.management.command` decorators using the cls parameter.

    .. code-block:: python

        from django_typer import TyperCommand, DTCommand, command

        class CustomCommand(DTCommand):
            ...

        class Command(TyperCommand):

            @command(cls=CustomCommand)
            def handle(self):
                ...


    See :doc:`click:commands` for more information.
    """


class DTGroup(DjangoTyperMixin, CoreTyperGroup):
    """
    This class extends the TyperGroup class to work with the django-typer interfaces.
    If you need to add functionality to the group class you should inherit from this
    class. You can then pass your custom class to the
    :func:`~django_typer.management.command` decorators using the cls parameter.

    .. code-block:: python

        from django_typer import TyperCommand, DTGroup, group

        class CustomGroup(DTGroup):
            ...

        class Command(TyperCommand):

            @group(cls=CustomGroup)
            def grp(self):
                ...

    See `click docs on custom groups
    <https://click.palletsprojects.com/en/latest/commands/#custom-groups>`_
    and :doc:`click:advanced` for more information.
    """

    def list_commands(self, ctx: click.Context) -> t.List[str]:
        """
        Do our best to list commands in definition order.
        """
        cmds = list(self.commands.keys())
        ordered = []
        for defined in getattr(self.django_command, "_defined_order", []):
            if defined in cmds:
                ordered.append(defined)
                cmds.remove(defined)
        return ordered + cmds

    def invoke(self, ctx: click.Context) -> t.Any:
        """
        Override click.Group.invoke to include the group callback's return value in
        the results list when chain=True and invoke_without_command=True. In Click's
        default implementation the group callback's return is discarded in chain mode;
        here we prepend it to the subcommand results so finalize handlers can see it.

        Hopefully this gets fixed upstream and we can remove this override.
        """
        if not self.chain or not self.invoke_without_command:
            return super().invoke(ctx)

        def _process_result(value: t.Any) -> t.Any:
            if self._result_callback is not None:
                value = ctx.invoke(self._result_callback, value, **ctx.params)
            return value

        # No subcommands provided — run group callback and pass its return as a
        # single-element list (or empty list if it returned None) to the finalizer.
        prot_args = getattr(ctx, "_protected_args", None) or getattr(
            ctx, "protected_args", None
        )
        if not prot_args:
            with ctx:
                group_rv = click.Command.invoke(self, ctx)
                return _process_result([group_rv] if group_rv is not None else [])

        args = [*prot_args, *ctx.args]
        ctx.args = []
        if hasattr(ctx, "_protected_args"):
            ctx._protected_args = []
        else:
            # remove when support for click 8.1.8 dropped
            ctx.protected_args = []  # type: ignore

        with ctx:
            ctx.invoked_subcommand = "*" if args else None
            group_rv = click.Command.invoke(self, ctx)

            contexts = []
            while args:
                cmd_name, cmd, args = self.resolve_command(ctx, args)
                assert cmd is not None
                sub_ctx = cmd.make_context(
                    cmd_name,
                    args,
                    parent=ctx,
                    allow_extra_args=True,
                    allow_interspersed_args=False,
                )
                contexts.append(sub_ctx)
                args, sub_ctx.args = sub_ctx.args, []

            rv = [group_rv] if group_rv is not None else []
            for sub_ctx in contexts:
                with sub_ctx:
                    rv.append(sub_ctx.command.invoke(sub_ctx))
            return _process_result(rv)


# staticmethod objects are not picklable which causes problems with deepcopy
# hence the following mishegoss


class Finalizer(t.Generic[P, R]):
    """
    A class that wraps a finalizer function and makes it callable while passing the
    django command instance if expected.
    """

    finalizer: t.Callable[P, R]
    is_method: bool

    @property
    def name(self):
        return self.finalizer.__name__

    def __init__(self, finalizer: t.Callable[P, R]):
        self.finalizer = finalizer
        self.is_method = bool(is_method(finalizer))

    def __call__(
        self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        if self.is_method:
            cmd = kwargs.pop("_command", None) or (
                getattr(
                    t.cast(Context, click.get_current_context(silent=True)),
                    "django_command",
                    None,
                )
                or get_current_command()
            )
            args = [cmd, *args]  # type: ignore
        return self.finalizer(*args, **accepted_kwargs(self.finalizer, kwargs))


@t.overload  # pragma: no cover
def _check_static(
    func: typer.models.CommandFunctionType,
) -> typer.models.CommandFunctionType: ...


@t.overload  # pragma: no cover
def _check_static(func: None) -> None: ...


def _check_static(func):
    """
    Check if a function is a staticmethod and return it if it is otherwise make
    it static if it should be but isn't.
    """
    if func and not is_method(func) and not isinstance(func, staticmethod):
        return staticmethod(func)
    return func


@t.overload  # pragma: no cover
def _strip_static(func: t.Callable[P, R]) -> t.Callable[P, R]: ...


@t.overload  # pragma: no cover
def _strip_static(func: None) -> None: ...


def _strip_static(func: t.Optional[t.Callable[P, R]]) -> t.Optional[t.Callable[P, R]]:
    """
    Strip the staticmethod wrapper from a function if it is present.
    """
    ret = getattr(func, "__func__", func)
    return ret


def _cache_initializer(
    callback: t.Callable[..., t.Any],
    common_init: bool,
    help: t.Optional[t.Union[str, Promise]] = Default(None),
    cls: t.Type[DTGroup] = DTGroup,
    **kwargs: t.Any,
):
    def register(
        cmd: t.Type["TyperCommand"],
        _help: t.Optional[t.Union[str, Promise]] = Default(None),
        **extra,
    ):
        extra.pop("_name", None)
        return cmd.typer_app.callback(
            cls=type(
                "_Initializer",
                (cls,),
                {"django_command": cmd, "common_init": common_init},
            ),
            help=cmd.typer_app.info.help or help or _help,
            **kwargs,
            **extra,
        )(_strip_static(callback))

    setattr(callback, _CACHE_KEY, register)


def _cache_finalizer(callback: t.Callable[..., t.Any]):
    def register(cmd: t.Type["TyperCommand"]):
        finalizer = Finalizer(_strip_static(callback))
        cmd.typer_app.info.result_callback = finalizer

    setattr(callback, _CACHE_KEY, register)


def _cache_command(
    callback: t.Callable[..., t.Any],
    name: t.Optional[str] = None,
    help: t.Optional[t.Union[str, Promise]] = None,
    cls: t.Type[DTCommand] = DTCommand,
    **kwargs: t.Any,
):
    def register(
        cmd: t.Type["TyperCommand"],
        _name: t.Optional[str] = None,
        _help: t.Optional[t.Union[str, Promise]] = None,
        **extra,
    ):
        return cmd.typer_app.command(
            name=name or _name,
            cls=type("_Command", (cls,), {"django_command": cmd}),
            help=help or _help or None,
            **kwargs,
            **extra,
        )(_strip_static(callback))

    setattr(callback, _CACHE_KEY, register)


TyperFunction = t.Union[
    "Typer[P, R]",
    typer.models.CommandInfo,
    typer.models.TyperInfo,
    t.Callable[..., t.Any],
]


def _get_direct_function(
    obj: "TyperCommand",
    app_node: TyperFunction,
):
    """
    Get a direct callable function bound to the given object if it is not static held by
    the given Typer instance or TyperInfo instance.
    """
    if isinstance(app_node, Typer):
        method = app_node.is_method
        cb = getattr(app_node.registered_callback, "callback", app_node.info.callback)
    elif cb := getattr(app_node, "callback", None):
        method = is_method(cb)
    else:
        assert callable(app_node)
        cb = app_node
        method = is_method(cb)
    assert cb
    return MethodType(cb, obj) if method else staticmethod(cb)


class AppFactory(type):
    """
    A metaclass used to define/set Command classes into the defining module when
    the Typer-like functional interface is used.
    """

    def __call__(self, *args, **kwargs: t.Any) -> "Typer":
        if called_from_module():
            frame = inspect.currentframe()
            cmd_module = inspect.getmodule(frame.f_back) if frame else None
            if cmd_module and not hasattr(cmd_module, "Command"):

                class Command(
                    TyperCommand,
                    name=kwargs.pop("name", None) or cmd_module.__name__.split(".")[-1],
                    **kwargs,
                    typer_app=args[0] if args else None,
                ):
                    pass

                # spoof it so hard
                Command.__module__ = cmd_module.__name__
                Command.__qualname__ = f"{cmd_module.__name__}.Command"
                setattr(cmd_module, "Command", Command)
                return Command.typer_app
            else:
                return Typer(**kwargs)

        return super().__call__(*args, **kwargs)


class Typer(typer.Typer, t.Generic[P, R], metaclass=AppFactory):
    """
    Typer_ adds additional groups of commands by adding Typer_ apps to parent
    Typer_ apps. This class extends the ``typer.Typer`` class so that we can add
    the additional information necessary to attach this app to the root app
    and other groups specified on the django command.

    :param name: the name of the class being created
    :param bases: the base classes of the class being created
    :param attrs: the attributes of the class being created
    :param cls: The class to use as the core typer group wrapper
    :param invoke_without_command: whether to invoke the group callback if no command
        was specified.
    :param no_args_is_help: whether to show the help if no arguments are provided
    :param subcommand_metavar: the metavar to use for subcommands in the help output
    :param chain: whether to chain commands, this allows multiple commands from the
        group to be specified and run in order sequentially in one call from the command
        line.
    :param result_callback: a callback to invoke with the result of the command
    :param context_settings: the click context settings to use - see
        :class:`click.Context`.
    :param help: the help string to use, defaults to the function docstring, if you need
        to translate the help you should use the help kwarg instead because docstrings
        will not be translated.
    :param epilog: the epilog to use in the help output
    :param short_help: the short help to use in the help output
    :param options_metavar: the metavar to use for options in the help output
    :param add_help_option: whether to add the help option to the command
    :param hidden: whether to hide this group from the help output
    :param deprecated: show a deprecation warning
    :param rich_markup_mode: the rich markup mode to use - if rich is installed
        this can be used to enable rich markup or Markdown in the help output. Can
        be "markdown", "rich" or None to disable markup rendering.
    :param rich_help_panel: the rich help panel to use - if rich is installed
        this can be used to group commands into panels in the help output.
    :param pretty_exceptions_enable: whether to enable pretty exceptions - if rich is
        installed this can be used to enable pretty exception rendering. This will
        default to on if the traceback configuration settings installs the rich
        traceback handler. This allows tracebacks to be configured by the user on a
        per deployment basis in the settings file. We therefore do not advise
        hardcoding this value.
    :param pretty_exceptions_show_locals: whether to show local variables in pretty
        exceptions - if rich is installed. This will default to the 'show_locals'
        setting in the traceback configuration setting (on by default). This allows
        tracebacks to be configured by the user on a per deployment basis in the
        settings file. We therefore do not advise hardcoding this value.
    :param pretty_exceptions_short: whether to show short tracebacks in pretty
        exceptions - if rich is installed. This will default to the 'short' setting
        in the traceback configuration setting (off by default). This allows tracebacks
        to be configured by the user on a per deployment basis in the settings file. We
        therefore do not advise hardcoding this value.
    """

    parent: t.Optional["Typer"] = None

    _django_command: t.Optional[t.Type["TyperCommand"]] = None

    # these aren't defined on the super class which messes up __getattr__
    registered_groups: t.List[typer.models.TyperInfo] = []
    registered_commands: t.List[typer.models.CommandInfo] = []
    registered_callback: t.Optional[typer.models.TyperInfo] = None

    is_method: t.Optional[bool] = None
    top_level: bool = False

    @property
    def django_command(self) -> t.Optional[t.Type["TyperCommand"]]:
        return self._django_command or getattr(self.parent, "django_command", None)

    @django_command.setter
    def django_command(self, cmd: t.Optional[t.Type["TyperCommand"]]):
        self._django_command = cmd

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return super().__call__(*args, **kwargs)

    def __get__(self, obj, _=None) -> "Typer[P, R]":
        """
        Our Typer app wrapper also doubles as a descriptor, so when
        it is accessed on the instance, we return the wrapped function
        so it may be called directly - but when accessed on the class
        the app itself is returned so it can modified by other decorators
        on the class and subclasses.
        """
        if isinstance(obj, TyperCommand):
            return t.cast(Typer[P, R], BoundProxy(obj, self))
        return self

    def __getattr__(self, name: str) -> t.Any:
        for cmd in self.registered_commands:
            assert cmd.callback
            if name in _names(cmd):
                return cmd
        for grp in self.registered_groups:
            cmd_grp = t.cast(Typer, grp.typer_instance)
            assert cmd_grp
            if name in _names(cmd_grp):
                return cmd_grp
        raise AttributeError(
            "{cls} object has no attribute {name}".format(
                cls=self.__class__.__name__, name=name
            )
        )

    def __init__(
        self,
        *args,
        name: t.Optional[str] = Default(None),
        cls: t.Optional[t.Type[DTGroup]] = DTGroup,
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: t.Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        # Command
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
        callback: t.Optional[t.Callable[t.Concatenate[TC, P], R]] = Default(None),
        help: t.Optional[t.Union[str, Promise]] = Default(None),
        epilog: t.Optional[str] = Default(None),
        short_help: t.Optional[t.Union[str, Promise]] = Default(None),
        options_metavar: str = Default("[OPTIONS]"),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = Default(False),
        add_completion: bool = True,
        # Rich settings
        rich_markup_mode: typer.core.MarkupMode = DEFAULT_MARKUP_MODE,
        rich_help_panel: t.Union[str, None] = Default(None),
        suggest_commands: bool = True,
        pretty_exceptions_enable: bool = True,
        pretty_exceptions_show_locals: bool = False,
        pretty_exceptions_short: bool = True,
        parent: t.Optional["Typer"] = None,
        django_command: t.Optional[t.Type["TyperCommand"]] = None,
        **kwargs: t.Any,
    ):
        assert not args  # should have been removed by metaclass
        self.parent = parent
        self._django_command = django_command
        self.top_level = kwargs.pop("top_level", False)
        typer_app = kwargs.pop("typer_app", None)
        callback = _strip_static(callback)
        if callback:
            self.is_method = is_method(callback)

        super().__init__(
            name=name,
            cls=type(
                "_DTGroup", (cls or DTGroup,), {"django_command": self.django_command}
            ),
            invoke_without_command=invoke_without_command,
            no_args_is_help=no_args_is_help,
            subcommand_metavar=subcommand_metavar,
            chain=chain,
            result_callback=result_callback,
            context_settings=context_settings,
            callback=callback,
            help=t.cast(str, help),
            epilog=epilog,
            short_help=t.cast(str, short_help),
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            hidden=hidden,
            deprecated=deprecated,
            add_completion=add_completion,
            rich_markup_mode=rich_markup_mode,
            rich_help_panel=rich_help_panel,
            suggest_commands=suggest_commands,
            pretty_exceptions_enable=pretty_exceptions_enable,
            pretty_exceptions_show_locals=pretty_exceptions_show_locals,
            pretty_exceptions_short=pretty_exceptions_short,
            **kwargs,
        )
        # if we're copying a supplied typer app, pull in the hierarchy and options
        if typer_app:
            self.registered_callback = typer_app.registered_callback
            self.registered_commands = copy(typer_app.registered_commands)
            self.registered_groups = deepcopy(typer_app.registered_groups)
            self.rich_help_panel = (
                typer_app.rich_help_panel
                if isinstance(self.rich_help_panel, DefaultPlaceholder)
                else self.rich_help_panel
            )
            for param, cfg in vars(self.info).items():
                if isinstance(cfg, DefaultPlaceholder):
                    setattr(self.info, param, getattr(typer_app.info, param))

    def callback(  # type: ignore
        self,
        *,
        cls: t.Type[DTGroup] = DTGroup,
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: t.Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        # Command
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
        help: t.Optional[t.Union[str, Promise]] = Default(None),
        epilog: t.Optional[str] = Default(None),
        short_help: t.Optional[t.Union[str, Promise]] = Default(None),
        options_metavar: t.Optional[str] = Default(None),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = Default(False),
        # Rich settings
        rich_help_panel: t.Union[str, None] = Default(None),
        **kwargs: t.Any,
    ) -> t.Callable[
        [typer.models.CommandFunctionType], typer.models.CommandFunctionType
    ]:
        """"""

        def make_callback(
            func: typer.models.CommandFunctionType,
        ) -> typer.models.CommandFunctionType:
            self.is_method = is_method(func)
            self.registered_callback = typer.models.TyperInfo(
                cls=type(
                    "_Initializer",
                    (cls,),
                    {
                        "django_command": self.django_command,
                        "common_init": self.parent is None,
                    },
                ),
                invoke_without_command=invoke_without_command,
                no_args_is_help=no_args_is_help,
                subcommand_metavar=subcommand_metavar,
                chain=chain,
                result_callback=result_callback,
                context_settings=context_settings,
                name=func.__name__,
                callback=func,
                help=t.cast(str, help),
                epilog=epilog,
                short_help=t.cast(str, short_help),
                options_metavar=(
                    options_metavar or self._info_val_str("options_metavar")
                ),
                add_help_option=add_help_option,
                hidden=hidden,
                deprecated=deprecated,
                rich_help_panel=rich_help_panel,
                **kwargs,
            )
            return _check_static(func)

        return make_callback

    initialize = callback  # allow initialize as an alias for callback

    def command(  # type: ignore
        self,
        name: t.Optional[str] = None,
        *,
        cls: t.Type[DTCommand] = DTCommand,
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = None,
        help: t.Optional[t.Union[str, Promise]] = None,
        epilog: t.Optional[str] = None,
        short_help: t.Optional[t.Union[str, Promise]] = None,
        options_metavar: t.Optional[str] = Default(None),
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
        # Rich settings
        rich_help_panel: t.Union[str, None] = Default(None),
        **kwargs: t.Any,
    ) -> t.Callable[[t.Callable[P2, R2]], t.Callable[P2, R2]]:
        """
        A function decorator that creates a new command and attaches it to this group.
        This is a passthrough to ``Typer.command()`` and the options are the same,
        except we swap the default command class for our wrapper.

        The decorated function is the command function. It may also be invoked directly
        as a method from an instance of the django command class.

        .. code-block:: python

            class Command(TyperCommand):

                @group()
                def group1(self):
                    pass

                @group1.command()
                def command1(self):
                    # do stuff here

        .. note::

            If you need to use a different command class you will need to either
            inherit from django-typer or make sure yours is interface compatible with
            our extensions. You shouldn't need to do this though - if the library does
            not do something you need it to please submit an issue.

        :param name: the name of the command (defaults to the name of the decorated
            function)
        :param cls: the command class to use
        :param context_settings: the context settings to use - see
            :class:`click.Context`
        :param help: the help string to use, defaults to the function docstring, if
            you need the help to be translated you should use the help kwarg instead
            because docstrings will not be translated.
        :param epilog: the epilog to use in the help output
        :param short_help: the short help to use in the help output
        :param options_metavar: the metavar to use for options in the help output
        :param add_help_option: whether to add the help option to the command
        :param no_args_is_help: whether to show the help if no arguments are provided
        :param hidden: whether to hide the command from help output
        :param deprecated: show a deprecation warning
        :param rich_help_panel: the rich help panel to use - if rich is installed
            this can be used to group commands into panels in the help output.
        """

        def make_command(func: t.Callable[P2, R2]) -> t.Callable[P2, R2]:
            return _check_static(
                super(Typer, self).command(
                    name=name,
                    cls=type(
                        "_Command", (cls,), {"django_command": self.django_command}
                    ),
                    context_settings=context_settings,
                    help=t.cast(str, help),
                    epilog=epilog,
                    short_help=t.cast(str, short_help),
                    options_metavar=options_metavar,
                    add_help_option=add_help_option,
                    no_args_is_help=no_args_is_help,
                    hidden=hidden,
                    deprecated=deprecated,
                    rich_help_panel=rich_help_panel,
                    **kwargs,
                )(_strip_static(func))
            )

        return make_command

    def add_typer(  # type: ignore
        self,
        typer_instance: "Typer",
        *,
        name: t.Optional[str] = Default(None),
        cls: t.Type[DTGroup] = Default(DTGroup),
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: t.Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        # Command
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
        callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        help: t.Optional[t.Union[str, Promise]] = Default(None),
        epilog: t.Optional[str] = Default(None),
        short_help: t.Optional[t.Union[str, Promise]] = Default(None),
        options_metavar: t.Optional[str] = Default(None),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = False,
        # Rich settings
        rich_help_panel: t.Union[str, None] = Default(None),
        **kwargs: t.Any,
    ) -> None:
        """ """
        typer_instance.parent = self
        typer_instance.django_command = self.django_command

        assert cls  # cls must be interface compatible with DTGroup

        group_class = (
            type(
                "_DTGroup",
                (cls,),
                {"django_command": self.django_command},
            )
            if not isinstance(cls, DefaultPlaceholder)
            else typer_instance.info.cls
        )

        return super().add_typer(
            typer_instance=typer_instance,
            name=name,
            cls=group_class,
            invoke_without_command=invoke_without_command,
            no_args_is_help=no_args_is_help,
            subcommand_metavar=subcommand_metavar,
            chain=chain,
            result_callback=result_callback,
            context_settings=context_settings,
            callback=_strip_static(callback),
            help=t.cast(str, help),
            epilog=epilog,
            short_help=t.cast(str, short_help),
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            hidden=hidden,
            deprecated=deprecated,
            rich_help_panel=rich_help_panel,
            **kwargs,
        )

    @t.no_type_check
    def group(
        self,
        name: t.Optional[str] = Default(None),
        cls: t.Type[DTGroup] = DTGroup,
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: t.Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        # Command
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
        help: t.Optional[t.Union[str, Promise]] = Default(None),
        epilog: t.Optional[str] = Default(None),
        short_help: t.Optional[t.Union[str, Promise]] = Default(None),
        options_metavar: t.Optional[str] = Default(None),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = False,
        # Rich settings
        rich_help_panel: t.Union[str, None] = Default(None),
        **kwargs: t.Any,
    ) -> t.Callable[
        [
            t.Callable[
                t.Concatenate[TC, P2], R2  # pyright: ignore[reportInvalidTypeVarUse]
            ]
        ],
        "Typer[P2, R2]",
    ]:
        """
        Create a new subgroup and attach it to this group. This is like creating a new
        Typer app and adding it to a parent Typer app. The kwargs are passed through
        to the ``Typer()`` constructor.

        .. code-block:: python

            class Command(TyperCommand):

                @group()
                def group1(self):
                    pass

                @group1.group()
                def subgroup(self):
                    # do common group init stuff here

                @subgroup.command(help=_('My command does good stuff!'))
                def subcommand(self):
                    # do command stuff here


        :param name: the name of the group
        :param cls: the group class to use
        :param invoke_without_command: whether to invoke the group callback if no
            command was specified.
        :param no_args_is_help: whether to show the help if no arguments are provided
        :param subcommand_metavar: the metavar to use for subcommands in the help output
        :param chain: whether to chain commands, this allows multiple commands from the
            group to be specified and run in order sequentially in one call from the
            command line.
        :param result_callback: a callback to invoke with the result of the command
        :param context_settings: the click context settings to use - see
            :class:`click.Context`.
        :param help: the help string to use, defaults to the function docstring, if you
            need to translate the help you should use the help kwarg instead because
            docstrings will not be translated.
        :param epilog: the epilog to use in the help output
        :param short_help: the short help to use in the help output
        :param options_metavar: the metavar to use for options in the help output
        :param add_help_option: whether to add the help option to the command
        :param hidden: whether to hide this group from the help output
        :param deprecated: show a deprecation warning
        :param rich_help_panel: the rich help panel to use - if rich is installed
            this can be used to group commands into panels in the help output.
        """
        options_metavar = options_metavar or self._info_val_str("options_metavar")

        def create_app(
            func: t.Callable[t.Concatenate[TC, P2], R2],
        ) -> Typer[P2, R2]:
            grp: Typer[P2, R2] = Typer(  # pyright: ignore[reportAssignmentType]
                name=name or _strip_static(func).__name__.replace("_", "-"),
                cls=type("_DTGroup", (cls,), {"django_command": self.django_command}),
                invoke_without_command=invoke_without_command,
                no_args_is_help=no_args_is_help,
                subcommand_metavar=subcommand_metavar,
                chain=chain,
                result_callback=result_callback,
                callback=func,
                context_settings=context_settings,
                help=help,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                hidden=hidden,
                deprecated=deprecated,
                rich_help_panel=rich_help_panel,
                parent=self,
                **kwargs,
            )
            self.add_typer(
                grp,
                name=name or _strip_static(func).__name__.replace("_", "-"),
                options_metavar=options_metavar,
            )
            return grp

        return create_app

    def finalize(self):
        """
        Add a finalizer callback to collect the results of all commands run as part of
        this command group. This is analogous to the ``result_callback`` on
        ``Typer.add_typer`` but works seamlessly for methods. See
        :ref:`howto_finalizers` for more information.
        """

        def create_finalizer(func: t.Callable[P2, R2]) -> t.Callable[P2, R2]:
            func = _strip_static(func)
            self.info.result_callback = Finalizer(func)
            return func

        return create_finalizer


class BoundProxy(t.Generic[P, R]):
    """
    A helper class that proxies the Typer or command objects and binds them
    to the django command instance.
    """

    command: "TyperCommand"
    proxied: t.Union[TyperFunction, Finalizer]

    def __init__(self, command: "TyperCommand", proxied: TyperFunction):
        self.command = command
        self.proxied = proxied

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if isinstance(self.proxied, Typer) and not self.proxied.parent:
            # if we're calling a top level Typer app we need invoke Typer's call
            return self.proxied(*args, **kwargs)
        elif isinstance(self.proxied, Finalizer):
            return self.proxied(*args, _command=self.command, **kwargs)
        return _get_direct_function(self.command, self.proxied)(*args, **kwargs)

    def __getattr__(self, name: str) -> t.Any:
        """
        If our proxied object __getattr__ returns a Typer or Command object we
        wrap it in a BoundProxy so that it can be called directly as a method
        on the django command instance.
        """
        if hasattr(self.proxied, name):
            attr = getattr(self.proxied, name)
            # want to avoid recursive binding
            if isinstance(attr, (Typer, typer.models.CommandInfo)):
                return BoundProxy(self.command, attr)
            return attr
        elif isinstance(self.proxied, Typer) and isinstance(
            self.proxied.info.result_callback, Finalizer
        ):
            return BoundProxy(self.command, self.proxied.info.result_callback)

        raise AttributeError(
            "{cls} object has no attribute {name}".format(
                cls=self.__class__.__name__, name=name
            )
        )


def initialize(
    *,
    cls: t.Type[DTGroup] = DTGroup,
    invoke_without_command: bool = Default(False),
    no_args_is_help: bool = Default(False),
    subcommand_metavar: t.Optional[str] = Default(None),
    chain: bool = Default(False),
    result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
    # Command
    context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
    help: t.Optional[t.Union[str, Promise]] = Default(None),
    epilog: t.Optional[str] = Default(None),
    short_help: t.Optional[t.Union[str, Promise]] = Default(None),
    options_metavar: t.Optional[str] = Default(None),
    add_help_option: bool = Default(True),
    hidden: bool = Default(False),
    deprecated: bool = Default(False),
    # Rich settings
    rich_help_panel: t.Union[str, None] = Default(None),
    **kwargs: t.Any,
) -> t.Callable[[t.Callable[P2, R2]], t.Callable[P2, R2]]:
    """
    A function decorator that creates a Typer_
    `callback <https://typer.tiangolo.com/tutorial/commands/callback/>`_. This
    decorator wraps the
    `Typer.callback() <https://typer.tiangolo.com/tutorial/commands/callback/>`_
    functionality. We've renamed it to ``initialize()`` because ``callback()`` is
    to general and not intuitive. Callbacks in Typer_ are functions that are invoked
    before a command is invoked and that can accept their own arguments. When an
    ``initialize()`` function is supplied to a django
    :class:`~django_typer.management.TyperCommand` the default Django_ options will be
    added as parameters. You can specify these parameters
    (see :mod:`django_typer.types`) as arguments on the wrapped function if you wish to
    receive them - otherwise they will be intercepted by the base class infrastructure
    and used to their purpose.

    The parameters are passed through to
    `Typer.callback() <https://typer.tiangolo.com/tutorial/commands/callback/>`_

    For example the below command defines two subcommands that both have a common
    initializer that accepts a --precision parameter option:

    .. code-block:: python
        :linenos:
        :caption: management/commands/math.py

        import typing as t
        from typer import Argument, Option
        from django_typer import TyperCommand, initialize, command


        class Command(TyperCommand):

            precision = 2

            @initialize(help="Do some math at the given precision.")
            def init(
                self,
                precision: t.Annotated[
                    int, Option(help="The number of decimal places to output.")
                ] = precision,
            ):
                self.precision = precision

            @command(help="Multiply the given numbers.")
            def multiply(
                self,
                numbers: t.Annotated[
                    t.List[float], Argument(help="The numbers to multiply")
                ],
            ):
                ...

            @command()
            def divide(
                self,
                numerator: t.Annotated[float, Argument(help="The numerator")],
                denominator: t.Annotated[float, Argument(help="The denominator")]
            ):
                ...

    When we run, the command we should provide the --precision option before the
    subcommand:

        .. code-block:: bash

            $ ./manage.py math --precision 5 multiply 2 2.333
            4.66600

    :param name: the name of the callback (defaults to the name of the decorated
        function)
    :param cls: the command class to use - (the
        :func:`~django_typer.management.initialize` function is technically the root
        command group)
    :param invoke_without_command: whether to invoke the callback if no command was
        specified.
    :param no_args_is_help: whether to show the help if no arguments are provided
    :param subcommand_metavar: the metavar to use for subcommands in the help output
    :param chain: whether to chain commands, this allows multiple commands from the
        group to be specified and run in order sequentially in one call from the command
        line.
    :param result_callback: a callback to invoke with the result of the command
    :param context_settings: the click context settings to use - see
        :class:`click.Context`.
    :param help: the help string to use, defaults to the function docstring, if you need
        to translate the help you should use the help kwarg instead because docstrings
        will not be translated.
    :param epilog: the epilog to use in the help output
    :param short_help: the short help to use in the help output
    :param options_metavar: the metavar to use for options in the help output
    :param add_help_option: whether to add the help option to the command
    :param hidden: whether to hide this group from the help output
    :param deprecated: show a deprecation warning
    :param rich_help_panel: the rich help panel to use - if rich is installed
        this can be used to group commands into panels in the help output.
    """

    def make_initializer(func: t.Callable[P2, R2]) -> t.Callable[P2, R2]:
        func = _check_static(func)
        _cache_initializer(
            func,
            common_init=True,
            cls=cls,
            invoke_without_command=invoke_without_command,
            subcommand_metavar=subcommand_metavar,
            chain=chain,
            result_callback=result_callback,
            context_settings=context_settings,
            help=help,
            epilog=epilog,
            short_help=short_help,
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            no_args_is_help=no_args_is_help,
            hidden=hidden,
            deprecated=deprecated,
            rich_help_panel=rich_help_panel,
            **kwargs,
        )
        return func

    return make_initializer


callback = initialize  # allow callback as an alias


def finalize() -> t.Callable[[t.Callable[P2, R2]], t.Callable[P2, R2]]:
    """
    Attach a callback function that collects and finalizes results returned
    from any invoked subcommands. This is a wrapper around typer's result_callback that
    extends it to work as a method and for non-compound commands.

    .. code-block:: python

        class Command(TyperCommand, chain=True):

            @finalize()
            def collect(self, results: t.List[str]):
                return ", ".join(results)

            @command()
            def cmd1(self):
                return "result1"

            @command()
            def cmd2(self):
                return "result2"

    .. code-block:: bash

        $ ./manage.py command cmd1 cmd2
        result1, result2

    The callback must at minimum accept a single argument that is either a list of
    results or a singular result if the command is not compound. The callback may
    optionally accept named arguments that correspond to parameters at the given
    command group scope. These parameters will also be available on the current
    context.
    """

    def make_finalizer(func: t.Callable[P2, R2]) -> t.Callable[P2, R2]:
        func = _check_static(func)
        _cache_finalizer(func)
        return func

    return make_finalizer


def command(
    name: t.Optional[str] = None,
    *,
    cls: t.Type[DTCommand] = DTCommand,
    context_settings: t.Optional[t.Dict[t.Any, t.Any]] = None,
    help: t.Optional[t.Union[str, Promise]] = None,
    epilog: t.Optional[str] = None,
    short_help: t.Optional[t.Union[str, Promise]] = None,
    options_metavar: t.Optional[str] = Default(None),
    add_help_option: bool = True,
    no_args_is_help: bool = False,
    hidden: bool = False,
    deprecated: bool = False,
    # Rich settings
    rich_help_panel: t.Union[str, None] = Default(None),
    **kwargs: t.Any,
) -> t.Callable[[t.Callable[P, R]], t.Callable[P, R]]:
    """
    A function decorator that creates a new command and attaches it to the root
    command group. This is a passthrough to
    `Typer.command() <https://typer.tiangolo.com/tutorial/commands/>`_ and the
    options are the same, except we swap the default command class for our wrapper.

    We do not need to decorate :meth:`~django.core.management.BaseCommand.handle`
    functions with this decorator, but if we want to pass options upstream to typer we
    can:

    .. code-block:: python

        class Command(TyperCommand):

            @command(epilog="This is the epilog for the command.")
            def handle(self):
                ...

    We can also use the command decorator to define multiple subcommands:

    .. code-block:: python

        class Command(TyperCommand):

            @command()
            def command1(self):
                # execute command1 logic here

            @command(name='command2')
            def other_command(self):
                # arguments passed to the decorator are passed to typer and control
                # various aspects of the command, for instance here we've changed the
                # name of the command to 'command2' from 'other_command'

    The decorated function is the command function. It may also be invoked directly
    as a method from an instance of the :class:`~django_typer.management.TyperCommand`
    class, see :func:`~django_typer.management.get_command`.

    :param name: the name of the command (defaults to the name of the decorated
        function)
    :param cls: the command class to use
    :param context_settings: the context settings to use - see :class:`click.Context`
    :param help: the help string to use, defaults to the function docstring, if
        you need the help to be translated you should use the help kwarg instead
        because docstrings will not be translated.
    :param epilog: the epilog to use in the help output
    :param short_help: the short help to use in the help output
    :param options_metavar: the metavar to use for options in the help output
    :param add_help_option: whether to add the help option to the command
    :param no_args_is_help: whether to show the help if no arguments are provided
    :param hidden: whether to hide the command from help output
    :param deprecated: show a deprecation warning
    :param rich_help_panel: the rich help panel to use - if rich is installed
        this can be used to group commands into panels in the help output.
    """

    def make_command(func: t.Callable[P, R]) -> t.Callable[P, R]:
        func = _check_static(func)
        _cache_command(
            func,
            name=name,
            cls=cls,
            context_settings=context_settings,
            help=help,
            epilog=epilog,
            short_help=short_help,
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            no_args_is_help=no_args_is_help,
            hidden=hidden,
            deprecated=deprecated,
            # Rich settings
            rich_help_panel=rich_help_panel,
            **kwargs,
        )
        return func

    return make_command


def group(
    name: t.Optional[str] = Default(None),
    cls: t.Type[DTGroup] = DTGroup,
    invoke_without_command: bool = Default(False),
    no_args_is_help: bool = Default(False),
    subcommand_metavar: t.Optional[str] = Default(None),
    chain: bool = Default(False),
    result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
    # Command
    context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
    help: t.Optional[t.Union[str, Promise]] = Default(None),
    epilog: t.Optional[str] = Default(None),
    short_help: t.Optional[t.Union[str, Promise]] = Default(None),
    options_metavar: str = Default("[OPTIONS]"),
    add_help_option: bool = Default(True),
    hidden: bool = Default(False),
    deprecated: bool = False,
    # Rich settings
    rich_help_panel: t.Union[str, None] = Default(None),
    **kwargs: t.Any,
) -> t.Callable[
    [t.Callable[t.Concatenate[TC, P], R]],  # pyright: ignore[reportInvalidTypeVarUse]
    Typer[P, R],
]:
    """
    A function decorator that creates a new subgroup and attaches it to the root
    command group. This is like creating a new Typer_ app and adding it to a parent
    Typer app. The kwargs are passed through to the ``Typer()`` constructor. The
    :func:`~django_typer.management.group` functions work like
    :func:`~django_typer.management.initialize` functions for their command groups.

    .. code-block:: python
        :caption: management/commands/example.py

        from django_typer import TyperCommand, group

        class Command(TyperCommand):

            @group()
            def group1(self, flag: bool = False):
                # do group init stuff here

            # to attach a command to the group, use the command() decorator
            # on the group function
            @group1.command()
            def command1(self):
                ...

            # you can also attach subgroups to groups!
            @group1.group()
            def subgroup(self):
                # do subgroup init stuff here

            @subgroup.command()
            def subcommand(self):
                ...

    These groups and subcommands can be invoked from the command line like so:

    .. code-block:: bash

        $ ./manage.py example group1 --flag command1
        $ ./manage.py example group1 --flag subgroup subcommand

    :param name: the name of the group (defaults to the name of the decorated function)
    :param cls: the group class to use
    :param invoke_without_command: whether to invoke the group callback if no command
        was specified.
    :param no_args_is_help: whether to show the help if no arguments are provided
    :param subcommand_metavar: the metavar to use for subcommands in the help output
    :param chain: whether to chain commands, this allows multiple commands from the
        group to be specified and run in order sequentially in one call from the command
        line.
    :param result_callback: a callback to invoke with the result of the command
    :param context_settings: the click context settings to use - see
        :class:`click.Context`
    :param help: the help string to use, defaults to the function docstring, if you need
        to translate the help you should use the help kwarg instead because docstrings
        will not be translated.
    :param epilog: the epilog to use in the help output
    :param short_help: the short help to use in the help output
    :param options_metavar: the metavar to use for options in the help output
    :param add_help_option: whether to add the help option to the command
    :param hidden: whether to hide this group from the help output
    :param deprecated: show a deprecation warning
    :param rich_help_panel: the rich help panel to use - if rich is installed
        this can be used to group commands into panels in the help output.
    """

    def create_app(
        func: t.Callable[t.Concatenate[TC, P], R],
    ) -> Typer[P, R]:
        grp = Typer(
            name=name or _strip_static(func).__name__.replace("_", "-"),
            cls=cls,
            invoke_without_command=invoke_without_command,
            no_args_is_help=no_args_is_help,
            subcommand_metavar=subcommand_metavar,
            chain=chain,
            result_callback=result_callback,
            callback=func,
            context_settings=context_settings,
            help=help,
            epilog=epilog,
            short_help=short_help,
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            hidden=hidden,
            deprecated=deprecated,
            rich_help_panel=rich_help_panel,
            parent=None,
            top_level=True,
            **kwargs,
        )
        return grp

    return create_app


def _add_common_initializer(
    cmd: t.Union["TyperCommandMeta", t.Type["TyperCommand"], "TyperCommand"],
) -> t.Optional[typer.models.TyperInfo]:
    """
    Add a callback to the typer app that will add the unsuppressed
    common django base command parameters to the CLI if the command
    is a compound command and no existing callback is registered.

    :param cmd: The command class or instance.
    :return: The callback that was/is registered on the command
    """
    if cmd.is_compound_command and not cmd.typer_app.registered_callback:
        cmd.typer_app.callback(
            cls=type(  # pyright: ignore[reportArgumentType]
                "_Initializer",
                (cmd.typer_app.info.cls or DTGroup,),
                {
                    "django_command": cmd,
                    "_callback_is_method": False,
                    "common_init": True,
                },
            )
        )(lambda: None)
    return cmd.typer_app.registered_callback


def _resolve_help(dj_cmd: "TyperCommand"):
    """
    If no help string would be rendered for the root level command and a class docstring
    is present, use it as the help string.

    :param dj_cmd: The TyperCommand to resolve the help string for.
    """
    hlp = None
    for cmd_cls in [
        c
        for c in dj_cmd.__class__.__mro__
        if issubclass(c, TyperCommand) and c is not TyperCommand
    ]:
        hlp = cmd_cls.__doc__
        if hlp:
            break
    if hlp:
        if dj_cmd.typer_app.registered_callback:
            cb = dj_cmd.typer_app.registered_callback
            if not cb.help and not cb.callback.__doc__:
                cb.help = hlp
        else:
            cmd = (
                dj_cmd.typer_app.registered_commands[0]
                if dj_cmd.typer_app.registered_commands
                else None
            )
            if cmd and not cmd.help and not cmd.callback.__doc__:
                cmd.help = hlp
            elif not dj_cmd.typer_app.info.help:
                dj_cmd.typer_app.info.help = hlp
    elif (
        dj_cmd.typer_app.info.help
        and not dj_cmd.is_compound_command
        and dj_cmd.typer_app.registered_commands
        and not dj_cmd.typer_app.registered_commands[0].help
    ):
        dj_cmd.typer_app.registered_commands[0].help = dj_cmd.typer_app.info.help


def _names(tc: t.Union[typer.models.CommandInfo, Typer]) -> t.Set[str]:
    """
    For a command or group, get a list of attribute name and its CLI name.

    This annoyingly lives in different places depending on how the command
    or group was defined. This logic is sensitive to typer internals.
    """
    names = set()
    if isinstance(tc, typer.models.CommandInfo):
        assert tc.callback
        names.add(tc.callback.__name__)
        if tc.name:
            names.add(tc.name)
    else:
        if tc.info.name:
            names.add(tc.info.name)
        # TODO sometimes tc.info can be disjoint with tc.registered_callback
        if tc.registered_callback and tc.registered_callback.callback:
            names.add(tc.registered_callback.callback.__name__)
        if tc.info.callback:
            names.add(tc.info.callback.__name__)
    return names


@lru_cache(maxsize=None)
def _bfs_match(
    app: Typer, name: str
) -> t.Optional[t.Union[typer.models.CommandInfo, Typer, Finalizer]]:
    """
    Perform a breadth first search for a command or group by name.

    :param app: The Typer app to search.
    :param name: The name of the command or group to search for.
    :return: The command or group if found, otherwise None.
    """

    def find_at_level(
        lvl: Typer,
    ) -> t.Optional[t.Union[typer.models.CommandInfo, Typer, Finalizer]]:
        for cmd in reversed(lvl.registered_commands):
            if name in _names(cmd):
                return cmd
        if name in _names(lvl):
            return lvl

        if (
            isinstance(lvl.info.result_callback, Finalizer)
            and lvl.info.result_callback.name == name
        ):
            return lvl.info.result_callback
        return None

    # fast exit out if at top level (most searches - avoid building BFS)
    if found := find_at_level(app):
        return found

    bfs_order: t.List[Typer] = []
    queue = deque([app])

    while queue:
        grp = queue.popleft()
        bfs_order.append(grp)
        # if names conflict, only pick the first the others have been
        # overridden - avoids walking down stale branches
        seen = set()
        for child_grp in reversed(grp.registered_groups):
            child_app = t.cast(Typer, child_grp.typer_instance)
            assert child_app
            if child_app.info.name not in seen:
                seen.update(_names(child_app))
                queue.append(child_app)

    for grp in bfs_order[1:]:
        found = find_at_level(grp)
        if found:
            return found
    return None


class TyperCommandMeta(type):
    """
    The metaclass used to build the TyperCommand class. This metaclass is responsible
    for building Typer app using the arguments supplied to the TyperCommand constructor.
    It also discovers if :meth:`~django.core.management.BaseCommand.handle` was supplied
    as the single command implementation.

    .. warning::

        This metaclass is private because it may change substantially in the future to
        support changes in the upstream libraries. The TyperCommand interface should be
        considered the stable interface.

    :param name: the name of the class being created
    :param bases: the base classes of the class being created
    :param attrs: the attributes of the class being created
    :param cls: The class to use as the core typer group wrapper
    :param invoke_without_command: whether to invoke the group callback if no command
        was specified.
    :param no_args_is_help: whether to show the help if no arguments are provided
    :param subcommand_metavar: the metavar to use for subcommands in the help output
    :param chain: whether to chain commands, this allows multiple commands from the
        group to be specified and run in order sequentially in one call from the command
        line.
    :param result_callback: a callback to invoke with the result of the command
    :param context_settings: the click context settings to use - see
        :class:`click.Context`
    :param help: the help string to use, defaults to the function docstring, if you need
        to translate the help you should use the help kwarg instead because docstrings
        will not be translated.
    :param epilog: the epilog to use in the help output
    :param short_help: the short help to use in the help output
    :param options_metavar: the metavar to use for options in the help output
    :param add_help_option: whether to add the help option to the command
    :param hidden: whether to hide this group from the help output
    :param deprecated: show a deprecation warning
    :param rich_markup_mode: the rich markup mode to use - if rich is installed
        this can be used to enable rich markup or Markdown in the help output. Can
        be "markdown", "rich" or None to disable markup rendering.
    :param rich_help_panel: the rich help panel to use - if rich is installed
        this can be used to group commands into panels in the help output.
    :param pretty_exceptions_enable: whether to enable pretty exceptions - if rich is
        installed this can be used to enable pretty exception rendering. This will
        default to on if the traceback configuration settings installs the rich
        traceback handler. This allows tracebacks to be configured by the user on a
        per deployment basis in the settings file. We therefore do not advise
        hardcoding this value.
    :param pretty_exceptions_show_locals: whether to show local variables in pretty
        exceptions - if rich is installed. This will default to the 'show_locals'
        setting in the traceback configuration setting (on by default). This allows
        tracebacks to be configured by the user on a per deployment basis in the
        settings file. We therefore do not advise hardcoding this value.
    :param pretty_exceptions_short: whether to show short tracebacks in pretty
        exceptions - if rich is installed. This will default to the 'short' setting
        in the traceback configuration setting (off by default). This allows tracebacks
        to be configured by the user on a per deployment basis in the settings file. We
        therefore do not advise hardcoding this value.
    """

    style: ColorStyle
    stdout: BaseOutputWrapper
    stderr: BaseOutputWrapper
    requires_system_checks: t.Union[t.Sequence[str], str]
    suppressed_base_arguments: t.Optional[t.Iterable[str]]
    typer_app: Typer
    no_color: bool
    force_color: bool
    skip_checks: bool
    is_compound_command: bool
    _handle: t.Optional[t.Callable[..., t.Any]]

    # this holds the Typer app commands and groups defined directly on the class
    # and its parents.
    _defined_groups: t.Dict[str, Typer] = {}

    def __new__(
        mcs,
        cls_name,
        bases,
        attrs,
        name: t.Optional[str] = Default(None),
        cls: t.Optional[t.Type[DTGroup]] = DTGroup,
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: t.Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
        callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        help: t.Optional[t.Union[str, Promise]] = Default(None),
        epilog: t.Optional[str] = Default(None),
        short_help: t.Optional[t.Union[str, Promise]] = Default(None),
        options_metavar: str = Default("[OPTIONS]"),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = Default(False),
        rich_markup_mode: typer.core.MarkupMode = DEFAULT_MARKUP_MODE,
        rich_help_panel: t.Union[str, None] = Default(None),
        suggest_commands: bool = True,
        pretty_exceptions_enable: t.Union[DefaultPlaceholder, bool] = Default(True),
        pretty_exceptions_show_locals: t.Union[DefaultPlaceholder, bool] = Default(
            False
        ),
        pretty_exceptions_short: t.Union[DefaultPlaceholder, bool] = Default(True),
        **kwargs: t.Any,
    ):
        """
        This method is called when a new class is created.
        """
        try:
            # avoid unnecessary work creating the TyperCommand class
            # is there a less weird way to do this?
            is_base_init = not TyperCommand  # type: ignore[truthy-function]
        except NameError:
            is_base_init = True
        typer_app = None

        if not is_base_init:
            # conform the pretty exception defaults to the settings traceback config
            tb_config = traceback_config()
            if isinstance(pretty_exceptions_enable, DefaultPlaceholder):
                pretty_exceptions_enable = use_rich_tracebacks()

            if isinstance(pretty_exceptions_show_locals, DefaultPlaceholder):
                pretty_exceptions_show_locals = tb_config.get(
                    "show_locals", pretty_exceptions_show_locals
                )
            if isinstance(pretty_exceptions_short, DefaultPlaceholder):
                pretty_exceptions_short = tb_config.get(
                    "short", pretty_exceptions_short
                )

            attr_help = attrs.get("help", Default(None))
            for base in [
                base
                for base in bases
                if issubclass(base, TyperCommand) and base is not TyperCommand
            ]:
                if isinstance(help, DefaultPlaceholder):
                    help = base._help_kwarg  # type: ignore[unreachable]
                if isinstance(attr_help, DefaultPlaceholder):
                    attr_help = base.help
                if isinstance(options_metavar, DefaultPlaceholder):
                    options_metavar = base.typer_app.info.options_metavar

            def command_bases() -> t.Generator[t.Type[TyperCommand], None, None]:
                # the mro is not yet resolved so we have to do it manually
                seen = set()
                for first_level in reversed(bases):
                    for base in reversed(first_level.__mro__):
                        if issubclass(base, TyperCommand) and base is not TyperCommand:
                            if base not in seen:
                                seen.add(base)
                                yield base

            typer_app = Typer(
                name=name or attrs.get("__module__", "").rsplit(".", maxsplit=1)[-1],
                cls=cls,
                help=help or attr_help,  # pyright: ignore[reportArgumentType]
                invoke_without_command=invoke_without_command,
                no_args_is_help=no_args_is_help,
                subcommand_metavar=subcommand_metavar,
                chain=chain,
                result_callback=result_callback,
                context_settings=context_settings,
                callback=callback,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                hidden=hidden,
                deprecated=deprecated,
                add_completion=False,  # see autocomplete command instead!
                rich_markup_mode=rich_markup_mode,
                rich_help_panel=rich_help_panel,
                suggest_commands=suggest_commands,
                pretty_exceptions_enable=pretty_exceptions_enable,
                pretty_exceptions_show_locals=t.cast(
                    bool, pretty_exceptions_show_locals
                ),
                pretty_exceptions_short=t.cast(bool, pretty_exceptions_short),
                **kwargs,
            )

            # move up here
            def get_ctor(attr: t.Any) -> t.Optional[t.Callable[..., t.Any]]:
                return getattr(attr, _CACHE_KEY, None)

            # because we're mapping a non-class based interface onto a class based
            # interface, we have to handle this class mro stuff manually here
            handle = None  # there can be only one or none
            _defined_groups: t.Dict[str, Typer] = {}
            to_remove = []
            to_register = []
            local_handle = attrs.pop("handle", None)
            defined_order = []
            for cmd_cls, cls_attrs in [
                *[(base, vars(base)) for base in command_bases()],
                (None, attrs),
            ]:
                defined_order += [
                    cmd
                    for cmd in getattr(cmd_cls, "_defined_order", [])
                    if cmd not in defined_order
                ]
                for name, attr in list(cls_attrs.items()):
                    if name == "_handle":
                        continue
                    if name == "_defined_groups":
                        _defined_groups = {**_defined_groups, **attr}
                        continue
                    if name != "typer_app" and isinstance(attr, Typer):
                        assert name
                        to_remove.append(name)
                        _defined_groups[name] = attr
                        if cmd_cls is None and name not in defined_order:
                            defined_order.append(name)
                    elif register := get_ctor(attr):
                        to_register.append(register)
                        if cmd_cls is None and name not in defined_order:
                            defined_order.append(name)

                handle = getattr(cmd_cls, "_handle", handle)

            handle = local_handle or handle

            for grp in set(_defined_groups.values()):
                if grp.top_level:
                    cpy = deepcopy(grp)
                    cpy.parent = typer_app
                    typer_app.add_typer(
                        cpy,
                        name=cpy.info.name,
                        options_metavar=cpy.info.options_metavar or options_metavar,
                    )

            # remove the groups from the class to allow __getattr__ to control
            # which group instance is returned based on call context
            for name in to_remove:
                attrs.pop(name)

            attrs["_defined_groups"] = _defined_groups

            if handle:
                ctor = get_ctor(handle)
                defined_order.insert(0, typer_app.info.name)
                if ctor:
                    to_register.append(
                        lambda cmd_cls: ctor(
                            cmd_cls,
                            _name=typer_app.info.name,
                            _help=attrs.get("help", Default(None)),
                        )
                    )
                else:
                    to_register.append(
                        lambda _: typer_app.command(
                            typer_app.info.name,
                            help=typer_app.info.help or None,
                        )(handle)
                    )

            attrs = {
                "_defined_order": defined_order,
                **attrs,
                "_handle": handle,
                "_to_register": to_register,
                "typer_app": typer_app,
            }

        else:
            # we do this to avoid typing complaints on handle overrides
            attrs["handle"] = attrs.pop("_run")

        if help:
            attrs["_help_kwarg"] = help

        return super().__new__(mcs, cls_name, bases, attrs)

    def __init__(self, cls_name, bases, attrs, **kwargs):
        """
        This method is called after a new class is created.
        """
        self = t.cast(t.Type["TyperCommand"], self)
        if getattr(self, "typer_app", None):
            self.typer_app.django_command = self
            self.typer_app.info.name = (
                self.typer_app.info.name or self.__module__.rsplit(".", maxsplit=1)[-1]
            )
            for cmd in getattr(self, "_to_register", []):
                cmd(self)

            _add_common_initializer(self)

        super().__init__(cls_name, bases, attrs, **kwargs)

    def __getattr__(cls, name: str) -> t.Any:
        """
        Fall back breadth first search of the typer app tree to resolve attribute
        accesses of the type:

            Command.sub_grp or Command.sub_cmd or Command.finalizer
        """
        if name != "typer_app":
            if called_from_command_definition():
                if name in cls._defined_groups:
                    return cls._defined_groups[name]
            found = _bfs_match(cls.typer_app, name)
            if found:
                return found
        raise AttributeError(
            "{cls} object has no attribute {name}".format(cls=cls.__name__, name=name)
        )


class CommandNode:
    """
    A tree node that represents a command in the command tree. This is used to
    walk the click command hierarchy and produce helps and map command paths
    to command functions. The command tree is built on TyperCommand initialization.

    :param name: the name of the command or subcommand
    :param click_command: the click command object
    :param context: the click context object
    :param django_command: the django command instance
    :param parent: the parent node or None if this is a root node
    """

    name: str
    """
    The name of the group or command that this node represents.
    """

    click_command: DjangoTyperMixin
    """
    The click command object that this node represents.
    """

    context: Context
    """
    The Typer context object used to run this command.
    """

    django_command: "TyperCommand"
    """
    Back reference to the django command instance that this command belongs to.
    """

    @cached_property
    def children(self) -> t.Dict[str, "CommandNode"]:
        """
        The child group and command nodes of this command node.
        """
        return {
            name: CommandNode(name, cmd, self.django_command, parent=self.context)
            for name, cmd in getattr(
                self.context.command,
                "commands",
                {
                    name: self.context.command.get_command(  # type: ignore
                        self.context, name
                    )
                    for name in (
                        self.context.command.list_commands(self.context)
                        if isinstance(self.context.command, click.Group)
                        else []
                    )
                },
            ).items()
        }

    @property
    def callback(self) -> t.Callable[..., t.Any]:
        """Get the function for this command or group"""
        return _get_direct_function(
            self.django_command, getattr(self.click_command._callback, "__wrapped__")
        )

    def __init__(
        self,
        name: str,
        click_command: DjangoTyperMixin,
        django_command: "TyperCommand",
        parent: t.Optional[Context] = None,
    ):
        self.name = name
        self.click_command = click_command
        self.django_command = django_command
        self.context = Context(
            self.click_command,
            info_name=name,
            django_command=django_command,
            parent=parent,
        )

    def print_help(self) -> t.Optional[str]:
        """
        Prints the help for this command to stdout of the django command.
        """
        # if rich is installed this prints the help, if it is not it
        # returns the help as a string - we deal with this higher on the
        # stack
        return self.click_command.get_help(self.context)

    def get_command(self, *command_path: str) -> "CommandNode":
        """
        Return the command node for the given command path at or below
        this node.

        :param command_path: the parent group names followed by the name of the command
            or group to retrieve
        :return: the command node at the given group/subcommand path
        :raises LookupError: if the command path does not exist
        """
        if not command_path:
            return self
        try:
            return self.children[command_path[0]].get_command(*command_path[1:])
        except KeyError as err:
            raise LookupError(f'No such command "{command_path[0]}"') from err

    def __call__(self, *args, **kwargs) -> t.Any:
        """
        Call this command or group directly.

        :param args: the arguments to pass to the command or group callback
        :param kwargs: the named parameters to pass to the command or group callback
        """
        return self.callback(*args, **kwargs)


class TyperParser:
    """
    A class that conforms to the argparse.ArgumentParser interface that the django
    base class works with that is returned by
    :meth:`~django.core.management.BaseCommand.create_parser`. This class does not
    strictly conform to the argparse interface but does just enough to satisfy the
    django base class.

    :param django_command: the django command instance
    :param prog_name: the name of the manage script that invoked the command
    :param subcommand: the name of the django command
    """

    class Action:
        """
        Emulate the interface of argparse.Action. Partial implementation
        used to satisfy the django BaseCommand class.

        :param param: the click parameter to wrap as an argparse Action
        """

        param: click.Parameter
        required: bool = False

        def __init__(self, param: click.Parameter):
            self.param = param

        @property
        def dest(self) -> t.Optional[str]:
            """
            The name of the parameter as passed to the command.
            """
            return self.param.name

        @property
        def nargs(self) -> int:
            """
            The number of arguments consumed by this parameter or 0 if it is a flag.
            """
            return 0 if getattr(self.param, "is_flag", False) else self.param.nargs

        @property
        def option_strings(self) -> t.List[str]:
            """
            call_command uses this to determine a mapping of supplied options to
            function arguments. I.e. it will remap option_string: dest. We don't want
            this because we'd rather have supplied parameters line up with their
            function arguments to allow deconfliction when CLI options share the same
            name.
            """
            return []

    _actions: t.List[t.Any]
    _mutually_exclusive_groups: t.List[t.Any] = []

    django_command: "TyperCommand"
    prog_name: str
    subcommand: str

    def __init__(self, django_command: "TyperCommand", prog_name, subcommand):
        self._actions = []
        self.django_command = django_command
        self.prog_name = prog_name
        self.subcommand = subcommand
        self.tree = self.django_command.command_tree
        self.tree.context.info_name = f"{self.prog_name} {self.subcommand}"

        def populate_params(node: CommandNode) -> None:
            for param in node.click_command.params:
                self._actions.append(self.Action(param))
            for child in node.children.values():
                populate_params(child)

        populate_params(self.tree)

    def print_help(self, *command_path: str):
        """
        Print the help for the given command path to stdout of the django command.
        """
        command_node = self.tree.get_command(*command_path)
        hlp = command_node.print_help()
        if hlp:
            self.django_command.stdout.write(
                hlp, style_func=lambda msg: msg, ending="\n\n"
            )

    def parse_args(self, args=None, namespace=None) -> _ParsedArgs:
        """
        Parse the given arguments into a parsed arguments namespace object.
        If any arguments trigger termination of the command (like --help) then
        this method will exit the program.

        Parse will also add the common django parameter defaults to the parsed
        arguments object.

        :param args: the arguments to parse
        :param namespace: the namespace to populate with the parsed arguments
            (this is ignored for TyperCommands but is required by the django
            base class)
        """
        with self.django_command:
            cmd = get_typer_command(self.django_command.typer_app)
            with cmd.make_context(
                info_name=f"{self.prog_name} {self.subcommand}",
                django_command=self.django_command,
                args=list(args or []),
            ) as ctx:
                common = {
                    **_remove_suppressed(
                        self.django_command,
                        COMMON_DEFAULTS,
                        {param.name for param in cmd.params if param.name},
                    ),
                    **ctx.params,
                }
                self.django_command._traceback = common.get(
                    "traceback", self.django_command._traceback
                )
                return _ParsedArgs(args=args or [], **common)

    def add_argument(self, *args, **kwargs):
        """
        add_argument() is disabled for TyperCommands because all arguments
        and parameters are specified as args and kwargs on the function calls.
        """
        raise NotImplementedError("add_argument() is not supported")


class OutputWrapper(BaseOutputWrapper):
    """
    Override django's base OutputWrapper to avoid exceptions when strings are
    returned from command functions.
    """

    disable: bool = False

    def write(self, msg="", style_func=None, ending=None):
        """
        If the message is not a string, first cast it before invoking the base
        class write method.
        """
        if self.disable:
            return
        if not isinstance(msg, str):
            msg = str(msg)
        return super().write(msg=msg, style_func=style_func, ending=ending)

    def flush(self):
        # as of python 3.13, sometimes flush is called on a closed stream
        if not getattr(self._out, "closed", False):
            super().flush()


class TyperCommand(BaseCommand, metaclass=TyperCommandMeta):
    """
    An extension of :class:`~django.core.management.BaseCommand` that uses the Typer_
    library to parse arguments_ and options_. This class adapts
    :class:`~django.core.management.BaseCommand` using a light touch that relies on most
    of the original :class:`~django.core.management.BaseCommand` implementation to
    handle default arguments and behaviors.

    All of the documented :class:`~django.core.management.BaseCommand` functionality
    works as expected. :func:`~django.core.management.call_command` also works as
    expected. TyperCommands however add a few extra features:

        - We define arguments_ and options_ using concise and optionally annotated type
          hints.
        - Simple TyperCommands implemented only using
          :meth:`~django.core.management.BaseCommand.handle` can be called directly by
          invoking the command as a callable.
        - We can define arbitrarily complex subcommand group hierarchies using the
          :func:`~django_typer.management.group` and
          :func:`~django_typer.management.command` decorators.
        - Commands and subcommands can be fetched and invoked directly as functions
          using :func:`~django_typer.management.get_command`
        - We can define common initialization logic for groups of commands using
          :func:`~django_typer.management.initialize`
        - TyperCommands may safely return non-string values from
          :meth:`~django.core.management.BaseCommand.handle`

    Defining a typer command is a lot like defining a
    :class:`~django.core.management.BaseCommand` except that we do not have an
    :meth:`~django.core.management.BaseCommand.add_arguments` method. Instead we define
    the parameters using type hints directly on
    :meth:`~django.core.management.BaseCommand.handle`:

    .. code-block:: python

        import typing as t
        from django_typer import TyperCommand

        class Command(TyperCommand):

            def handle(
                self,
                arg: str,
                option: t.Optional[str] = None
            ):
                # do command logic here

    TyperCommands can be extremely simple like above, or we can create really complex
    command group hierarchies with subcommands and subgroups (see
    :func:`~django_typer.management.group` and
    :func:`~django_typer.management.command`).

    Typer_ apps can be configured with a number of parameters to control behavior such
    as exception behavior, help output, help markup interpretation, result processing
    and execution flow. These parameters can be passed to typer as keyword arguments in
    your Command class inheritance:

    .. code-block:: python
        :caption: management/commands/chain.py
        :linenos:

        import typing as t
        from django_typer import TyperCommand, command


        class Command(TyperCommand, rich_markup_mode='markdown', chain=True):

            suppressed_base_arguments = [
                '--verbosity', '--traceback', '--no-color', '--force-color',
                '--skip_checks', '--settings', '--pythonpath', '--version'
            ]

            @command()
            def command1(self, option: t.Optional[str] = None):
                \"""This is a *markdown* help string\"""
                print('command1')
                return option

            @command()
            def command2(self, option: t.Optional[str] = None):
                \"""This is a *markdown* help string\"""
                print('command2')
                return option


    We're doing a number of things here:

        - Using the :func:`~django_typer.management.command` decorator to define
          multiple subcommands.
        - Using :attr:`~django.core.management.BaseCommand.suppressed_base_arguments`
          to suppress the default options Django adds to the command interface.
        - Using `rich_markup_mode
          <https://typer.tiangolo.com/tutorial/commands/help/#rich-markdown-and-markup>`_
          to enable markdown rendering in help output.
        - Using the chain parameter to enable :ref:`click:command-chaining`.


    We can see that our help renders like so:

    .. typer:: tests.apps.test_app.management.commands.chain.Command:typer_app
        :prog: ./manage.py chain
        :width: 80
        :convert-png: latex


    And we can see the chain behavior by calling our command(s) like so:

    .. code-block:: bash

        $ ./manage.py chain command1 --option one command2 --option two
        command1
        command2
        ['one', 'two']

    See :class:`~django_typer.management.TyperCommandMeta` for the list of accepted
    parameters. Also refer to the Typer_ docs for more information on the behaviors
    expected for those parameters - they are passed through to the Typer class
    constructor. Not all parameters may make sense in the context of a django command.

    :param stdout: the stdout stream to use
    :param stderr: the stderr stream to use
    :param no_color: whether to disable color output
    :param force_color: whether to force color output even if the stream is not a tty
    """

    # TyperCommands are built in stages. The metaclass is responsible for finding
    # all the commands and callbacks and building the Typer_ app. This happens at
    # class definition time (i.e. on module load). When the TyperCommand is instantiated
    # the command tree is built thats used for subcommand resolution in django-typer's
    # get_command method and for help output.

    style: ColorStyle
    stdout: BaseOutputWrapper
    stderr: BaseOutputWrapper
    # requires_system_checks: t.Union[t.List[str], t.Tuple[str, ...], t.Literal['__all__']]

    # we do not use verbosity because the base command does not do anything with it
    # if users want to use a verbosity flag like the base django command adds
    # they can use the type from django_typer.types.Verbosity
    suppressed_base_arguments = {"verbosity"}

    missing_args_message = "Missing parameter: {parameter}"

    typer_app: Typer
    no_color: bool = False
    force_color: bool = False
    skip_checks: bool = False

    print_result: bool = True
    """Turn on/off automatic write to stdout of results returned by command"""

    _handle: t.Callable[..., t.Any]
    _traceback: bool = False
    _help_kwarg: t.Optional[str] = Default(None)
    _defined_groups: t.Dict[str, Typer] = {}
    _finalizer: t.Optional[Finalizer] = None
    _suppressed_base_arguments: t.Optional[t.Set[str]] = None

    help: t.Optional[t.Union[DefaultPlaceholder, str, Promise]] = Default(None)  # type: ignore

    # allow deriving commands to override handle() from BaseCommand
    # without triggering static type checking complaints
    handle: t.Callable[..., t.Any]

    @property
    def command_tree(self) -> CommandNode:
        """
        Get the root CommandNode for this command. Allows easy traversal of the command
        tree.
        """
        return CommandNode(
            f"{sys.argv[0]} {self._name}",
            click_command=t.cast(DjangoTyperMixin, get_typer_command(self.typer_app)),
            django_command=self,
        )

    @classmethod
    def initialize(
        cmd,  # pyright: ignore[reportSelfClsParameterName]
        *,
        cls: t.Type[DTGroup] = DTGroup,
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: t.Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        # Command
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
        help: t.Optional[t.Union[str, Promise]] = Default(None),
        epilog: t.Optional[str] = Default(None),
        short_help: t.Optional[t.Union[str, Promise]] = Default(None),
        options_metavar: t.Optional[str] = Default(None),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = Default(False),
        # Rich settings
        rich_help_panel: t.Union[str, None] = Default(None),
        **kwargs: t.Any,
    ) -> t.Callable[[t.Callable[P, R]], t.Callable[P, R]]:
        """
        Override the initializer for this command class after it has been defined.

        .. note::
            See :ref:`plugins` for details on when you might want to use this extension
            pattern.

        .. code-block:: python

            from your_app.management.commands.your_command import Command as YourCommand

            @YourCommand.initialize()
            def init(self, ...):
                # implement your command initialization logic here

        :param name: the name of the callback (defaults to the name of the decorated
            function)
        :param cls: the command class to use - (the
            :func:`~django_typer.management.initialize` function is technically the root
            command group)
        :param invoke_without_command: whether to invoke the callback if no command was
            specified.
        :param no_args_is_help: whether to show the help if no arguments are provided
        :param subcommand_metavar: the metavar to use for subcommands in the help output
        :param chain: whether to chain commands, this allows multiple commands from the
            group to be specified and run in order sequentially in one call from the
            command line.
        :param result_callback: a callback to invoke with the result of the command
        :param context_settings: the click context settings to use - see
            :class:`click.Context`.
        :param help: the help string to use, defaults to the function docstring, if you
            need to translate the help you should use the help kwarg instead because
            docstrings will not be translated.
        :param epilog: the epilog to use in the help output
        :param short_help: the short help to use in the help output
        :param options_metavar: the metavar to use for options in the help output
        :param add_help_option: whether to add the help option to the command
        :param hidden: whether to hide this group from the help output
        :param deprecated: show a deprecation warning
        :param rich_help_panel: the rich help panel to use - if rich is installed
            this can be used to group commands into panels in the help output.
        """
        if called_from_command_definition():
            return initialize(
                cls=cls,
                context_settings=context_settings,
                help=help,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                invoke_without_command=invoke_without_command,
                no_args_is_help=no_args_is_help,
                subcommand_metavar=subcommand_metavar,
                chain=chain,
                result_callback=result_callback,
                hidden=hidden,
                deprecated=deprecated,
                # Rich settings
                rich_help_panel=rich_help_panel,
                **kwargs,
            )

        def make_initializer(func: t.Callable[P, R]) -> t.Callable[P, R]:
            # we might have to override a method defined in the base class
            setattr(cmd, func.__name__, func)
            cmd.typer_app.callback(
                cls=type("_Initializer", (cls,), {"django_command": cmd}),
                context_settings=context_settings,
                help=help,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                invoke_without_command=invoke_without_command,
                no_args_is_help=no_args_is_help,
                subcommand_metavar=subcommand_metavar,
                chain=chain,
                result_callback=result_callback,
                hidden=hidden,
                deprecated=deprecated,
                # Rich settings
                rich_help_panel=rich_help_panel,
                **kwargs,
            )(_strip_static(func))
            return func

        return make_initializer

    callback = initialize

    @classmethod
    def finalize(cls) -> t.Callable[[t.Callable[P2, R2]], t.Callable[P2, R2]]:
        """
        Override the finalizer for this command class after it has been defined.

        .. note::
            See :ref:`plugins` for details on when you might want to use this extension
            pattern.

        .. code-block:: python

            from your_app.management.commands.your_command import Command as YourCommand

            @YourCommand.finalize()
            def collect(self, ...):
                # implement your command result collection logic here
        """
        if called_from_command_definition():
            return finalize()

        def make_finalizer(func: t.Callable[P2, R2]) -> t.Callable[P2, R2]:
            setattr(cls, func.__name__, func)
            cls.typer_app.info.result_callback = Finalizer(_strip_static(func))
            return func

        return make_finalizer

    @classmethod
    def command(
        cmd,  # pyright: ignore[reportSelfClsParameterName]
        name: t.Optional[str] = None,
        *,
        cls: t.Type[DTCommand] = DTCommand,
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = None,
        help: t.Optional[t.Union[str, Promise]] = None,
        epilog: t.Optional[str] = None,
        short_help: t.Optional[t.Union[str, Promise]] = None,
        options_metavar: t.Optional[str] = Default(None),
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
        # Rich settings
        rich_help_panel: t.Union[str, None] = Default(None),
        **kwargs: t.Any,
    ) -> t.Callable[[t.Callable[P, R]], t.Callable[P, R]]:
        """
        Add a command to this command class after it has been defined. You can
        use this decorator to add commands to a root command from other Django apps.

        .. note::
            See :ref:`plugins` for details on when you might want to use this extension
            pattern.

        .. code-block:: python

            from your_app.management.commands.your_command import Command as YourCommand

            @YourCommand.command()
            def new_command(self, ...):
                # implement your additional command here

        :param name: the name of the command (defaults to the name of the decorated
            function)
        :param cls: the command class to use
        :param context_settings: the context settings to use - see
            :class:`click.Context`
        :param help: the help string to use, defaults to the function docstring, if
            you need the help to be translated you should use the help kwarg instead
            because docstrings will not be translated.
        :param epilog: the epilog to use in the help output
        :param short_help: the short help to use in the help output
        :param options_metavar: the metavar to use for options in the help output
        :param add_help_option: whether to add the help option to the command
        :param no_args_is_help: whether to show the help if no arguments are provided
        :param hidden: whether to hide the command from help output
        :param deprecated: show a deprecation warning
        :param rich_help_panel: the rich help panel to use - if rich is installed
            this can be used to group commands into panels in the help output.
        """
        if called_from_command_definition():
            return command(
                name=name,
                cls=cls,
                context_settings=context_settings,
                help=help,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                no_args_is_help=no_args_is_help,
                hidden=hidden,
                deprecated=deprecated,
                # Rich settings
                rich_help_panel=rich_help_panel,
                **kwargs,
            )

        def make_command(func: t.Callable[P, R]) -> t.Callable[P, R]:
            # we might have to override a method defined in the base class
            setattr(cmd, func.__name__, func)
            cmd.typer_app.command(
                name=name,
                cls=type("_Command", (cls,), {"django_command": cmd}),
                context_settings=context_settings,
                help=help,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                no_args_is_help=no_args_is_help,
                hidden=hidden,
                deprecated=deprecated,
                # Rich settings
                rich_help_panel=rich_help_panel,
                **kwargs,
            )(_strip_static(func))  # pyright: ignore[reportCallIssue, reportArgumentType]
            return func

        return make_command

    @classmethod
    def group(
        cmd,  # pyright: ignore[reportSelfClsParameterName]
        name: t.Optional[str] = Default(None),
        cls: t.Type[DTGroup] = DTGroup,
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: t.Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        # Command
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
        help: t.Optional[t.Union[str, Promise]] = Default(None),
        epilog: t.Optional[str] = Default(None),
        short_help: t.Optional[t.Union[str, Promise]] = Default(None),
        options_metavar: t.Optional[str] = Default(None),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = False,
        # Rich settings
        rich_help_panel: t.Union[str, None] = Default(None),
        **kwargs: t.Any,
    ) -> t.Callable[
        [
            t.Callable[
                t.Concatenate[TC, P], R  # pyright: ignore[reportInvalidTypeVarUse]
            ]
        ],
        Typer[P, R],
    ]:
        """
        Add a group to this command class after it has been defined. You can
        use this decorator to add groups to a root command from other Django apps.

        .. note::
            See :ref:`plugins` for details on when you might want to use this extension
            pattern.

        .. code-block:: python

            from your_app.management.commands.your_command import Command as YourCommand

            @YourCommand.group()
            def new_group(self, ...):
                # implement your group initializer here

            @new_group.command()
            def grp_command(self, ...):
                # implement group subcommand here

        :param name: the name of the group (defaults to the name of the decorated
            function)
        :param cls: the group class to use
        :param invoke_without_command: whether to invoke the group callback if no
            command was specified.
        :param no_args_is_help: whether to show the help if no arguments are provided
        :param subcommand_metavar: the metavar to use for subcommands in the help output
        :param chain: whether to chain commands, this allows multiple commands from the
            group to be specified and run in order sequentially in one call from the
            command line.
        :param result_callback: a callback to invoke with the result of the command
        :param context_settings: the click context settings to use - see
            :class:`click.Context`.
        :param help: the help string to use, defaults to the function docstring, if you
            need to translate the help you should use the help kwarg instead because
            docstrings will not be translated.
        :param epilog: the epilog to use in the help output
        :param short_help: the short help to use in the help output
        :param options_metavar: the metavar to use for options in the help output
        :param add_help_option: whether to add the help option to the command
        :param hidden: whether to hide this group from the help output
        :param deprecated: show a deprecation warning
        :param rich_help_panel: the rich help panel to use - if rich is installed
            this can be used to group commands into panels in the help output.
        """
        options_metavar = options_metavar or cmd.typer_app._info_val_str(
            "options_metavar"
        )
        if called_from_command_definition():
            return group(
                name=name,
                cls=cls,
                invoke_without_command=invoke_without_command,
                no_args_is_help=no_args_is_help,
                subcommand_metavar=subcommand_metavar,
                chain=chain,
                result_callback=result_callback,
                context_settings=context_settings,
                help=help,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                hidden=hidden,
                deprecated=deprecated,
                rich_help_panel=rich_help_panel,
                **kwargs,
            )

        def create_app(
            func: t.Callable[t.Concatenate[TC, P], R],
        ) -> Typer[P, R]:
            grp: Typer[P, R] = Typer(
                name=name or func.__name__.replace("_", "-"),
                cls=cls,
                invoke_without_command=invoke_without_command,
                no_args_is_help=no_args_is_help,
                subcommand_metavar=subcommand_metavar,
                chain=chain,
                result_callback=result_callback,
                callback=func,
                context_settings=context_settings,
                help=help,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                hidden=hidden,
                deprecated=deprecated,
                rich_help_panel=rich_help_panel,
                parent=None,
                **kwargs,
            )
            cmd.typer_app.add_typer(
                grp,
                name=name or func.__name__.replace("_", "-"),
                options_metavar=options_metavar,
            )
            return grp

        return create_app

    @classproperty
    def is_compound_command(cls) -> bool:
        """Return True if this command has more than a single executable block."""
        return bool(
            cls.typer_app.registered_groups
            or len(cls.typer_app.registered_commands) > 1
            or cls.typer_app.registered_callback
        )

    @property
    def _name(self) -> str:
        """The name of the django command"""
        return self.typer_app.info.name or self.__module__.rsplit(".", maxsplit=1)[-1]

    def __enter__(self):
        _command_context.__dict__.setdefault("stack", []).append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _command_context.stack.pop()
        if isinstance(exc_val, click.exceptions.Exit):
            sys.exit(exc_val.exit_code)
        if isinstance(exc_val, click.exceptions.UsageError):
            err_msg = (
                self.missing_args_message.format(
                    parameter=getattr(getattr(exc_val, "param", None), "name", "")
                )
                if isinstance(exc_val, click.exceptions.MissingParameter)
                else str(exc_val)
            )

            # we might be in a subcommand - so make sure we pull that help out
            # by walking up the context tree until we're at root
            cmd_pth: t.List[str] = []
            ctx = exc_val.ctx
            while ctx and ctx.parent:
                assert ctx.info_name
                cmd_pth.insert(0, ctx.info_name)
                ctx = ctx.parent
            if (
                getattr(self, "_called_from_command_line", False)
                and not self._traceback
            ):
                self.print_help(sys.argv[0], self._name, *cmd_pth)
                self.stderr.write(err_msg)
                sys.exit(1)
            raise CommandError(str(exc_val)) from exc_val

    def __init__(
        self,
        stdout: t.Optional[t.TextIO] = None,
        stderr: t.Optional[t.TextIO] = None,
        no_color: bool = no_color,
        force_color: bool = force_color,
        **kwargs: t.Any,
    ):
        assert self.typer_app.info.name
        _load_command_plugins(self.typer_app.info.name)
        _add_common_initializer(self)
        _resolve_help(self)

        self.force_color = force_color
        self.no_color = no_color
        with self:
            super().__init__(
                stdout=stdout,
                stderr=stderr,
                no_color=no_color,
                force_color=force_color,
                **kwargs,
            )
            # redo output pipes to use our wrappers that avoid
            # exceptions when strings are returned from command functions
            stdout_style_func = self.stdout.style_func
            stderr_style_func = self.stderr.style_func
            self.stdout = OutputWrapper(stdout or sys.stdout)
            self.stderr = OutputWrapper(stderr or sys.stderr)
            self.stdout.style_func = stdout_style_func
            self.stderr.style_func = stderr_style_func
            try:
                assert get_typer_command(self.typer_app)
            except RuntimeError as rerr:
                raise NotImplementedError(
                    f"No commands or command groups were registered on {self._name}"
                ) from rerr

    def get_subcommand(self, *command_path: str) -> CommandNode:
        """
        Retrieve a :class:`~django_typer.management.CommandNode` at the given command
        path.

        :param command_path: the path to the command to retrieve, where each argument
            is the string name in order of a group or command in the hierarchy.
        :return: the command node at the given path
        :raises LookupError: if no group or command exists at the given path
        """
        return self.command_tree.get_command(*command_path)

    def __init_subclass__(cls, **_):
        """Avoid passing typer arguments up the subclass init chain"""
        return super().__init_subclass__()

    def create_parser(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, prog_name: str, subcommand: str, **_
    ):
        """
        Create a parser for this command. This also sets the command
        context, so any functions below this call on the stack may
        use :func:`django_typer.utils.get_current_command` to retrieve the django
        command instance.

        :param prog_name: the name of the manage script that invoked the command
        :param subcommand: the name of the django command
        """
        with self:
            if getattr(self, "_called_from_command_line", False):
                script = get_usage_script(prog_name)
                if isinstance(script, Path):
                    prog_name = str(script)
                    if not str(prog_name).startswith(("..", "/", ".")):
                        prog_name = f"./{prog_name}"
                else:
                    prog_name = str(script)
            return TyperParser(self, prog_name, subcommand)

    def print_help(self, prog_name: str, subcommand: str, *cmd_path: str):
        """
        Print the help message for this command to stdout of the django command.

        :param prog_name: the name of the manage script that invoked the command
        :param subcommand: the name of the django command
        :param cmd_path: the path to the command to print the help for. This is
            an extension to the base class ``print_help()`` interface, required because
            typer/click have different helps for each subgroup or subcommand.
        """
        with self:
            self.create_parser(prog_name, subcommand).print_help(*cmd_path)

    def __getattr__(self, name: str) -> t.Any:
        """
        Do a breadth first search of the typer app tree to find a command or group
        and return that command or group if the attribute name matches the command/group
        function OR its registered CLI name.
        """
        init = getattr(
            self.typer_app.registered_callback,
            "callback",
            self.typer_app.info.callback,
        )
        if init and init and name == init.__name__:
            return BoundProxy(self, init)
        found = _bfs_match(self.typer_app, name)
        if found:
            return BoundProxy(self, found)
        raise AttributeError(
            "{cls} object has no attribute {name}".format(
                cls=self.__class__.__name__, name=name
            )
        )

    def __call__(self, *args, **kwargs):
        """
        Call this command's derived class
        :meth:`~django.core.management.BaseCommand.handle` implementation directly. Note
        this does not call the :meth:`~django.core.management.BaseCommand.handle`
        function below - but the :meth:`~django.core.management.BaseCommand.handle`
        function that was implemented on the deriving class if one exists.

        When simple commands are implemented using only the
        :meth:`~django.core.management.BaseCommand.handle` function we may invoke that
        handle function directly using this call operator:

        .. code-block:: python

            class Command(TyperCommand):

                def handle(self, option1: bool, option2: bool):
                    # invoked by this __call__

            my_command = get_command('my_command')

            # invoke the handle() function directly
            my_command(option1=True, option2=False)

        .. note::

            This only works for commands that implement
            :meth:`~django.core.management.BaseCommand.handle`. Commands that have
            multiple commands and groups are not required to implement
            :meth:`~django.core.management.BaseCommand.handle` and for those commands
            the functions should be invoked directly.

        :param args: the arguments to directly pass to
            :meth:`~django.core.management.BaseCommand.handle`
        :param kwargs: the options to directly pass to
            :meth:`~django.core.management.BaseCommand.handle`
        """
        with self:
            handle = getattr(self, "_handle", None) or getattr(
                self.typer_app,
                "handle",
                None,  # registered dynamically
            )
            if callable(handle):
                return handle(*args, **kwargs)
            raise NotImplementedError(
                f"{self.__class__} does not implement handle(), you must call the other"
                " command functions directly."
            )

    @t.no_type_check
    def _run(self, *args, **options):
        """
        Invoke the underlying Typer app with the given arguments and parameters.

        :param args: the arguments to pass to the command, may be strings needing
            to be parsed, or already resolved object types the argument ultimately
            resolves to. TODO - check this is true
        :param options: the options to pass to the command, may be strings needing
            to be parsed, or already resolved object types the option ultimately
            resolves to.
        :return: t.Any object returned by the Typer app
        """
        with self:
            result = self.typer_app(
                args=args,
                standalone_mode=False,
                supplied_params=options,
                django_command=self,
                complete_var=None,
                prog_name=f"{sys.argv[0]} {self.typer_app.info.name}",
            )
            if not self.is_compound_command and isinstance(
                self.typer_app.info.result_callback, Finalizer
            ):
                # result callbacks are not called on singular commands by click/typer
                #  we do that here to keep our interface consistent
                result = self.typer_app.info.result_callback(
                    result, **options, _command=self
                )
            self.stdout.disable = not self.print_result
            return result

    def run_from_argv(self, argv):
        """
        Wrap the :meth:`~django.core.management.BaseCommand.run_from_argv` method to
        push the command onto the stack so any code in frames below this can get a
        reference to the command instance using
        :func:`~django_typer.utils.get_current_command`.

        :param argv: the arguments to pass to the command
        """
        with self:
            return super().run_from_argv(argv)

    def execute(self, *args, **options):
        """
        Wrap the :meth:`~django.core.management.BaseCommand.execute` method to set and
        unset no_color and force_color options.

        This function pushes the command onto the stack so any frame
        below this call may use get_current_command() to get a reference
        to the command instance.

        args and options are passed to
        :meth:`~django.core.management.BaseCommand.handle`.

        :param args: the arguments to pass to the command
        :param options: the options to pass to the command
        :return: Any object returned by the command
        """
        no_color = self.no_color
        force_color = self.force_color
        skip_checks = self.skip_checks
        if options.get("no_color", None) is not None:
            self.no_color = options["no_color"]
        if options.get("force_color", None) is not None:
            self.force_color = options["force_color"]
        if options.get("skip_checks", None) is not None:
            self.skip_checks = options["skip_checks"]
        try:
            with self:
                # base class requires force_color, no_color and skip_checks to be
                # present - we allow them to be suppressed
                return super().execute(
                    *args,
                    **{
                        "force_color": self.force_color,
                        "no_color": self.no_color,
                        "skip_checks": self.skip_checks,
                        **options,
                    },
                )
        finally:
            self.no_color = no_color
            self.force_color = force_color
            self.skip_checks = skip_checks

    def echo(
        self, message: t.Optional[t.Any] = None, nl: bool = True, err: bool = False
    ):
        """
        A wrapper for `typer.echo()
        <https://typer.tiangolo.com/tutorial/printing/#typer-echo>`_ that response
        ``--no-color`` and ``--force-color`` flags, and writes to the command's stdout.

        :param message: The string or bytes to output. Other objects are
            converted to strings.
        :param err: Write to ``stderr`` instead of ``stdout``.
        :param nl: Print a newline after the message. Enabled by default.
        """

        return typer.echo(
            message=message,
            file=t.cast(t.IO[str], self.stderr._out if err else self.stdout._out),
            nl=nl,
            color=False if self.no_color else True if self.force_color else None,
        )

    def secho(
        self,
        message: t.Optional[t.Any] = None,
        nl: bool = True,
        err: bool = False,
        **styles: t.Any,
    ):
        """
        A wrapper for `typer.secho()
        <https://typer.tiangolo.com/tutorial/printing/#typersecho-style-and-print>`_
        that response ``--no-color`` and ``--force-color`` flags, and writes to the
        command's stdout.

        :param message: The string or bytes to output. Other objects are
            converted to strings.
        :param err: Write to ``stderr`` instead of ``stdout``.
        :param nl: Print a newline after the message. Enabled by default.
        :param styles: Styles to apply to the output
        """
        return typer.secho(
            message=message,
            file=t.cast(t.IO[str], self.stderr._out if err else self.stdout._out),
            nl=nl,
            color=False if self.no_color else True if self.force_color else None,
            **styles,
        )
