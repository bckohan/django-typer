from django.contrib.auth.models import Group

from django_typer.management import TyperCommand, command


class Command(TyperCommand, chain=True):
    # the initializer, every chained subcommand and the finalizer run in one
    # transaction - if any of them fails nothing is committed
    atomic = True

    @command()
    def create(self, name: str):
        Group.objects.create(name=name)

    @command()
    def rename(self, old: str, new: str):
        Group.objects.filter(name=old).update(name=new)

    @command()
    def delete(self, name: str):
        # raises Group.DoesNotExist if there is no such group
        Group.objects.get(name=name).delete()
