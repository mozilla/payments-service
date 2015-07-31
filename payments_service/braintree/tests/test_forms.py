from nose.tools import eq_

from payments_service.auth import SolitudeBuyer

from .test_views.test_subscriptions import SubscriptionTest
from ..forms import ChangeSubscriptionPayMethodForm, ManageSubscriptionForm


class SubscriptionFormTest(SubscriptionTest):

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
        res = self.setup_uri_lookups()[self.subscription_uri]

        self.submit()

        # api.by_url('/subscription').get_object_or_404(...)
        get = res.get_object_or_404
        eq_(get.call_args[1]['paymethod__braintree_buyer__buyer'],
            self.buyer_pk)

    def test_cannot_change_another_users_subscription(self):
        self.setup_uri_lookups(uri_404=self.subscription_uri)

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
        res = self.setup_uri_lookups()[self.new_pay_method_uri]

        self.submit()

        # api.by_url('/paymethod').get_object_or_404(...)
        eq_(res.get_object_or_404.call_args[1]['braintree_buyer__buyer__uuid'],
            self.buyer_uuid)

    def test_cannot_use_another_users_paymethod(self):
        self.setup_uri_lookups(uri_404=self.new_pay_method_uri)

        form = self.submit(expect_errors=True)
        assert 'new_pay_method_uri' in form.errors, (
            form.errors.as_text()
        )
