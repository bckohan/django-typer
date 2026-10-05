"""
The base settings without DT_PRINT_RESULT - the 4.x default of not printing
values returned from commands.
"""

from .base import *  # noqa: F403

del DT_PRINT_RESULT  # noqa: F821
