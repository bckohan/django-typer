r"""
    ___ _                           _____                       
   /   (_) __ _ _ __   __ _  ___   /__   \_   _ _ __   ___ _ __ 
  / /\ / |/ _` | '_ \ / _` |/ _ \    / /\/ | | | '_ \ / _ \ '__|
 / /_//| | (_| | | | | (_| | (_) |  / /  | |_| | |_) |  __/ |   
/___,'_/ |\__,_|_| |_|\__, |\___/   \/    \__, | .__/ \___|_|   
     |__/             |___/               |___/|_|              

"""

import sys
from types import SimpleNamespace, MethodType
import typing as t

import click
import typer
from importlib import import_module
from django.core.management.base import BaseCommand
from django.core.management import get_commands
from typer import Typer
from typer.core import TyperCommand as CoreTyperCommand
from typer.core import TyperGroup as CoreTyperGroup
from typer.main import get_command as get_typer_command, MarkupMode, get_params_convertors_ctx_param_name_from_function
from typer.models import CommandFunctionType
from typer.models import Context as TyperContext
from typer.models import Default
from dataclasses import dataclass
import contextlib

from .types import (
    ForceColor,
    NoColor,
    PythonPath,
    Settings,
    SkipChecks,
    Traceback,
    Verbosity,
    Version,
)

VERSION = (0, 1, 0)

__title__ = "Django Typer"
__version__ = ".".join(str(i) for i in VERSION)
__author__ = "Brian Kohan"
__license__ = "MIT"
__copyright__ = "Copyright 2023 Brian Kohan"


__all__ = [
    "TyperCommand",
    "Context",
    "TyperGroupWrapper",
    "TyperCommandWrapper",
    "callback",
    "command",
    "get_command"
]

def get_command(
    command_name: str,
    *subcommand: str, 
    stdout: t.Optional[t.IO[str]]=None,
    stderr: t.Optional[t.IO[str]]=None,
    no_color: bool=False,
    force_color: bool=False
):
    # todo - add a __call__ method to the command class if it is not a TyperCommand and has no
    # __call__ method - this will allow this interface to be used for standard commands
    module = import_module(f'{get_commands()[command_name]}.management.commands.{command_name}')
    cmd = module.Command(stdout=stdout, stderr=stderr, no_color=no_color, force_color=force_color)
    if subcommand:
        method = cmd.get_subcommand(*subcommand).command._callback.__wrapped__
        return MethodType(method, cmd)  # return the bound method
    return cmd


class _ParsedArgs(SimpleNamespace):  # pylint: disable=too-few-public-methods
    def __init__(self, args, **kwargs):
        super().__init__(**kwargs)
        self.args = args

    def _get_kwargs(self):
        return {"args": self.args, **_common_options()}


class Context(TyperContext):
    """
    An extension of the click.Context class that adds a reference to
    the TyperCommand instance so that the Django command can be accessed
    from within click/typer callbacks that take a context.

    e.g. This is necessary so that get_version() behavior can be implemented
    within the Version type itself.
    """

    django_command: "TyperCommand"
    children: t.List["Context"]

    def __init__(
        self,
        command: click.Command,  # pylint: disable=redefined-outer-name
        parent: t.Optional["Context"] = None,
        django_command: t.Optional["TyperCommand"] = None,
        _resolved_params: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs,
    ):
        super().__init__(command, **kwargs)
        self.django_command = django_command
        if not django_command and parent:
            self.django_command = parent.django_command
        self.params.update(_resolved_params or {})
        self.children = []
        if parent:
            parent.children.append(self)


