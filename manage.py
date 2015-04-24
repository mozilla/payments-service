#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    if 'test' in sys.argv[1:2]:
        os.environ.setdefault('UNDER_TEST', '1')

    os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                          "payments_service.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
