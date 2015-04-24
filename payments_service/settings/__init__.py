import os
from .base import *  # noqa
try:
    if os.environ.get('UNDER_TEST') == '1':
        print 'Not importing local settings under test'
    else:
        from .local import *  # noqa
except ImportError:
    print 'No local.py imported, skipping.'