class DjangoAdapterMixin:  # pylint: disable=too-few-public-methods
    context_class: t.Type[click.Context] = Context

    def __init__(
        self,
        *args,
        callback: t.Optional[  # pylint: disable=redefined-outer-name
            t.Callable[..., t.Any]
        ] = None,
        params: t.Optional[t.List[click.Parameter]] = None,
        **kwargs,
    ):
        params = params or []
        self._callback = callback
        expected = [param.name for param in params[1:]]
        self_arg = params[0].name if params else "self"

        def call_with_self(*args, **kwargs):
            if callback:
                return callback(
                    *args,
                    **{
                        param: val for param, val in kwargs.items() if param in expected
                    },
                    **{
                        self_arg: getattr(click.get_current_context(), "django_command", None)
                    },
                )
            return None

        super().__init__(  # type: ignore
            *args,
            params=[
                *params[1:],
                *[param for param in COMMON_PARAMS if param.name not in expected],
            ],
            callback=call_with_self,
            **kwargs,
        )


class TyperCommandWrapper(DjangoAdapterMixin, CoreTyperCommand):
    pass


class TyperGroupWrapper(DjangoAdapterMixin, CoreTyperGroup):
    pass


def callback(  # pylint: disable=too-mt.Any-local-variables
    name: t.Optional[str] = Default(None),
    *,
    cls: t.Type[TyperGroupWrapper] = TyperGroupWrapper,
    invoke_without_command: bool = Default(False),
    no_args_is_help: bool = Default(False),
    subcommand_metavar: t.Optional[str] = Default(None),
    chain: bool = Default(False),
    result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
    # Command
    context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
    help: t.Optional[str] = Default(None),
    epilog: t.Optional[str] = Default(None),
    short_help: t.Optional[str] = Default(None),
    options_metavar: str = Default("[OPTIONS]"),
    add_help_option: bool = Default(True),
    hidden: bool = Default(False),
    deprecated: bool = Default(False),
    # Rich settings
    rich_help_panel: t.Union[str, None] = Default(None),
    **kwargs,
):
    def decorator(func: CommandFunctionType):
        func._typer_constructor_ = lambda cmd, **extra: cmd.typer_app.callback(
            name=name or extra.pop("name", None),
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
            **extra,
        )(func)
        return func

    return decorator


def command(
    name: t.Optional[str] = None,
    *args,
    cls: t.Type[TyperCommandWrapper] = TyperCommandWrapper,
    context_settings: t.Optional[t.Dict[t.Any, t.Any]] = None,
    help: t.Optional[str] = None,
    epilog: t.Optional[str] = None,
    short_help: t.Optional[str] = None,
    options_metavar: str = "[OPTIONS]",
    add_help_option: bool = True,
    no_args_is_help: bool = False,
    hidden: bool = False,
    deprecated: bool = False,
    # Rich settings
    rich_help_panel: t.Union[str, None] = Default(None),
    **kwargs,
):
    def decorator(func: CommandFunctionType):
        func._typer_constructor_ = lambda cmd, **extra: cmd.typer_app.command(
            name=name or extra.pop("name", None),
            *args,
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
            **extra,
        )(func)
        return func

    return decorator


