import mock

from payments_service.auth import SolitudeBuyer

from .test_views.test_subscriptions import SubscriptionTest
from ..forms import ChangeSubscriptionPayMethodForm, ManageSubscriptionForm


class SubscriptionFormTest(SubscriptionTest):

    def setUp(self):
        super(SubscriptionFormTest, self).setUp()
        p = mock.patch('payments_service.braintree.utils.user_owns_resource')
        self.user_owns_resource = p.start()
        self.user_owns_resource.return_value = True
        self.addCleanup(p.stop)

    def submit(self, expect_errors=False):
        user = SolitudeBuyer(self.buyer_uuid, self.buyer_pk)
        Form, data = self.form_data()
        form = Form(user, data)
        if not expect_errors:
            assert form.is_valid(), form.errors.as_text()
        return form


class TestManageSubscriptionForm(SubscriptionFormTest):

    def form_data(self):
        return ManageSubscriptionForm, {
            'subscription_uri': self.subscription_uri,
        }

    def test_look_up_subscription_by_user(self):
        self.submit()

        self.user_owns_resource.assert_called_with(
            self.subscription_uri,
            {'paymethod__braintree_buyer__buyer': self.buyer_pk})

    def test_cannot_change_another_users_subscription(self):
        self.user_owns_resource.return_value = False

        form = self.submit(expect_errors=True)
        assert 'subscription_uri' in form.errors, (
            form.errors.as_text()
        )


class TestChangeSubscriptionPayMethodForm(SubscriptionFormTest):

    def form_data(self):
        return ChangeSubscriptionPayMethodForm, {
            'new_pay_method_uri': self.new_pay_method_uri,
            'subscription_uri': self.subscription_uri,
        }

    def test_look_up_paymethod_by_user(self):
        self.submit()

        self.user_owns_resource.assert_called_with(
            self.new_pay_method_uri,
            {'braintree_buyer__buyer__uuid': self.buyer_uuid})

    def test_cannot_use_another_users_paymethod(self):
        self.user_owns_resource.return_value = False

        form = self.submit(expect_errors=True)
        assert 'new_pay_method_uri' in form.errors, (
            form.errors.as_text()
        )
