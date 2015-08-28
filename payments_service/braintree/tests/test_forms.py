from django.core.exceptions import ObjectDoesNotExist

import mock
from nose.tools import eq_

from payments_service.auth import SolitudeBuyer
from payments_service.base.tests import WithFakePaymentsConfig

from .test_views.test_subscriptions import ExistingSubscriptionTest
from ..forms import (ChangeSubscriptionPayMethodForm,
                     ManageSubscriptionForm, SaleForm, SubscriptionForm)


class PaymentFormTest(ExistingSubscriptionTest):

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


class TestSubscriptionForm(WithFakePaymentsConfig, PaymentFormTest):

    def setUp(self):
        super(TestSubscriptionForm, self).setUp()
        self.pay_method_nonce = 'some-bt-pay-method-nonce'
        self.plan_id = 'service-subscription'

    def form_data(self):
        return SubscriptionForm, {
            'pay_method_nonce': self.pay_method_nonce,
            'plan_id': self.plan_id,
        }

    def expect_non_existant_buyer(self):
        getter = self.solitude.generic.buyer.get_object_or_404
        getter.side_effect = ObjectDoesNotExist

    def expect_existing_buyer(self, uuid='some-uuid',
                              authenticated=False):
        self.solitude.generic.buyer.get_object_or_404.return_value = {
            'resource_pk': 1244,
            'uuid': uuid,
            'authenticated': authenticated,
        }

    def test_too_many_pay_methods(self):
        form = self.submit(
            expect_errors=True,
            overrides=dict(pay_method_uri='/my/saved/paymethod',
                           pay_method_nonce='some-nonce'),
        )
        assert '__all__' in form.errors, (
            form.errors.as_text()
        )

    def test_missing_pay_method(self):
        form = self.submit(
            expect_errors=True,
            overrides=dict(pay_method_uri=None,
                           pay_method_nonce=None),
        )
        assert '__all__' in form.errors, (
            form.errors.as_text()
        )

    def test_email_only_recurring_donation_creates_user(self):
        self.expect_non_existant_buyer()
        email = 'someone@somewhere.org'
        self.solitude.generic.buyer.post.return_value = {
            'uuid': 'created-uuid',
            'resource_pk': 1234,
        }

        form = self.submit(
            user=False,
            overrides=dict(plan_id='org-recurring-donation',
                           email=email))

        assert self.solitude.generic.buyer.post.called
        args = self.solitude.generic.buyer.post.call_args[0][0]
        eq_(args['email'], email)
        eq_(args['authenticated'], False)
        assert args['uuid'].startswith('service:unauthenticated:'), (
            args['uuid']
        )
        eq_(form.user.uuid, 'created-uuid')

    def test_reuse_email_buyer_if_not_authenticated(self):
        self.expect_existing_buyer(uuid='existing-uuid',
                                   authenticated=False)
        email = 'someone@somewhere.org'
        form = self.submit(
            user=False,
            overrides=dict(plan_id='org-recurring-donation',
                           email=email))
        eq_(form.user.uuid, 'existing-uuid')
        assert not self.solitude.generic.buyer.post.called

    def test_cannot_reuse_email_buyer_if_they_were_authenticated(self):
        self.expect_existing_buyer(authenticated=True)
        form = self.submit(
            expect_errors=True,
            user=False,
            overrides=dict(plan_id='org-recurring-donation',
                           email='someone@somewhere.org'))
        assert '__all__' in form.errors, (
            form.errors.as_text()
        )

    def test_recurring_donation_requires_email(self):
        form = self.submit(
            expect_errors=True,
            user=False,
            overrides=dict(plan_id='org-recurring-donation'))
        assert 'plan_id' in form.errors, (
            form.errors.as_text()
        )

    def test_cannot_subscribe_to_an_unknown_plan(self):
        form = self.submit(
            expect_errors=True,
            overrides=dict(plan_id='non-existant-plan'))
        assert 'plan_id' in form.errors, (
            form.errors.as_text()
        )

    def test_email_only_user_cannot_subscribe_to_an_auth_protected_plan(self):
        form = self.submit(
            expect_errors=True,
            user=False,
            overrides=dict(plan_id='service-subscription',
                           email='someone@somewhere.org'))
        assert 'plan_id' in form.errors, (
            form.errors.as_text()
        )
        assert not self.solitude.generic.buyer.post.called


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
