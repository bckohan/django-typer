from .handle2 import Command as Handle


class Command(Handle):
    help = "Test various forms of handle override."

    def handle(self) -> str:
        return "handle4"
