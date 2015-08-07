from django.core.urlresolvers import reverse

import mock
from nose.tools import eq_

from payments_service.base.tests import AuthenticatedTestCase


class TestGetTransactions(AuthenticatedTestCase):

    def setUp(self):
        super(TestGetTransactions, self).setUp()
        self.transaction_uri = '/transaction/1234/'
        self.seller_product_uri = '/product/1234/'
        self.uri_resources = self.setup_uri_lookups()

        self.api_transactions = [{
            'transaction': self.transaction_uri,
            'resource_pk': 1,
        }]
        self.solitude.braintree.mozilla.transaction.get.return_value = (
            self.api_transactions
        )

        self.uri_resources[self.transaction_uri].get_object.return_value = {
            'seller_product': self.seller_product_uri,
        }

        self.uri_resources[self.seller_product_uri].get_object.return_value = {
        }

    def setup_uri_lookups(self):
        resources = {
            self.transaction_uri: mock.Mock(),
            self.seller_product_uri: mock.Mock(),
        }

        def get_api_object(uri):
            res = resources.get(uri)
            if not res:
                raise ValueError('unknown uri {}'.format(uri))
            return res

        self.solitude.by_url.side_effect = get_api_object
        return resources

    def get(self):
        return self.json(
            self.client.get(reverse('braintree:transactions'))
        )

    def test_return_api_transactions(self):
        res, data = self.get()
        eq_(res.status_code, 200, res)
        eq_(data['transactions'], self.api_transactions)

    def test_only_get_user_transactions(self):
        self.get()

        get = self.solitude.braintree.mozilla.transaction.get
        eq_(get.call_args[1]['transaction__buyer__uuid'],
            self.buyer_uuid)

    def test_get_nested_uri_results(self):
        self.get()
        # Currently, nested URIs will be fetched to expand the result set.
        # For example, this URI would be fetched and its result inserted:
        # {
        #     "resource_pk": 1,
        #     "transaction": "/transaction/123/",
        # }
        assert self.uri_resources[self.transaction_uri].get_object.called
        assert self.uri_resources[self.seller_product_uri].get_object.called
