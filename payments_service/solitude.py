from django.conf import settings

from curling.lib import API


def api():
    return API(settings.SOLITUDE_URL)
