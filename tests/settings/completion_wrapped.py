"""
Settings for running the completion test suite through a wrapper command named
``manage`` that forwards to ``python manage.py`` - the documented workaround for
invocations like ``just manage`` or ``poetry run manage``.
"""

from .completion import *  # noqa: F403

DT_MANAGE_SCRIPT = "manage"
