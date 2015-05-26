import mock

from payments_service.base.tests import AuthenticatedTestCase


class TransactionTestCase(AuthenticatedTestCase):

    def setUp(self):
        super(TransactionTestCase, self).setUp()
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
