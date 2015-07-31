from django.core.urlresolvers import reverse

from nose.tools import eq_

from payments_service.base.tests import AuthenticatedTestCase


class TestTokenGenerator(AuthenticatedTestCase):

    def setUp(self):
        super(TestTokenGenerator, self).setUp()
        self.url = reverse('braintree:token.generate')

    def post(self):
        res = self.client.post(reverse('braintree:token.generate'))
        return self.json(res)

    def test_api_connection(self):
        # This is just a simple test to make sure the endpoint is
        # connected to Solitude.
        self.solitude.braintree.token.generate.post.return_value = {
            'token': 'some-token',
        }
        res, data = self.post()
        eq_(res.status_code, 200, res)
        eq_(data['token'], 'some-token')
