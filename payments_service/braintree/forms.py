import logging

from django import forms

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

    def clean(self):
        cleaned_data = super(SubscriptionForm, self).clean()
        pay_method_nonce = cleaned_data.get('pay_method_nonce')
        pay_method_uri = cleaned_data.get('pay_method_uri')

        method_missing = not pay_method_uri and not pay_method_nonce
        too_many_methods = pay_method_uri and pay_method_nonce

        if method_missing or too_many_methods:
            raise forms.ValidationError(
                'Either pay_method_nonce or pay_method_uri can be submitted')


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
    # A variable amount to pay for the product. This only applies to products
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
