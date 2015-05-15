from . import base as _base_settings
from .base import *  # noqa
try:
    if _base_settings.UNDER_TEST:
        print 'Not importing local settings while under test'
    else:
        from .local import *  # noqa
except ImportError:
    print 'No local.py imported, skipping.'
