from io import StringIO

from django.test import TestCase
from django.utils import translation

from django_typer.management import get_command


class TestHelpOptionTranslation(TestCase):
    def help_text(self, language):
        buffer = StringIO()
        with translation.override(language):
            get_command("shellcompletion", no_color=True, stdout=buffer).print_help(
                "./manage.py", "shellcompletion"
            )
        return buffer.getvalue()

    def test_help_option_translated(self):
        self.assertIn("Diese Nachricht anzeigen und beenden.", self.help_text("de"))
        # the cached help option follows the active language
        self.assertIn("Show this message and exit.", self.help_text("en"))
        self.assertIn("Diese Nachricht anzeigen und beenden.", self.help_text("de"))
