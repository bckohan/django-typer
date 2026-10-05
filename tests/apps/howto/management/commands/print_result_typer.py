from django_typer.management import Typer

app = Typer()

app.django_command.print_result = True


@app.command()
def handle():
    return "This will be printed"
