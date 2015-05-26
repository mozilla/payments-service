from nose.tools import eq_, ok_

from payments_service.solitude import constants
from payments_service.solitude.tests import TransactionTestCase
from payments_service.solitude.transaction import Transaction
from payments_service.auth import SolitudeBuyer


class TestTransaction(TransactionTestCase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.session = {}
        self.buyer = SolitudeBuyer('uuid', 'pk')

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

    def test_create_twice(self):
        # Check that the session resets the transaction on creation.
        Transaction(self.session).create(self.buyer, 'a-plan')
        with self.assertRaises(ValueError):
            Transaction(self.session).create(self.buyer, 'a-plan')

    def test_create_from_session(self):
        self.session = {Transaction.key: '123'}
        eq_(Transaction(self.session).id, '123')

    def create(self):
        obj = Transaction(self.session)
        obj.create(self.buyer, 'a-plan')
        return obj

    def test_reset(self):
        obj = self.create()
        obj.reset()
        eq_(obj.id, None)
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
