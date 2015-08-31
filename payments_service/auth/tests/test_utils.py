from django.core.exceptions import ObjectDoesNotExist

from payments_service.base.tests import TestCase

from .. utils import set_up_braintree_customer


class TestSetUpBraintreeCustomer(TestCase):

    def set_solitude_buyer_getter(self):
        buyer = {
            'uuid': 'buyer-uuid',
            'resource_pk': 1
        }
        self.solitude.generic.buyer.get_object.return_value = buyer
        return buyer

    def test_with_existing_customer(self):
        buyer = self.set_solitude_buyer_getter()
        set_up_braintree_customer(buyer)

        bt_getter = self.solitude.braintree.mozilla.buyer.get_object_or_404
        bt_getter.assert_called_with(buyer=buyer['resource_pk'])
        assert not self.solitude.braintree.customer.post.called

    def test_without_customer(self):
        buyer = self.set_solitude_buyer_getter()

        # Set up non-existing braintree customer.
        bt_getter = self.solitude.braintree.mozilla.buyer.get_object_or_404
        bt_getter.side_effect = ObjectDoesNotExist

        set_up_braintree_customer(buyer)

        self.solitude.braintree.customer.post.assert_called_with(
            {'uuid': buyer['uuid']}
        )
