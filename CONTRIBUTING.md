# Contributing

Contributions are encouraged! Please use the issue page to submit feature requests or bug reports. Issues with attached PRs will be given priority and have a much higher likelihood of acceptance. Please also open an issue and associate it with any submitted PRs.

We are actively seeking additional maintainers. If you're interested, please open an issue or [contact me](https://github.com/bckohan).

## Installation

### Install Just

We provide a platform independent justfile with recipes for all the development tasks. You should [install just](https://just.systems/man/en/installation.html) if it is not on your system already.

`django-typer` uses [uv](https://docs.astral.sh/uv) for environment, package, and dependency management. ``just setup`` will install the necessary build tooling if you do not already have it:

```sh
just setup <python version>
```

**This will also install pre-commit** If you wish to submit code that does not pass pre-commit checks you can disable pre-commit by running:

```sh
just run pre-commit uninstall
```

### Install the Dev environment

To install all development dependencies run the ``install`` recipe:

```sh
just install
```

### Windows

There is a symbolic link to the top level examples directory in tests. On Windows to make sure this link is created you need to be in [developer mode](https://learn.microsoft.com/en-us/windows/apps/get-started/enable-your-device-for-development) and to configure git to allow symbolic links:

```console
git config --global core.symlinks true
```

## Documentation

`django-typer` documentation is generated using [Sphinx](https://www.sphinx-doc.org) with the [furo](https://github.com/pradyunsg/furo) theme. Any new feature PRs must provide updated documentation for the features added. To build the docs run doc8 to check for formatting issues then run Sphinx:

```sh
just docs  # builds docs
just check-docs  # lint the docs
just check-docs-links  # check for broken links in the docs
```

Run the docs with auto rebuild using:

```sh
just docs-live
```

## Static Analysis

`django-typer` uses [ruff](https://docs.astral.sh/ruff/) for Python linting, header import standardization and code formatting. [mypy](http://mypy-lang.org/) and [pyright](https://github.com/microsoft/pyright) are used for static type checking. Before any PR is accepted the following must be run, and static analysis tools should not produce any errors or warnings. Disabling certain errors or warnings where justified is acceptable:

To fix formatting and linting problems that are fixable run:

```sh
just fix
```

To run all static analysis without automated fixing you can run:

```sh
just check
```

## Running Tests

`django-typer` is set up to use [pytest](https://docs.pytest.org) to run unit tests. All the tests are housed in `tests`. Before a PR is accepted, all tests must be passing and the code coverage must be at 100%. A small number of exempted error handling branches are acceptable.

To run the full suite in an isolated virtual environment with only the minimal test dependencies installed you should use ``test-all``:

```sh
just test-all
```
To run the full test suite against a specific python/django you can pass sync options to ``test-all``. This requires the djXX dependency groups. For example to run against python 3.11 on Django 5.2.x:

```sh
just test-all -p 3.11 --group dj52
```

The other test commands will use the current synced virtual environment. To run a single test, or group of tests in a class:

```sh
just test <path_to_tests_file>::ClassName::FunctionName
```

For instance, to run all tests in BasicTests, and then just the test_call_command test you would do:

```sh
just test tests/test_basics.py::BasicTests
just test tests/test_basics.py::BasicTests::test_call_command
```

### Debugging tests

To debug a test use the ``debug-test`` recipe:

```sh
just debug-test tests/test_basics.py::BasicTests::test_call_command
```

This will set a breakpoint at the start of the test.

To run specific tests or debug tests against specific Python or Django versions you must first sync:

```sh
just install -p 3.11 --group dj52
just test -k test_call_command
just debug-test -k test_call_command
```

## Versioning

django-typer strictly adheres to [semantic versioning](https://semver.org).

## Issuing Releases

The release workflow is triggered by tag creation. You must have [git tag signing enabled](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits). Our justfile has a release shortcut:

```sh
just release x.x.x
```

## Just Recipes

```sh
benchmark                     # generate and document benchmarks
build                         # build src package and wheel
build-docs                    # build the docs
build-docs-html               # build html documentation
check                         # run all static checks
check-all                     # run all checks except documentation link checking (too slow!)
check-docs                    # lint the documentation
check-docs-links              # check the documentation links for broken links
check-format                  # check if the code needs formatting
check-lint                    # lint the code
check-package                 # run package checks
check-readme                  # check that the readme renders
check-types                   # run all static type checking
check-types-isolated          # run all static type checking in an isolated environment
check-types-mypy *RUN_ARGS    # run static type checking with mypy
check-types-pyright *RUN_ARGS # run static type checking with pyright
clean                         # remove all non repository artifacts
clean-docs                    # remove doc build artifacts
clean-env                     # remove the virtual environment
clean-git-ignored             # remove all git ignored files
coverage                      # generate the test coverage report
coverage-erase                # erase any coverage data
debug-test *TESTS             # debug an test (project venv)
docs                          # build and open the documentation
docs-live                     # serve the documentation, with auto-reload
fetch-refs LIB                # fetch the intersphinx references for the given package
fix                           # fix formatting, linting issues and import sorting
format                        # format the code and sort imports
install *OPTS="--all-extras"  # update and install development dependencies
install-basic                 # install without extra dependencies
install-precommit             # install git pre-commit hooks
install-psycopg3              # install with postgresql dependencies
install-uv                    # install the uv package manager
lint                          # sort the imports and fix linting issues
list-missed-tests             # run the tests and report if any were not run - sanity check
log-tests                     # run all tests and log them
manage *COMMAND               # run django-admin
open-docs                     # open the html documentation
precommit                     # run the pre-commit checks
release VERSION               # issue a relase for the given semver string (e.g. 2.1.0)
run +ARGS                     # run the command in the virtual environment
setup python="python"         # setup the venv, pre-commit hooks
sort-imports                  # sort the python imports
test *TESTS                   # run specific tests (project venv)
test-all *ENV                 # run all tests (isolated venv)
test-bash                     # test bash shell completions
test-fish                     # test fish shell completions
test-no-rich *ENV             # run the tests that require rich not to be installed (isolated venv)
test-powershell               # test powershell shell completions
test-pwsh                     # test pwsh shell completions
test-rich *ENV                # run the tests that require rich to be installed (isolated venv)
test-zsh                      # test zsh shell completions
validate_version VERSION      # validate the given version string against the lib version
zizmor                        # run zizmor security analysis of CI
```