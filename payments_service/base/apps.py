import logging

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

log = logging.getLogger(__name__)


class BaseApp(AppConfig):
    """
    Default configuration for the payments_service app.
    """
    name = 'payments_service.base'

    def ready(self):
        if settings.DEBUG:
            log.warn('skipping app validation in debug mode')
            return
        else:
            log.info('validating app settings')

        if not settings.SESSION_COOKIE_SECURE:
            raise ImproperlyConfigured(
                'You cannot run in non-debug mode with '
                'SESSION_COOKIE_SECURE=False')

        if settings.SECRET_KEY == 'LOCAL_DEVELOPMENT':
            raise ImproperlyConfigured(
                'You cannot run in non-debug mode with '
                'the default SECRET_KEY')
