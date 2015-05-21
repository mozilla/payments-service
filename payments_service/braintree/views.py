import logging

from django.core.exceptions import ObjectDoesNotExist

from rest_framework.views import APIView
from rest_framework.response import Response
from slumber.exceptions import HttpClientError

from .. import solitude
from ..base.views import error_400
from ..solitude import SolitudeBodyguard
from .forms import SubscriptionForm

log = logging.getLogger(__name__)


class TokenGenerator(SolitudeBodyguard):
    """
    Generate a client token to begin processing payments.
    """
    methods = ['post']
    resource = 'braintree.token.generate'


class Subscriptions(APIView):
    """
    Deals with Braintree plan subscriptions.
    """
    def __init__(self, *args, **kw):
        super(Subscriptions, self).__init__(*args, **kw)
        self.api = solitude.api()

    def post(self, request):
        form = SubscriptionForm(request.DATA)
        if not form.is_valid():
            return error_400(response=form.errors)

        buyer_uuid = request.user.pk
        try:
            self.set_up_customer(buyer_uuid)
            pay_method_uri = self.get_pay_method(
                buyer_uuid,
                form.cleaned_data['pay_method_uri'],
                form.cleaned_data['pay_method_nonce'])

            self.api.braintree.subscription.post({
                'paymethod': pay_method_uri,
                'plan': form.cleaned_data['plan_id'],
            })
        except HttpClientError, exc:
            return error_400(exception=exc)

        return Response({}, status=204)

    def get_pay_method(self, buyer_uuid, pay_method_uri, pay_method_nonce):
        if not pay_method_uri:
            log.info('creating new payment method for buyer {b}'
                     .format(b=buyer_uuid))
            pay_method = self.api.braintree.paymethod.post({
                'buyer_uuid': buyer_uuid,
                'nonce': pay_method_nonce,
            })
            pay_method_uri = pay_method['mozilla']['resource_uri']
        else:
            log.info('paying with saved payment method {m} for buyer {b}'
                     .format(b=buyer_uuid, m=pay_method_uri))

        return pay_method_uri

    def set_up_customer(self, buyer_uuid):
        # TODO: This can be simplified after:
        # https://github.com/mozilla/payments-service/issues/22
        buyer = self.api.generic.buyer.get_object_or_404(uuid=buyer_uuid)
        try:
            resource = self.api.braintree.mozilla.buyer(buyer['resource_pk'])
            resource.get_object_or_404()
            log.info('using existing braintree customer tied to buyer {b}'
                     .format(b=buyer))
        except ObjectDoesNotExist:
            log.info('creating new braintree customer for {buyer}'
                     .format(buyer=buyer_uuid))
            self.api.braintree.customer.post({'uuid': buyer_uuid})
