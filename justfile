set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set unstable := true
set script-interpreter := ['uv', 'run', '--script']

export PYTHONPATH := source_directory()

[private]
default:
    @just --list --list-submodules

# run django-admin
[script]
manage *COMMAND:
    import os
    import sys
    import shlex
    from pathlib import Path
    from django.core import management
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings.base")
    management.execute_from_command_line(["just manage", *shlex.split("{{ COMMAND }}")])

# install the uv package manager
[linux]
[macos]
install-uv:
    curl -LsSf https://astral.sh/uv/install.sh | sh

# install the uv package manager
[windows]
install-uv:
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# setup the venv, pre-commit hooks
setup python="python":
    uv venv -p {{ python }}
    @just install-precommit

# install git pre-commit hooks
install-precommit:
    @just run --no-default-groups --group precommit --exact --isolated pre-commit install

# update and install development dependencies
install *OPTS="--all-extras":
    uv sync {{ OPTS }}

# install without extra dependencies
install-basic:
    uv sync

# install documentation dependencies
_install-docs:
    uv sync --no-default-groups --group docs --all-extras

# install with postgresql dependencies
install-psycopg3:
    uv sync --all-extras --group psycopg3

# run static type checking with mypy
check-types-mypy *ENV:
    @just run --no-default-groups --all-extras --group typing {{ ENV }} mypy

# run static type checking with pyright
check-types-pyright *ENV:
    @just run --no-default-groups --all-extras --group typing {{ ENV }} pyright

# run all static type checking
check-types *ENV:
    @just check-types-mypy {{ ENV }}
    @just check-types-pyright {{ ENV }}

# run all static type checking in an isolated environment
check-types-isolated *ENV:
    @just check-types-mypy {{ ENV }} --exact --isolated
    @just check-types-pyright {{ ENV }} --exact --isolated

# run package checks
check-package:
    uv pip check

# remove doc build artifacts
[script]
clean-docs:
    import shutil
    shutil.rmtree('./doc/build', ignore_errors=True)

# remove the virtual environment
clean-env:
    python -c "import shutil, pathlib; p=pathlib.Path('.venv'); shutil.rmtree(p, ignore_errors=True) if p.exists() else None"

# remove all git ignored files
clean-git-ignored:
    git clean -fdX

# remove all non repository artifacts
clean: clean-docs clean-git-ignored clean-env

# build html documentation
build-docs-html: _install-docs
    @just run sphinx-build --fresh-env --builder html --doctree-dir ./doc/build/doctrees ./doc/source ./doc/build/html

# [script]
# _open-pdf-docs:
#     import webbrowser
#     from pathlib import Path
#     webbrowser.open(f"file://{Path('./doc/build/pdf/django-typer.pdf').absolute()}")
# # build pdf documentation
# build-docs-pdf: install-docs
#     @just run sphinx-build --fresh-env --builder latex --doctree-dir ./doc/build/doctrees ./doc/source ./doc/build/pdf
#     make -C ./doc/build/pdf
#     @just _open-pdf-docs

# build the docs
build-docs: build-docs-html

# build src package and wheel
build:
    uv build

# open the html documentation
[script]
open-docs:
    import os
    import webbrowser
    webbrowser.open(f'file://{os.getcwd()}/doc/build/html/index.html')

# build and open the documentation
docs: build-docs-html open-docs

# serve the documentation, with auto-reload
docs-live: _install-docs
    @just run --no-default-groups --group docs sphinx-autobuild doc/source doc/build --open-browser --watch src --port 8000 --delay 1

_link_check:
    -uv run sphinx-build -b linkcheck -Q -D linkcheck_timeout=10 ./doc/source ./doc/build
    -uv run --no-default-groups --group docs sphinx-build -b linkcheck -Q -D linkcheck_timeout=10 ./doc/source ./doc/build

# check the documentation links for broken links
[script]
check-docs-links: _link_check
    import os
    import sys
    import json
    from pathlib import Path
    # The json output isn't valid, so we have to fix it before we can process.
    data = json.loads(f"[{','.join((Path(os.getcwd()) / 'doc/build/output.json').read_text().splitlines())}]")
    broken_links = [link for link in data if link["status"] not in {"working", "redirected", "unchecked", "ignored"}]
    if broken_links:
        for link in broken_links:
            print(f"[{link['status']}] {link['filename']}:{link['lineno']} -> {link['uri']}", file=sys.stderr)
        sys.exit(1)

