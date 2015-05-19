from contextlib import contextmanager

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from nose.tools import raises

from payments_service import base
from payments_service.base.apps import BaseApp
from payments_service.base.tests import TestCase


@override_settings(DEBUG=False)
class TestBaseApp(TestCase):

    def setUp(self):
        super(TestBaseApp, self).setUp()
        self.app = BaseApp(base.__name__, base)

    @contextmanager
    def overrides(self, **kw):
        kw.setdefault('SESSION_COOKIE_SECURE', True)
        kw.setdefault('SECRET_KEY', 'some secret key')
        with self.settings(**kw):
            yield

    def test_valid_settings(self):
        with self.overrides():
            self.app.ready()

    @raises(ImproperlyConfigured)
    def test_insecure_session_cookie(self):
        with self.overrides(SESSION_COOKIE_SECURE=False):
            self.app.ready()

    @raises(ImproperlyConfigured)
    def test_default_secret_key(self):
        with self.overrides(SECRET_KEY=settings.SECRET_KEY):
            self.app.ready()
