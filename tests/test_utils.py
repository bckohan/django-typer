from django_typer.utils import (
    get_usage_script,
    accepts_var_kwargs,
    get_win_shell,
    detect_shell,
    parse_iso_duration,
    duration_iso_string,
)
from django.test import override_settings
from django.core.management import call_command
from pathlib import Path
from shellingham import ShellDetectionFailure
import shutil
import pytest
import subprocess
import sys
import os


check_frame = Path(__file__).parent / "frame_check.py"


def test_get_usage_script():
    assert (
        get_usage_script("/root/path/to/scrapt")
        == Path("/root/path/to/scrapt").absolute()
    )


def test_accepts_var_kwargs():
    def func1(a, b, **kwargs): ...

    def func2(**kwargs): ...

    def func3(named=None, **kwargs): ...

    def func4(named=None): ...

    def func5(a): ...

    def func6(): ...

    assert accepts_var_kwargs(func1)
    assert accepts_var_kwargs(func2)
    assert accepts_var_kwargs(func3)
    assert not accepts_var_kwargs(func4)
    assert not accepts_var_kwargs(func5)
    assert not accepts_var_kwargs(func6)


def test_call_frame_check():
    result = subprocess.run(
        [sys.executable, str(check_frame.absolute())], text=True, capture_output=True
    )
    assert result.stdout.splitlines() == [
        "False",
        "True",
        "False",
        "True",
        "False",
        "True",
    ]


@override_settings(INSTALLED_APPS=["tests.apps.bad", "django_typer"])
def test_register_bad_command_plugin():
    with pytest.raises(ValueError):
        call_command("bad")


@pytest.mark.skipif(
    bool(shutil.which("pwsh") or shutil.which("powershell")),
    reason="Only test when pwsh is unavailable",
)
def test_get_win_shell_no_pwsh():
    with pytest.raises(ShellDetectionFailure):
        get_win_shell()


@pytest.mark.skipif(
    bool(shutil.which("pwsh") or shutil.which("powershell")),
    reason="Only test when pwsh is unavailable",
)
def test_powershell_profile_fail():
    from django_typer.shells.powershell import PowerShellComplete

    with pytest.raises(Exception):
        PowerShellComplete().get_user_profile()


def test_detection_failure_no_env():
    shell = os.environ.pop("SHELL", "")
    try:
        with pytest.raises(ShellDetectionFailure):
            detect_shell(max_depth=0)
    finally:
        os.environ["SHELL"] = shell


def test_detection_env_fallback():
    shell = os.environ.pop("SHELL", "")
    os.environ["SHELL"] = "/bin/bash"
    try:
        assert detect_shell(max_depth=0)[0] == "bash"
    finally:
        os.environ["SHELL"] = shell


def test_detect_shell():
    assert detect_shell(max_depth=256)