class _TyperCommandMeta(type):
    def __new__(
        mcs,
        name,
        bases,
        attrs,
        cls: t.Optional[t.Type[CoreTyperGroup]] = TyperGroupWrapper,
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: t.Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        context_settings: t.Optional[t.Dict[t.Any, t.Any]] = Default(None),
        callback: t.Optional[t.Callable[..., t.Any]] = Default(None),
        help: t.Optional[str] = Default(None),
        epilog: t.Optional[str] = Default(None),
        short_help: t.Optional[str] = Default(None),
        options_metavar: str = Default("[OPTIONS]"),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = Default(False),
        add_completion: bool = True,
        rich_markup_mode: MarkupMode = None,
        rich_help_panel: t.Union[str, None] = Default(None),
        pretty_exceptions_enable: bool = True,
        pretty_exceptions_show_locals: bool = True,
        pretty_exceptions_short: bool = True
    ):
        """
        This method is called when a new class is created.
        """
        typer_app = Typer(
            name=mcs.__module__.rsplit(".", maxsplit=1)[-1],
            cls=cls,
            help=help or attrs.get("help", typer.models.Default(None)),
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
            add_completion=add_completion,
            rich_markup_mode=rich_markup_mode,
            rich_help_panel=rich_help_panel,
            pretty_exceptions_enable=pretty_exceptions_enable,
            pretty_exceptions_show_locals=pretty_exceptions_show_locals,
            pretty_exceptions_short=pretty_exceptions_short
        )

        def handle(self, *args, **options):
            return self.typer_app(
                args=args,
                standalone_mode=False,
                _resolved_params=options,
                django_command=self,
            )

        return super().__new__(
            mcs,
            name,
            bases,
            {
                "_handle": attrs.pop("handle", None),
                **attrs,
                "handle": handle,
                "typer_app": typer_app,
            },
        )

    def __init__(
        cls,
        name,
        bases,
        attrs,
        **kwargs
    ):
        """
        This method is called after a new class is created.
        """
        cls.typer_app.info.name = cls.__module__.rsplit(".", maxsplit=1)[-1]
        if cls._handle:
            if hasattr(cls._handle, "_typer_constructor_"):
                cls._handle._typer_constructor_(cls, name=cls.typer_app.info.name)
                del cls._handle._typer_constructor_
            else:
                cls.typer_app.command(cls.typer_app.info.name, cls=TyperCommandWrapper)(
                    cls._handle
                )

        for attr in attrs.values():
            if hasattr(attr, "_typer_constructor_"):
                attr._typer_constructor_(cls)
                del attr._typer_constructor_

        super().__init__(name, bases, attrs, **kwargs)


class TyperParser:

    @dataclass(frozen=True)
    class Action:
        dest: str
        required: bool = False

        @property
        def option_strings(self):
            return [self.dest]

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
        
        def populate_params(node):
            for param in node.command.params:
                self._actions.append(self.Action(param.name))
            for child in node.children.values():
                populate_params(child)

        populate_params(self.django_command.command_tree)
 
    def print_help(self, *command_path: str):
        self.django_command.command_tree.context.info_name = f'{self.prog_name} {self.subcommand}'
        command_node = self.django_command.get_subcommand(*command_path)
        with contextlib.redirect_stdout(self.django_command.stdout):
            command_node.print_help()

    def parse_args(self, args=None, namespace=None):
        try:
            cmd = get_typer_command(self.django_command.typer_app)
            with cmd.make_context(
                info_name=f'{self.prog_name} {self.subcommand}',
                django_command=self.django_command,
                args=list(args or [])
            ) as ctx:
                params = ctx.params
                def discover_parsed_args(ctx):
                    for child in ctx.children:
                        discover_parsed_args(child)
                        params.update(child.params)

                discover_parsed_args(ctx)
                
                return _ParsedArgs(
                    args=args or [], **{**_common_options(), **params}
                )
        except click.exceptions.Exit:
            sys.exit()

    def add_argument(self, *args, **kwargs):
        pass


def _common_options(
    version: Version = False,
    verbosity: Verbosity = 1,
    settings: Settings = "",
    pythonpath: PythonPath = None,
    traceback: Traceback = False,
    no_color: NoColor = False,
    force_color: ForceColor = False,
    skip_checks: SkipChecks = False,
):
    return {
        "version": version,
        "verbosity": verbosity,
        "settings": settings,
        "pythonpath": pythonpath,
        "traceback": traceback,
        "no_color": no_color,
        "force_color": force_color,
        "skip_checks": skip_checks,
    }


COMMON_PARAMS = get_params_convertors_ctx_param_name_from_function(_common_options)[0]
COMMON_PARAM_NAMES = [param.name for param in COMMON_PARAMS]