# lint the documentation
check-docs *ENV:
    @just run {{ ENV }} --no-default-groups --group docs doc8 --ignore-path ./doc/build --max-line-length 100 -q ./doc

# fetch the intersphinx references for the given package
[script]
fetch-refs LIB: _install-docs
    import os
    from pathlib import Path
    import logging as _logging
    import sys
    import runpy
    from sphinx.ext.intersphinx import inspect_main
    _logging.basicConfig()

    libs = runpy.run_path(Path(os.getcwd()) / "doc/source/conf.py").get("intersphinx_mapping")
    url = libs.get("{{ LIB }}", None)
    if not url:
        sys.exit(f"Unrecognized {{ LIB }}, must be one of: {', '.join(libs.keys())}")
    if url[1] is None:
        url = f"{url[0].rstrip('/')}/objects.inv"
    else:
        url = url[1]

    raise SystemExit(inspect_main([url]))

# lint the code
check-lint *ENV:
    @just run {{ ENV }} --no-default-groups --group lint ruff check --select I
    @just run {{ ENV }} --no-default-groups --group lint ruff check

# check if the code needs formatting
check-format *ENV:
    @just run {{ ENV }} --no-default-groups --group lint ruff format --check
    @just run {{ ENV }} --no-default-groups --group lint ruff format --line-length 80 --check examples

# check that the readme renders
check-readme *ENV:
    @just run {{ ENV }} --no-default-groups --group lint -m readme_renderer ./README.md -o /tmp/README.html

# sort the python imports
sort-imports *ENV:
    @just run {{ ENV }} --no-default-groups --group lint ruff check --fix --select I

# format the code and sort imports
format *ENV: sort-imports
    just --fmt --unstable
    @just run {{ ENV }} --no-default-groups --group lint ruff format
    @just run {{ ENV }} --no-default-groups --group lint ruff format --line-length 80 examples

# sort the imports and fix linting issues
lint *ENV: sort-imports
    @just run {{ ENV }} --no-default-groups --group lint ruff check --fix

# fix formatting, linting issues and import sorting
fix *ENV:
    @just lint {{ ENV }}
    @just format {{ ENV }}

# run all static checks
check *ENV:
    @just check-lint {{ ENV }}
    @just check-format {{ ENV }}
    @just check-types {{ ENV }}
    @just check-package
    @just check-docs {{ ENV }}
    @just check-readme {{ ENV }}

# run all checks except documentation link checking (too slow!)
check-all *ENV:
    @just check {{ ENV }}
    @just zizmor

# run zizmor security analysis of CI
zizmor:
    cargo install --locked zizmor
    zizmor --format sarif .github/workflows/ > zizmor.sarif

_log-tests:
    uv run pytest --collect-only --disable-warnings -q --no-cov | uv run python -c "from pathlib import Path; import sys; Path('./tests/tests.log').unlink(missing_ok=True); open('./tests/tests.log', 'a').close(); open('./tests/all_tests.log', 'w').writelines(sys.stdin)"

# run the tests and report if any were not run - sanity check
[script]
list-missed-tests: install _log-tests test-all
    import sys
    from pathlib import Path
    test_log = Path("./tests/tests.log")
    all_tests = Path("./tests/all_tests.log")
    assert test_log.is_file() and all_tests.is_file()

    tests_run = set(test_log.read_text().splitlines())
    all_tests = set(all_tests.read_text().splitlines()[0:-2])
    if tests_run != all_tests:
        print("Not all tests were run:", file=sys.stderr)
        for test in all_tests - tests_run:
            print(test, file=sys.stderr)
        sys.exit(1)

# test bash shell completions
[script("bash")]
test-bash:
    pytest --cov-append tests/shellcompletion/test_shell_resolution.py::TestShellResolution::test_bash tests/test_parser_completers.py tests/shellcompletion/test_bash.py || exit
    pytest --cov-append tests/shellcompletion/test_bash.py::BashExeTests::test_prompt_install || exit

