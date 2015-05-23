import mock
from nose.tools import eq_, ok_

from payments_service.base.tests import TestCase
from payments_service.solitude import constants
from payments_service.solitude.transaction import Transaction
from payments_service.auth import SolitudeBuyer


class TestTransaction(TestCase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.session = {}
        self.buyer = SolitudeBuyer('uuid', 'pk')
        self.solitude.generic.product.get_object_or_404.return_value = {
            'seller': '/generic/seller/123/',
            'resource_uri': '/generic/product/456/'
        }
        self.solitude.generic.transaction.post.return_value = {
            'resource_uri': '/generic/transaction/789/',
            'resource_pk': '789'
        }
        self.transaction_mock = mock.Mock(name='transaction.mock')
        self.solitude.generic.transaction.return_value = self.transaction_mock

    def test_create_gets_product(self):
        Transaction(self.session).create(self.buyer, 'a-plan')
        self.solitude.generic.product.get_object_or_404.assert_called_with(
            external_id='a-plan'
        )

    def test_create_posts(self):
        Transaction(self.session).create(self.buyer, 'a-plan')
        self.solitude.generic.transaction.post.assert_called_with({
            'status': constants.STATUS_STARTED,
            'seller_product': '/generic/product/456/',
            'provider': constants.PROVIDER_BRAINTREE,
            'buyer': '/generic/buyer/pk/',
            'seller': '/generic/seller/123/',
            'type': constants.TYPE_PAYMENT
        })

    def test_session_updated(self):
        Transaction(self.session).create(self.buyer, 'a-plan')
        eq_(self.session[Transaction.key], '789')

    def create(self):
        obj = Transaction(self.session)
        obj.create(self.buyer, 'a-plan')
        return obj

    def test_reset(self):
        self.create().reset()
        ok_(Transaction.key not in self.session)

    def test_update(self):
        self.create().update(status_reason='test')
        self.transaction_mock.patch.assert_called_with(
            {'status_reason': 'test'})

    def test_errored(self):
        self.create().errored('WAT')
        self.transaction_mock.patch.assert_called_with(
            {'status': constants.STATUS_ERRORED, 'status_reason': 'WAT'})

    def test_succeeded(self):
        self.create().succeeded()
        self.transaction_mock.patch.assert_called_with(
            {'status': constants.STATUS_COMPLETED})
