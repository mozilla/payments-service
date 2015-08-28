import json
import re

from django.conf import settings
from django.conf.urls import patterns, url
from django.test import TestCase as DjangoTestCase
from django.test.utils import override_settings

import mock
import payments_config
from nose.tools import eq_
from rest_framework.views import APIView

from . import dynamic_urls


class APIMock(mock.Mock):
    """
    A mock wrapper that you should use for any curling/slumber API object.
    """

    def tolist(self, *args, **kw):
        """
        DRF can get into a infinite loop with Mock on this method. If you
        override the mock so it returns a value it works.

        This is a hack of the worst kind.
        """
        raise RuntimeError(
            'Attempt to serialise a Mock without the result being overridden.')


class TestCase(DjangoTestCase):

    def setUp(self):
        super(TestCase, self).setUp()

        # Since all endpoints pretty much use Solitude, set up the mock
        # for convenience.
        p = mock.patch('payments_service.solitude.api', autospec=True)
        api = p.start()
        self.addCleanup(p.stop)
        self.solitude = APIMock()
        api.return_value = self.solitude

    def assert_form_error(self, res, fields=[]):
        eq_(res.status_code, 400, res)
        res, data = self.json(res)
        assert 'error_response' in data, data
        for field in fields:
            assert field in data['error_response'], (
                'field {f} not in {d}'
                .format(f=field, d=data['error_response'])
            )

    def json(self, response):
        if response.status_code == 204:
            return response, None
        else:
            return response, json.loads(response.content)

    def prepare_session(self, **kwargs):
        """
        Prepare a session before running view code so that the view
        can access the session values.

        This simulates what Django middleware does at the end of each response.
        """
        session = self.client.session
        session.update(kwargs)
        session.save()
        # This loads the encrypted session into the request cookies so that the
        # view will parse it. The `session_key` is actually the session
        # contents.
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key


class AuthenticatedTestCase(TestCase):
    """
    Test case for views that require a user login.
    """

    def setUp(self):
        super(AuthenticatedTestCase, self).setUp()
        self.buyer_pk = 1234
        self.buyer_uuid = 'some-solitude-buyer-uuid'
        self.prepare_session(buyer={'uuid': self.buyer_uuid,
                                    'pk': self.buyer_pk})


# This sets up a module that we can patch dynamically with URLs.
@override_settings(ROOT_URLCONF='payments_service.base.tests.dynamic_urls')
class WithDynamicEndpoints(DjangoTestCase):
    """
    Mixin to allow registration of ad-hoc views.
    """

    def endpoint(self, view, url_regex=None):
        """
        Register a view function or view class temporarily
        as the handler for requests to /dynamic-endpoint
        """
        url_regex = url_regex or r'^dynamic-endpoint$'
        try:
            is_class = issubclass(view, APIView)
        except TypeError:
            is_class = False
        if is_class:
            view = view.as_view()
        dynamic_urls.urlpatterns = patterns(
            '',
            url(url_regex, view),
        )
        self.addCleanup(self._clean_up_dynamic_urls)

    def _clean_up_dynamic_urls(self):
        dynamic_urls.urlpatterns = None


fake_payments_config = {
    # Example of a service that sells subscription products at fixed prices.
    'service': {
        'email': 'support@fake-service-provider.org',
        'name': 'Fake Service Provider',
        'url': 'http://fake-service-provider.org/',
        'terms': 'http://fake-service-provider.org/terms/',
        'kind': 'products',
        'products': [
            {
                'id': 'subscription',
                'description': 'Fake Subscription',
                'amount': '10.00',
                'recurrence': 'monthly',
                'user_identification': 'fxa-auth',
            },
        ]
    },
    # Example of an organization that accepts donations.
    'org': {
        'email': 'support@some-org.org',
        'name': 'Some Organization',
        'url': 'http://some-org.org/',
        'terms': 'http://some-org.org/terms/',
        'kind': 'donations',
        'products': [
            {
                'id': 'donation',
                'description': 'Donation',
                'recurrence': None,
                'user_identification': None,
            },
            {
                'id': 'recurring-donation',
                'description': 'Recurring Donation',
                'recurrence': 'monthly',
                'user_identification': 'email',
            }
        ]
    },
}


class FormTest(TestCase):
    """
    A mixin for tests directly against form objects.
    """

    def assert_form_error(self, errors, error_key, msg=None):
        """
        Make assertions about a form error

        **errors**
            The ``form.errors`` property
        **error_key**
            The field name or ``__all__`` error key
        **msg=None**
            An optional regular expression pattern that will be
            used to check the error message.
        """
        assert error_key in errors, (
            'error_key {} not in {}'.format(error_key, errors.as_text())
        )
        if msg:
            actual_msg = ', '.join(e.message for e in
                                   errors.as_data()[error_key])
            assert re.match(msg, actual_msg), (
                'error message "{}" did not match pattern "{}"'
                .format(actual_msg, msg)
            )


class WithFakePaymentsConfig(TestCase):
    """
    A mixin for any test that wants to work with a fake payments_config
    object. This will patch the payments_config.products and
    payments_config.sellers attributes with predictable, fake values.
    """

    def setUp(self):
        super(WithFakePaymentsConfig, self).setUp()

        sellers, products = payments_config.populate(fake_payments_config)
        for attr, val in (('products', products),
                          ('sellers', sellers)):
            p = mock.patch.object(payments_config, attr, val)
            p.start()
            self.addCleanup(p.stop)
