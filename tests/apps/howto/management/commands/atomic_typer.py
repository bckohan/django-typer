from django.contrib.auth.models import Group

from django_typer.management import Typer

app = Typer(chain=True)

# the initializer, every chained subcommand and the finalizer run in one
# transaction - if any of them fails nothing is committed
app.django_command.atomic = True


@app.command()
def create(name: str):
    Group.objects.create(name=name)


@app.command()
def rename(old: str, new: str):
    Group.objects.filter(name=old).update(name=new)


@app.command()
def delete(name: str):
    # raises Group.DoesNotExist if there is no such group
    Group.objects.get(name=name).delete()