def test_parse_iso_duration():
    from datetime import timedelta

    for duration in [
        timedelta(days=3, hours=4, minutes=30, seconds=15, microseconds=123456),
        timedelta(days=1, hours=12, minutes=0, seconds=0),
        timedelta(days=0, hours=23, minutes=45, seconds=30),
        timedelta(days=5, hours=0, minutes=15, seconds=5, microseconds=987654),
        timedelta(days=2, hours=8, minutes=0, seconds=0),
        -timedelta(days=3, hours=4, minutes=30, seconds=15, microseconds=123456),
        -timedelta(days=1, hours=12, minutes=0, seconds=0),
        -timedelta(days=2, hours=20, minutes=10, seconds=30),
        -timedelta(days=5, hours=6, minutes=0, seconds=50, microseconds=123000),
        -timedelta(days=10, hours=5, minutes=55, seconds=5),
        timedelta(),
        timedelta(days=1),
        timedelta(hours=2),
        timedelta(minutes=3),
        timedelta(seconds=4),
        timedelta(microseconds=5),
    ]:
        assert parse_iso_duration(duration_iso_string(duration)) == (duration, None)

    assert parse_iso_duration("") == (timedelta(), None)
    assert parse_iso_duration("-") == (-timedelta(), None)
    assert parse_iso_duration("+") == (timedelta(), None)

    with pytest.raises(ValueError):
        parse_iso_duration("?")

    with pytest.raises(ValueError):
        parse_iso_duration("=")

    with pytest.raises(ValueError):
        parse_iso_duration("P10DX1S")

    with pytest.raises(ValueError):
        parse_iso_duration("P10DT5H.43S")

    assert parse_iso_duration("-P2DT12H") == (-timedelta(days=2, hours=12), None)
    assert parse_iso_duration("P1") == (timedelta(), "1")
    assert parse_iso_duration("PT1") == (timedelta(), "1")
    assert parse_iso_duration("P2DT2H4") == (timedelta(days=2, hours=2), "4")
    assert parse_iso_duration("P2DT2H4M5") == (
        timedelta(days=2, hours=2, minutes=4),
        "5",
    )
    assert parse_iso_duration("P2DT2H4M5.") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5),
        None,
    )

    # microseconds are weird
    assert parse_iso_duration("P2DT2H4M5.000123") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5, microseconds=123),
        None,
    )
    assert parse_iso_duration("P2DT2H4M5.123456") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5, microseconds=123456),
        None,
    )

    assert parse_iso_duration("P2DT2H4M5.000123S") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5, microseconds=123),
        None,
    )
    assert parse_iso_duration("P2DT2H4M5.123456S") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5, microseconds=123456),
        None,
    )

    assert parse_iso_duration("P2DT2H4M5.00012") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5),
        "00012",
    )
    assert parse_iso_duration("P2DT2H4M5.12") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5),
        "12",
    )

    assert parse_iso_duration("P2DT2H4M5.00012S") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5, microseconds=120),
        None,
    )
    assert parse_iso_duration("P2DT2H4M5.12S") == (
        timedelta(days=2, hours=2, minutes=4, seconds=5, microseconds=120000),
        None,
    )

    assert parse_iso_duration("P2DT5.00012S") == (
        timedelta(days=2, seconds=5, microseconds=120),
        None,
    )
    assert parse_iso_duration("P2DT5.12S") == (
        timedelta(days=2, seconds=5, microseconds=120000),
        None,
    )

    assert parse_iso_duration("P2DT5.00012") == (timedelta(days=2, seconds=5), "00012")
    assert parse_iso_duration("P2DT5.12") == (timedelta(days=2, seconds=5), "12")

    assert parse_iso_duration("P2DT5.") == (timedelta(days=2, seconds=5), None)
    assert parse_iso_duration("P2DT5.") == (timedelta(days=2, seconds=5), None)

    assert parse_iso_duration("PT5") == (timedelta(), "5")
    assert parse_iso_duration("-PT5") == (-timedelta(), "5")

    # weeks (W = 7 days)
    assert parse_iso_duration("P1W") == (timedelta(weeks=1), None)
    assert parse_iso_duration("P2W") == (timedelta(days=14), None)
    assert parse_iso_duration("-P3W") == (-timedelta(days=21), None)
    assert parse_iso_duration("P2WT3H") == (timedelta(days=14, hours=3), None)
    assert parse_iso_duration("P1W2D") == (timedelta(days=9), None)

    # months (M before T = 30 days)
    assert parse_iso_duration("P1M") == (timedelta(days=30), None)
    assert parse_iso_duration("P2M") == (timedelta(days=60), None)
    assert parse_iso_duration("-P6M") == (-timedelta(days=180), None)
    assert parse_iso_duration("P1MT12H") == (timedelta(days=30, hours=12), None)
    assert parse_iso_duration("P2M3W") == (timedelta(days=60 + 21), None)

    # years (Y = 365 days)
    assert parse_iso_duration("P1Y") == (timedelta(days=365), None)
    assert parse_iso_duration("P2Y") == (timedelta(days=730), None)
    assert parse_iso_duration("-P1Y") == (-timedelta(days=365), None)
    assert parse_iso_duration("P1YT6H") == (timedelta(days=365, hours=6), None)

    # combined date designators
    assert parse_iso_duration("P1Y2M3W4D") == (
        timedelta(days=365 + 60 + 21 + 4),
        None,
    )
    assert parse_iso_duration("P1Y2M") == (timedelta(days=365 + 60), None)
    assert parse_iso_duration("P1Y6MT12H30M") == (
        timedelta(days=365 + 180, hours=12, minutes=30),
        None,
    )

    # partial / ambiguous with new designators
    assert parse_iso_duration("P1Y2") == (timedelta(days=365), "2")
    assert parse_iso_duration("P1Y2M3") == (timedelta(days=365 + 60), "3")


