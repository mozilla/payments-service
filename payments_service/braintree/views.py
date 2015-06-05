import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.views import APIView
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from slumber.exceptions import HttpClientError

from .. import solitude
from ..base.views import error_400, UnprotectedAPIView
from ..solitude import SolitudeBodyguard
from .forms import SubscriptionForm

log = logging.getLogger(__name__)


class TokenGenerator(SolitudeBodyguard):
    """
    Generate a client token to begin processing payments.
    """
    methods = ['post']
    resource = 'braintree.token.generate'


class PayMethod(SolitudeBodyguard):
    """
    Get saved payment methods for the logged in buyer.
    """
    methods = ['get']
    resource = 'braintree.mozilla.paymethod'

    def replace_call_args(self, request, args, kw):
        """
        Replace the GET parameters with custom values.

        This sets the right default parameters that we
        want to send to Solitude, allowing for some overrides.
        The important part is that it only lets you get
        payment methods for the logged in user.
        """
        replaced_kw = {
            'active': kw.get('active', 1),  # active by default
            'braintree_buyer__buyer__uuid': request.user.uuid,
        }
        return tuple(), replaced_kw


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

        if settings.ALLOW_REPEAT_PAYMENTS:
            log.warn('not protecting against repeat subscriptions')
        else:
            # TODO: remove this after
            # https://github.com/mozilla/solitude/issues/466
            product = self.api.generic.product.get_object_or_404(
                public_id=form.cleaned_data['plan_id'],
            )
            # Check if the user is already subscribed to this plan.
            result = self.api.braintree.mozilla.subscription.get(
                paymethod__braintree_buyer__buyer=self.request.user.pk,
                seller_product=product['resource_pk'],
            )
            if len(result):
                log.info(
                    'buyer {buyer} is already subscribed to product {product}'
                    .format(buyer=self.request.user.pk,
                            product=product['resource_pk']))
                return error_400(
                    response='user is already subscribed to this product')

        try:
            self.set_up_customer(request.user)
            pay_method_uri = self.get_pay_method(
                request.user,
                form.cleaned_data['pay_method_uri'],
                form.cleaned_data['pay_method_nonce']
            )
            self.api.braintree.subscription.post({
                'paymethod': pay_method_uri,
                'plan': form.cleaned_data['plan_id'],
            })
        except HttpClientError, exc:
            log.debug('caught bad request from solitude: {e}'.format(e=exc))
            return error_400(exception=exc)

        return Response({}, status=204)

    def get_pay_method(self, buyer, pay_method_uri, pay_method_nonce):
        if not pay_method_uri:
            log.info('creating new payment method for buyer {b}'
                     .format(b=buyer.uuid))
            pay_method = self.api.braintree.paymethod.post({
                'buyer_uuid': buyer.uuid,
                'nonce': pay_method_nonce,
            })
            pay_method_uri = pay_method['mozilla']['resource_uri']
        else:
            log.info('paying with saved payment method {m} for buyer {b}'
                     .format(b=buyer.uuid, m=pay_method_uri))

        return pay_method_uri

    def set_up_customer(self, buyer):
        try:
            self.api.braintree.mozilla.buyer.get_object_or_404(
                buyer=buyer.pk)
            log.info('using existing braintree customer tied to buyer {b}'
                     .format(b=buyer))
        except ObjectDoesNotExist:
            log.info('creating new braintree customer for {buyer}'
                     .format(buyer=buyer.pk))
            self.api.braintree.customer.post({'uuid': buyer.uuid})


class PlainTextRenderer(BaseRenderer):
    media_type = 'text/plain'
    format = 'txt'

    def render(self, data, media_type=None, renderer_context=None):
        return data.encode(self.charset)


class Webhook(UnprotectedAPIView, SolitudeBodyguard):
    methods = ['post', 'get']
    resource = 'braintree.webhook'

    def perform_content_negotiation(self, request, **kw):
        """
        Braintree sends a request that has an Accept Header of
        u'*/*; q=0.5', u'application/xml', but we need to force
        DRF to return it as text/plain. The only way we can do that
        is to override the content negotiation and insert our rather
        boring plain text renderer.

        See https://github.com/braintree/braintree_python/issues/54
        """
        if request.method.lower() == 'get':
            renderer = PlainTextRenderer()
            return (renderer, renderer.media_type)
        return (super(self.__class__, self)
                .perform_content_negotiation(request, **kw))