# test zsh shell completions
[script("zsh")]
test-zsh:
    pytest --cov-append tests/shellcompletion/test_shell_resolution.py::TestShellResolution::test_zsh tests/test_parser_completers.py tests/shellcompletion/test_zsh.py || exit
    pytest --cov-append tests/shellcompletion/test_zsh.py::ZshExeTests::test_prompt_install || exit

# test powershell shell completions
[script("powershell")]
test-powershell:
    pytest --cov-append tests/shellcompletion/test_shell_resolution.py::TestShellResolution::test_powershell tests/test_parser_completers.py tests/test_parser_completers.py tests/shellcompletion/test_powershell.py::PowerShellTests tests/shellcompletion/test_powershell.py::PowerShellExeTests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    pytest --cov-append tests/shellcompletion/test_powershell.py::PowerShellExeTests::test_prompt_install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# test pwsh shell completions
[script("pwsh")]
test-pwsh:
    pytest --cov-append tests/shellcompletion/test_shell_resolution.py::TestShellResolution::test_pwsh tests/test_parser_completers.py tests/shellcompletion/test_powershell.py::PWSHTests tests/shellcompletion/test_powershell.py::PWSHExeTests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    pytest --cov-append tests/shellcompletion/test_powershell.py::PWSHExeTests::test_prompt_install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# test fish shell completions
[script("fish")]
test-fish:
    pytest --cov-append tests/shellcompletion/test_shell_resolution.py::TestShellResolution::test_fish tests/test_parser_completers.py tests/shellcompletion/test_fish.py || exit
    pytest --cov-append tests/shellcompletion/test_fish.py::FishExeShellTests::test_prompt_install || exit

# run specific tests (project venv)
test *TESTS:
    @just run --group test --no-sync pytest {{ TESTS }}

# run the tests that require rich not to be installed (isolated venv)
test-no-rich *ENV:
    @just run --no-default-groups --exact --all-extras --group test --group colorama --isolated {{ ENV }} pytest --cov-append -m no_rich

# run the tests that require rich to be installed (isolated venv)
test-rich *ENV:
    @just run --no-default-groups --exact --all-extras --group test --group colorama --isolated {{ ENV }} pytest --cov-append -m rich

# run all tests (isolated venv)
test-all *ENV: coverage-erase
    @just test-rich {{ ENV }}
    @just test-no-rich {{ ENV }}
    uv run --no-default-groups --exact --all-extras --group test --group colorama --isolated {{ ENV }} pytest --cov-append -m "not rich and not no_rich"
    uv run --no-default-groups --exact --all-extras --group test --no-group colorama --isolated {{ ENV }} pytest --cov-append -k test_ctor_params

# debug a test (project venv)
debug-test *TESTS:
    @just run pytest \
      -o addopts='-ra -q' \
      -s --trace --pdbcls=IPython.terminal.debugger:Pdb \
      {{ TESTS }}

# run the pre-commit checks
precommit:
    @just run pre-commit

# erase any coverage data
coverage-erase:
    @just run --no-default-groups --group coverage coverage erase

# generate the test coverage report
coverage:
    @just run --no-default-groups --group coverage coverage combine --keep *.coverage
    @just run --no-default-groups --group coverage coverage report
    @just run --no-default-groups --group coverage coverage xml

# run the command in the virtual environment
run +ARGS:
    uv run {{ ARGS }}

# # generate translations using google translate
# translate: install-translate
#     @just manage translate --settings tests.settings.translate

# generate and document benchmarks
benchmark:
    @just run --no-dev --exact ./profiling/profile.py generate
    @just run --group profiling ./profiling/profile.py document

# validate the given version string against the lib version
[script]
validate_version VERSION:
    import re
    import tomllib
    import django_typer
    from packaging.version import Version
    raw_version = "{{ VERSION }}".lstrip("v")
    version_obj = Version(raw_version)
    # the version should be normalized
    assert str(version_obj) == raw_version
    # make sure all places the version appears agree
    assert raw_version == tomllib.load(open('pyproject.toml', 'rb'))['project']['version']
    assert raw_version == django_typer.__version__
    print(raw_version)

# issue a relase for the given semver string (e.g. 2.1.0)
release VERSION: install check-all
    @just validate_version v{{ VERSION }}
    git tag -s v{{ VERSION }} -m "{{ VERSION }} Release"
    git push https://github.com/django-commons/django-typer.git v{{ VERSION }}
