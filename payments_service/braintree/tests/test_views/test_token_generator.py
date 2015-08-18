from django.core.urlresolvers import reverse

from nose.tools import eq_

from payments_service.base.tests import TestCase


class TestTokenGenerator(TestCase):

    def setUp(self):
        super(TestTokenGenerator, self).setUp()
        self.url = reverse('braintree:token.generate')
        self.braintree_token = 'some-token'
        self.solitude.braintree.token.generate.post.return_value = {
            'token': self.braintree_token,
        }

    def post(self):
        res = self.client.post(reverse('braintree:token.generate'))
        return self.json(res)

    def test_get_braintree_token(self):
        res, data = self.post()
        eq_(res.status_code, 200, res)
        eq_(data['token'], self.braintree_token)

    def test_get_csrf_token(self):
        res, data = self.post()
        eq_(res.status_code, 200, res)
        assert 'csrf_token' in data, data
