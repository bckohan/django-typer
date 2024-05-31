from django_typer import Typer
from django_typer.types import Verbosity

app = Typer()

# after the first Typer() call this module will have a Command class
# and we can modify it directly to remove the --settings option
Command.suppressed_base_arguments = ["--settings"]


@app.command()
def handle(verbosity: Verbosity = 1): ...