def _make_exe(path: Path) -> Path:
    """Create an executable file that shutil.which() can find on all platforms."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        path = path.with_suffix(".bat")
        path.write_text("@echo off\r\nexit /b 0\r\n")
    else:
        path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def test_get_usage_script_on_path(tmp_path, monkeypatch):
    """A script launched by name from the path reports its bare name."""
    script = _make_exe(tmp_path / "bin" / "dt_probe")
    monkeypatch.setenv("PATH", str(script.parent))
    assert shutil.which(script.name) == str(script)
    assert get_usage_script(str(script)) == script.name


def test_get_usage_script_shim_on_path(tmp_path, monkeypatch):
    """
    When the name on the path is a shim/wrapper (pyenv, asdf, .cmd wrappers on
    windows, ...) that launches the real script, the bare name is still the
    correct way to invoke it.
    """
    shim = _make_exe(tmp_path / "shims" / "dt_probe")
    script = _make_exe(tmp_path / "venv" / "bin" / "dt_probe")
    monkeypatch.setenv("PATH", str(shim.parent))
    assert shutil.which(script.name) == str(shim)
    assert get_usage_script(str(script)) == script.name


def test_get_usage_script_relative_path_to_script_on_path(tmp_path, monkeypatch):
    """
    Invoking the script on the path through a relative path (../venv/bin/x)
    still reports the bare name - the relative path must be normalized before
    comparing it to the path resolution.
    """
    script = _make_exe(tmp_path / "bin" / "dt_probe")
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(proj)
    monkeypatch.setenv("PATH", str(script.parent))
    relative = os.path.join("..", "bin", script.name)
    assert Path(relative).is_file()
    assert get_usage_script(relative) == script.name


def test_get_usage_script_shadowed_by_different_script_on_path(tmp_path, monkeypatch):
    """
    Invoking a different script by relative path that shares its name with a
    command on the path must report the relative path, not the name.
    """
    on_path = _make_exe(tmp_path / "bin" / "dt_probe")
    proj = tmp_path / "proj"
    local = _make_exe(proj / "dt_probe")
    monkeypatch.chdir(proj)
    monkeypatch.setenv("PATH", str(on_path.parent))
    # (on windows which() searches the cwd first and finds the local script)
    assert shutil.which(local.name)
    usage = get_usage_script(f".{os.sep}{local.name}")
    assert isinstance(usage, Path)
    assert usage == Path(local.name)


def test_get_usage_script_not_on_path(tmp_path, monkeypatch):
    """A script that cannot be found on the path reports its path from cwd."""
    script = _make_exe(tmp_path / "venv" / "bin" / "dt_probe")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert shutil.which(script.name) is None
    usage = get_usage_script(str(script))
    assert isinstance(usage, Path)
    assert usage == Path("venv") / "bin" / script.name


def test_get_usage_script_manage_script_setting(tmp_path, monkeypatch):
    """DT_MANAGE_SCRIPT overrides script detection when no script is given."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "proj" / "manage.py")])
    with override_settings(DT_MANAGE_SCRIPT="mycli"):
        assert get_usage_script() == "mycli"
        # an explicitly requested script still wins
        assert (
            get_usage_script(str(tmp_path / "x" / "y"))
            == (tmp_path / "x" / "y").absolute()
        )
    with override_settings(DT_MANAGE_SCRIPT=None):
        assert isinstance(get_usage_script(), Path)


def test_get_usage_script_manage_script_env(tmp_path, monkeypatch):
    """DT_MANAGE_SCRIPT in the environment is used when the setting is absent."""
    from django.conf import settings

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "proj" / "manage.py")])
    monkeypatch.delattr(settings._wrapped, "DT_MANAGE_SCRIPT", raising=False)
    monkeypatch.setenv("DT_MANAGE_SCRIPT", "envcli")
    assert get_usage_script() == "envcli"
    # the settings module wins over the environment
    with override_settings(DT_MANAGE_SCRIPT="mycli"):
        assert get_usage_script() == "mycli"


def test_create_parser_manage_script_setting():
    """The DT_MANAGE_SCRIPT setting is used as the prog name in command help."""
    from django_typer.management import get_command

    command = get_command("basic")
    command._called_from_command_line = True
    with override_settings(DT_MANAGE_SCRIPT="mycli"):
        assert command.create_parser("./manage.py", "basic").prog_name == "mycli"
    assert command.create_parser("./manage.py", "basic").prog_name == "./manage.py"


def test_manage_script_setting_help_usage():
    """DT_MANAGE_SCRIPT is used as the program name in help printed from the command line."""
    from tests.utils import run_command

    stdout, stderr, retcode = run_command(
        "basic", "--settings", "tests.settings.manage_script", "--help"
    )
    assert retcode == 0, stderr
    assert "Usage: mycli basic" in stdout
    assert "manage.py" not in stdout
