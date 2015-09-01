from decimal import Decimal

from django.core.urlresolvers import reverse

import mock
from nose.tools import eq_
from slumber.exceptions import HttpClientError

from payments_service.base.tests import AuthenticatedTestCase


class TestSale(AuthenticatedTestCase):

    def setUp(self):
        super(TestSale, self).setUp()
        self.url = reverse('braintree:sale')
        self.default_data = {
            'amount': '10.00',
            'product_id': 'some-product-id',
            'nonce': 'some-braintree-nonce',
        }
        self.solitude.braintree.sale.post.return_value = {}

        p = mock.patch('payments_service.braintree.utils.user_owns_resource')
        self.user_owns_resource = p.start()
        self.user_owns_resource.return_value = True
        self.addCleanup(p.stop)

    def post(self, **custom_data):
        data = self.default_data.copy()
        data.update(custom_data)
        return self.json(self.client.post(self.url, data))

    def test_post_ok(self):
        res, data = self.post()
        eq_(res.status_code, 204)
        self.solitude.braintree.sale.post.assert_called_with({
            'amount': Decimal(self.default_data['amount']),
            'product_id': self.default_data['product_id'],
            'nonce': self.default_data['nonce'],
            'paymethod': None,
        })

    def test_post_paymethod_ok(self):
        paymethod = '/some/paymethod/123/'
        res, data = self.post(nonce='', paymethod=paymethod)
        eq_(res.status_code, 204)
        args = self.solitude.braintree.sale.post.call_args[0][0]
        eq_(args['paymethod'], paymethod)
        eq_(args['nonce'], '')

    def test_bad_solitude_request(self):
        exc = HttpClientError('bad request')
        exc.content = {'product_id': ['Invalid product.']}
        self.solitude.braintree.sale.post.side_effect = exc

        res, data = self.post()
        self.assert_error_response(
            res, msg_patterns={'product_id': exc.content['product_id'][0]})
