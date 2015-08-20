import mock

from payments_service.auth import SolitudeBuyer

from .test_views.test_subscriptions import SubscriptionTest
from ..forms import (ChangeSubscriptionPayMethodForm,
                     ManageSubscriptionForm, SaleForm)


class PaymentFormTest(SubscriptionTest):

    def setUp(self):
        super(PaymentFormTest, self).setUp()
        p = mock.patch('payments_service.braintree.utils.user_owns_resource')
        self.user_owns_resource = p.start()
        self.user_owns_resource.return_value = True
        self.addCleanup(p.stop)

    def form_data(self):
        raise NotImplementedError(
            'this method should return a tuple of '
            'FormClass, default_form_data (dict)')

    def submit(self, expect_errors=False, data=None, overrides=None,
               user=None):
        if user is None:
            user = SolitudeBuyer(self.buyer_uuid, self.buyer_pk)
        Form, default_data = self.form_data()

        form_data = data or default_data
        form_data.update(overrides or {})
        form = Form(user, form_data)

        if not expect_errors:
            assert form.is_valid(), form.errors.as_text()
        return form


class TestManageSubscriptionForm(PaymentFormTest):

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


class TestChangeSubscriptionPayMethodForm(PaymentFormTest):

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


class TestSaleForm(PaymentFormTest):

    def form_data(self):
        return SaleForm, {
            'nonce': 'braintree-paymethod-nonce',
            'product_id': 'product-id',
            'amount': '10.00',
        }

    def submit_paymethod(self, paymethod='/paymethod/123/', **kwargs):
        return self.submit(overrides={'nonce': None,
                                      'paymethod': paymethod},
                           **kwargs)

    def test_valid(self):
        self.submit()

    def test_no_valid_pay_method(self):
        form = self.submit(overrides={'nonce': None, 'paymethod': None},
                           expect_errors=True)
        assert '__all__' in form.errors, (
            form.errors.as_text()
        )

    def test_paymethod_requires_sign_in(self):
        form = self.submit_paymethod(
            # Pretend this is a form submission without sign-in.
            user=False,
            expect_errors=True,
        )
        assert 'paymethod' in form.errors, (
            form.errors.as_text()
        )

    def test_cannot_steal_someones_pay_method(self):
        self.user_owns_resource.return_value = False

        form = self.submit_paymethod(expect_errors=True)
        assert 'paymethod' in form.errors, (
            form.errors.as_text()
        )
