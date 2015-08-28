import logging
import uuid

from django import forms
import payments_config

from payments_service import solitude
from payments_service.auth import SolitudeBuyer

from . import utils

log = logging.getLogger(__name__)


class SubscriptionForm(forms.Form):
    """
    Input data for subscribing a user to a Braintree plan.
    """
    # A single use token representing the buyer's submitted payment method.
    pay_method_nonce = forms.CharField(max_length=255, required=False)
    # Solitude URI to an existing payment method for this buyer.
    pay_method_uri = forms.CharField(max_length=255, required=False)
    # Braintree subscription plan ID.
    plan_id = forms.CharField(max_length=255)
    # A custom amount to pay for the subscription. This only applies to
    # things like recurring donations. Solitude validates this value to make
    # sure you can't adjust fixed price subscriptions.
    amount = forms.DecimalField(required=False)
    email = forms.EmailField(required=False, max_length=254)

    def __init__(self, user, *args, **kwargs):
        # This is the currently signed in user. It may be None.
        self.user = user
        super(SubscriptionForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(SubscriptionForm, self).clean()
        pay_method_nonce = cleaned_data.get('pay_method_nonce')
        pay_method_uri = cleaned_data.get('pay_method_uri')

        method_missing = not pay_method_uri and not pay_method_nonce
        too_many_methods = pay_method_uri and pay_method_nonce

        if method_missing or too_many_methods:
            raise forms.ValidationError(
                'Either pay_method_nonce or pay_method_uri can be submitted')

        # Validate the product (the subscription plan) to make sure
        # it exists.
        plan_id = cleaned_data.get('plan_id')
        product = payments_config.products.get(plan_id)
        if not product:
            return self.add_error(
                'plan_id',
                forms.ValidationError('Unrecoginized plan_id: {}'
                                      .format(plan_id)))

        if not self.user:
            # If no user has been signed in, we will assume the subsciption
            # plan supports email-only subscriptions and raise the appropriate
            # errors if not.
            email = cleaned_data.get('email')
            if not email:
                return self.add_error(
                    'plan_id',
                    forms.ValidationError(
                        'While subscribing anonymously, '
                        'email cannot be empty'))
            else:
                self.validate_email_only_subscription(email, product)

    def validate_email_only_subscription(self, email, product):
        if product.user_identification != 'email':
            log.info('email-user {} cannot subscribe to plan '
                     '{} because user_identification={}'
                     .format(email, product.id,
                             product.user_identification))
            return self.add_error(
                'plan_id',
                forms.ValidationError(
                    'You cannot subscribe to this plan without '
                    'signing in first.'
                )
            )
        # TODO: this is currently not exactly right. This ignores the fact
        # that an authenticated buyer with this same email may exist in the
        # system so it would be bad to create a new one.
        log.info('Creating email-only buyer for email '
                 '{} and plan {}'.format(email, product.id))
        self.user = self.create_email_only_buyer(email)

    def create_email_only_buyer(self, email):
        api = solitude.api()
        buyer = api.generic.buyer.post({
            'email': email,
            'authenticated': False,
            'uuid': 'service:unauthenticated:{}'.format(uuid.uuid4())
        })
        log.info('Created email-only buyer {} for email {}'
                 .format(buyer['uuid'], email))
        return self.user_from_api(buyer)

    def user_from_api(self, buyer_api_result):
        return SolitudeBuyer(buyer_api_result['uuid'],
                             buyer_api_result['resource_pk'])


class ManageSubscriptionForm(forms.Form):
    subscription_uri = forms.CharField(max_length=255)

    def __init__(self, user, *args, **kw):
        self.user = user
        super(ManageSubscriptionForm, self).__init__(*args, **kw)

    def clean_subscription_uri(self):
        uri = self.cleaned_data['subscription_uri']
        if not utils.user_owns_resource(
            uri,
            {'paymethod__braintree_buyer__buyer': self.user.pk},
        ):
            raise forms.ValidationError(
                'subscription by URI does not exist or belongs to another user'
            )
        return uri


class ChangeSubscriptionPayMethodForm(ManageSubscriptionForm):
    new_pay_method_uri = forms.CharField(max_length=255)

    def clean_new_pay_method_uri(self):
        uri = self.cleaned_data['new_pay_method_uri']
        if not utils.user_owns_resource(
            uri,
            {'braintree_buyer__buyer__uuid': self.user.uuid},
        ):
            raise forms.ValidationError(
                'paymethod by URI does not exist or belongs to another user'
            )
        return uri


class DeletePayMethodForm(forms.Form):
    pay_method_uri = forms.CharField(max_length=255)

    def __init__(self, user, *args, **kw):
        super(DeletePayMethodForm, self).__init__(*args, **kw)
        self.user = user

    def clean_pay_method_uri(self):
        uri = self.cleaned_data['pay_method_uri']
        if not utils.user_owns_resource(
            uri,
            {'braintree_buyer__buyer__uuid': self.user.uuid},
        ):
            raise forms.ValidationError(
                'paymethod by URI does not exist or belongs to another user'
            )
        return uri


class SaleForm(forms.Form):
    """
    Input data for subscribing a user to a Braintree plan.
    """
    # A single use token representing the buyer's submitted payment method.
    nonce = forms.CharField(max_length=255, required=False)
    # Solitude URI to an existing payment method for this buyer.
    paymethod = forms.CharField(max_length=255, required=False)
    # ID from payments-config.
    product_id = forms.CharField(max_length=255)
    # A custom amount to pay for the product. This only applies to products
    # like donations.
    amount = forms.DecimalField(required=False)

    def __init__(self, user, *args, **kwargs):
        # This is the currently signed in user. It may be None.
        self.user = user
        super(SaleForm, self).__init__(*args, **kwargs)

    def clean_paymethod(self):
        paymethod = self.cleaned_data.get('paymethod')
        if not paymethod:
            return

        if not self.user:
            raise forms.ValidationError(
                'user must be signed-in to submit payment with a '
                'saved pay method')

        if not utils.user_owns_resource(
            paymethod,
            {'braintree_buyer__buyer__uuid': self.user.uuid},
        ):
            raise forms.ValidationError(
                'paymethod by URI does not exist or belongs to another user'
            )

        return paymethod
