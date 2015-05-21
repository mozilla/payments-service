from django import forms


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
