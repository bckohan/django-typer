from django_typer.management import TyperCommand


class Command(TyperCommand):
    print_result = True

    def handle(self):
        return "This will be printed"
