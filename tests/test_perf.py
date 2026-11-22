import os
from tests.utils import run_command
import time
import pytest
from pprint import pformat
from .utils import rich_installed
import platform


@pytest.mark.no_rich
@pytest.mark.skipif(
    rich_installed, reason="Rich should not be installed to test module bloat."
)
def test_performance_regression():
    env = dict(os.environ)

    # disable coverage
    for var in [
        "COVERAGE_PROCESS_START",
        "COV_CORE_SOURCE",
        "COV_CORE_CONFIG",
        "COV_CORE_DATAFILE",
        "PYTEST_XDIST_WORKER",
    ]:
        env.pop(var, None)

    start = time.perf_counter()
    result, stderr, retcode = run_command(
        "perf",
        "5",
        "--print",
        env={**env, "DJANGO_SETTINGS_MODULE": "tests.settings.perf_no_typer"},
    )
    end = time.perf_counter()
    if retcode:
        pytest.fail(stderr)
    assert result["print"]
    assert result["no_typer"] == 5
    mods_no_typer = result["modules"]
    no_typer_time = end - start

    start = time.perf_counter()
    result, stderr, retcode = run_command(
        "perf",
        "5",
        "--print",
        env={**env, "DJANGO_SETTINGS_MODULE": "tests.settings.perf_typer"},
    )
    end = time.perf_counter()
    if retcode:
        pytest.fail(stderr)
    assert result["print"]
    assert result["typer"] == 5
    mods_typer = result["modules"]
    typer_time = end - start

    start = time.perf_counter()
    result, stderr, retcode = run_command(
        "perf",
        "5",
        "--print",
        env={**env, "DJANGO_SETTINGS_MODULE": "tests.settings.perf_typer_no_app"},
    )
    end = time.perf_counter()
    if retcode:
        pytest.fail(stderr)
    assert result["print"]
    assert result["typer"] == 5
    mods_typer_no_app = result["modules"]
    typer_no_app_time = end - start

    # print the stats
    print("\nWithout typer:\n\t")
    print(f"\ttime: {no_typer_time:0.4f}")
    print(f"\tmodules: {len(mods_no_typer)}")

    print("\nWith typer:\n\t")
    print(f"\ttime: {typer_time:0.4f}")
    print(f"\tmodules: {len(mods_typer)}")

    print("\nWith typer, but app not installed:\n\t")
    print(f"\ttime: {typer_no_app_time:0.4f}")
    print(f"\tmodules: {len(mods_typer_no_app)}")

    # notify us if adding typer inflates module count by more than 25 percent -
    # Typer 0.29+ validates parameters with Pydantic, which alone loads ~60 modules
    assert len(mods_no_typer) / len(mods_typer) > 0.8, (
        f"Typer modules added: \n{pformat(set(mods_typer) - set(mods_no_typer))}"
    )
    assert len(mods_no_typer) / len(mods_typer_no_app) > 0.8, (
        f"Typer modules added: \n{pformat(set(mods_typer_no_app) - set(mods_no_typer))}"
    )

    # notify us if adding typer inflates command exec time by more than 20 percent
    assert no_typer_time / typer_time > 0.2
    assert no_typer_time / typer_no_app_time > 0.2


@pytest.mark.no_rich
@pytest.mark.skipif(
    rich_installed, reason="Rich should not be installed to test module bloat."
)
@pytest.mark.skipif(platform.system() != "Darwin", reason="Test is only for macOS")
def test_timing():
    env = dict(os.environ)
    # disable coverage
    for var in [
        "COVERAGE_PROCESS_START",
        "COV_CORE_SOURCE",
        "COV_CORE_CONFIG",
        "COV_CORE_DATAFILE",
        "PYTEST_XDIST_WORKER",
    ]:
        env.pop(var, None)

    result, stderr, retcode, no_typer_seconds = run_command(
        "perf",
        "5",
        env={**env, "DJANGO_SETTINGS_MODULE": "tests.settings.perf_no_typer"},
        time=True,
    )
    if retcode:
        pytest.fail(stderr)
    assert not result, "perf should not have printed"

    result, stderr, retcode, typer_seconds = run_command(
        "perf",
        "5",
        env={**env, "DJANGO_SETTINGS_MODULE": "tests.settings.perf_typer"},
        time=True,
    )
    if retcode:
        pytest.fail(stderr)
    assert not result, "perf should not have printed"

    result, stderr, retcode, typer_no_app_seconds = run_command(
        "perf",
        "5",
        env={**env, "DJANGO_SETTINGS_MODULE": "tests.settings.perf_typer_no_app"},
        time=True,
    )
    if retcode:
        pytest.fail(stderr)
    assert not result, "perf should not have printed"

    # print the stats
    print("\nWithout typer:\n\t")
    print(f"\ttime: {no_typer_seconds:0.4f}")

    print("\nWith typer:\n\t")
    print(f"\ttime: {typer_seconds:0.4f}")

    print("\nWith typer, but app not installed:\n\t")
    print(f"\ttime: {typer_no_app_seconds:0.4f}")

    # notify us if adding typer inflates command exec time by more than 20 percent
    assert no_typer_seconds / typer_seconds > 0.2
    assert no_typer_seconds / typer_no_app_seconds > 0.2