class TyperCommand(BaseCommand, metaclass=_TyperCommandMeta):
    """
    A BaseCommand extension class that uses the Typer library to parse
    arguments and options. This class adapts BaseCommand using a light touch
    that relies on most of the original BaseCommand implementation to handle
    default arguments and behaviors.

    The goal of django_typer is to provide full typer style functionality
    while maintaining compatibility with the Django management command system.
    This means that the BaseCommand interface is preserved and the Typer
    interface is added on top of it. This means that this code base is more
    robust to changes in the Django management command system - because most
    of the base class functionality is preserved but mt.Any typer and click
    internals are used directly to achieve this. We rely on robust CI to
    catch breaking changes in the click/typer dependencies.


    TODO - there is a problem with subcommand resolution and make_context()
    that needs to be addressed. Need to understand exactly how click/typer
    does this so it can be broken apart and be interface compatible with
    Django. Also when are callbacks invoked, etc - during make_context? or
    invoke? There is a complexity here with execute().

    TODO - lazy loaded command overrides.
    Should be able to attach to another TyperCommand like this and conflicts would resolve
    based on INSTALLED_APP precedence.
    
    class Command(TyperCommand, attach='app_label.command_name.subcommand1.subcommand2'):
        ...
    """

    class CommandNode:
        
        name: str
        command: t.Union[TyperCommandWrapper, TyperGroupWrapper]
        context: TyperContext
        children: t.Dict[str, "CommandNode"]

        def __init__(
            self,
            name: str,
            command: t.Union[TyperCommandWrapper, TyperGroupWrapper],
            context: TyperContext
        ):
            self.name = name
            self.command = command
            self.context = context
            self.children = {}

        def print_help(self):
            self.command.get_help(self.context)

        def get_command(self, *command_path: str):
            if not command_path:
                return self
            try:
                return self.children[command_path[0]].get_command(*command_path[1:])
            except KeyError:
                raise ValueError(f'No such command "{command_path[0]}"')

    typer_app: Typer

    command_tree: CommandNode

    def __init__(
        self,
        stdout: t.Optional[t.IO[str]]=None,
        stderr: t.Optional[t.IO[str]]=None,
        no_color: bool=False,
        force_color: bool=False,
        **kwargs
    ):
        super().__init__(stdout=stdout, stderr=stderr, no_color=no_color, force_color=force_color, **kwargs)
        self.command_tree = self._build_cmd_tree(
            get_typer_command(self.typer_app)
        )
   
    def get_subcommand(self, *command_path: str):
        return self.command_tree.get_command(*command_path)
    
    def _filter_commands(
        self, ctx: TyperContext, cmd_filter: t.Optional[t.List[str]] = None
    ):
        return sorted(
            [
                cmd
                for name, cmd in getattr(
                    ctx.command,
                    'commands',
                    {
                        name: ctx.command.get_command(ctx, name)
                        for name in getattr(
                            ctx.command, 'list_commands', lambda _: []
                        )(ctx)
                        or cmd_filter or []
                    },
                ).items()
                if not cmd_filter or name in cmd_filter
            ],
            key=lambda item: item.name,
        )

    def _build_cmd_tree(
        self,
        cmd: CoreTyperCommand,
        parent: t.Optional[Context] = None,
        info_name: t.Optional[str] = None,
        node: t.Optional[CommandNode] = None
    ):
        ctx = Context(
            cmd,
            info_name=info_name,
            parent=parent,
            django_command=self
        )
        current = self.CommandNode(cmd.name, cmd, ctx)
        if node:
            node.children[cmd.name] = current
        for cmd in self._filter_commands(ctx):
            self._build_cmd_tree(cmd, ctx, info_name=cmd.name, node=current)
        return current


    def __init_subclass__(cls, **_):
        """Avoid passing typer arguments up the subclass init chain"""
        return super().__init_subclass__()

    def create_parser(self, prog_name: str, subcommand: str, **_):
        return TyperParser(self, prog_name, subcommand)
    
    def print_help(self, prog_name: str, subcommand: str, *cmd_path: str):
        """
        Print the help message for this command, derived from
        ``self.usage()``.
        """
        parser = self.create_parser(prog_name, subcommand)
        parser.print_help(*cmd_path)

    def handle(self, *args: t.Any, **options: t.Any) -> t.Any:
        pass  # pragma: no cover

    def __call__(self, *args, **kwargs):
        """
        Call this command's handle() directly.
        """
        if hasattr(self, "_handle"):
            return self._handle(*args, **kwargs)
        raise NotImplementedError(f"{self.__class__}")
