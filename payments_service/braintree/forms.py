import logging

from django import forms
from django.core.exceptions import ObjectDoesNotExist

from .. import solitude

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


class ChangeSubscriptionPayMethodForm(forms.Form):
    new_pay_method_uri = forms.CharField(max_length=255)
    subscription_uri = forms.CharField(max_length=255)

    def __init__(self, user, *args, **kw):
        self.user = user
        super(ChangeSubscriptionPayMethodForm, self).__init__(*args, **kw)

    def clean_subscription_uri(self):
        uri = self.cleaned_data['subscription_uri']
        if not self.user_owns_resource(
            uri,
            {'paymethod__braintree_buyer__buyer': self.user.pk},
        ):
            raise forms.ValidationError(
                'subscription by URI does not exist or belongs to another user'
            )
        return uri

    def clean_new_pay_method_uri(self):
        uri = self.cleaned_data['new_pay_method_uri']
        if not self.user_owns_resource(
            uri,
            {'braintree_buyer__buyer__uuid': self.user.uuid},
        ):
            raise forms.ValidationError(
                'paymethod by URI does not exist or belongs to another user'
            )
        return uri

    def user_owns_resource(self, uri, lookup):
        try:
            # Get the resource at the URI filtered by the signed in user.
            # If the filtered result is empty (404) it means the user does not
            # own the resource.
            solitude.api().by_url(uri).get_object_or_404(**lookup)
            return True
        except ObjectDoesNotExist, exc:
            log.debug('{cls}: catching {e.__class__.__name__}: {e}'
                      .format(cls=self.__class__.__name__, e=exc))
            return False
