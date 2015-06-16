import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import Context
from django.template.loader import get_template

from dateutil.parser import parse as parse_date
from payments_config import products, sellers
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


class Webhook(UnprotectedAPIView):
    renderer_classes = [PlainTextRenderer]

    def __init__(self, *args, **kw):
        super(Webhook, self).__init__(*args, **kw)
        self.api = solitude.api()

    def get(self, request):
        try:
            result = self.api.braintree.webhook.get(
                bt_challenge=request.REQUEST.get('bt_challenge'))
            status = 200
        except HttpClientError, exc:
            log.info('webhook GET: ignoring bad request: '
                     '{e.__class__.__name__}: {e}'.format(e=exc))
            result = 'verification failed'
            status = 400
        return Response(result, status=status,
                        content_type='text/plain; charset=utf-8')

    def post(self, request):
        try:
            webhook_result = self.api.braintree.webhook.post({
                'bt_payload': request.DATA.get('bt_payload'),
                'bt_signature': request.DATA.get('bt_signature'),
            })
            if webhook_result:
                self.notify_buyer(webhook_result)
            else:
                # Solitude is configurred to return a 204 when we do
                # not need to act on the webhook.
                log.warning('not notifying buyer of webhook result; '
                            'received empty response (204)')
            result = ''
            # Even though this is an empty response,
            # Braintree expects it to be a 200.
            status = 200
        except HttpClientError, exc:
            log.info('webhook POST: ignoring bad request: '
                     '{e.__class__.__name__}: {e}'.format(e=exc))
            result = 'verification failed'
            status = 400

        return Response(result, status=status)

    def notify_buyer(self, result):
        log.debug('about to handle webhook: {s}'
                  .format(s=result))
        log.info('notifying buyer {b} about webhook of kind: {k}'
                 .format(b=result['mozilla']['buyer'],
                         k=result['braintree']['kind']))

        # TODO: get the real product.
        # https://github.com/mozilla/solitude/issues/481
        product = products['mozilla-concrete-brick']

        # TODO: use a real lookup in the config
        # https://github.com/mozilla/payments-config/issues/8
        sellers_by_product = {}
        for seller_id, seller in sellers.items():
            for p in seller.products:
                sellers_by_product[p.id] = seller

        bt_trans = result['mozilla']['transaction']['braintree']
        moz_trans = result['mozilla']['transaction']['generic']

        # TODO: get the actual seller name, not the ID.
        # https://github.com/mozilla/payments-config/issues/7
        # TODO: I think we need to get the actual price of the transaction here
        # (localized).
        # TODO: This assumes monthly subscriptions but we should figure that
        # out automatically.
        # TODO: link to terms and conditions for the payment.
        # TODO: maybe localize the email?
        # This will default to English.

        tpl = get_template('braintree/subscription_receipt.txt')
        text_body = tpl.render(Context(dict(
            product=product,
            seller=sellers_by_product[product.id],
            result=result,
            date=parse_date(moz_trans['created']).strftime('%d %b %Y'),
            transaction=moz_trans,
            # TODO: map type IDs to credit card names.
            # https://github.com/mozilla/payments-config/issues/6
            cc_type=result['mozilla']['paymethod']['type'],
            cc_truncated_id=result['mozilla']['paymethod']['truncated_id'],
            bill_start=parse_date(
                bt_trans['billing_period_start_date']).strftime('%d %b %Y'),
            bill_end=parse_date(
                bt_trans['billing_period_end_date']).strftime('%d %b %Y'),
            next_pay_date=parse_date(
                bt_trans['next_billing_date']).strftime('%d %b %Y'),
        )))

        connection = get_connection(fail_silently=False)
        mail = EmailMultiAlternatives(
            "You're subscribed to {prod.description}".format(prod=product),
            text_body,
            settings.SUBSCRIPTION_FROM_EMAIL,
            [result['mozilla']['buyer']['email']],
            reply_to=[settings.SUBSCRIPTION_REPLY_TO_EMAIL],
            connection=connection)

        # TODO: send an HTML email.
        # https://github.com/mozilla/payments-service/issues/59
        #
        # mail.attach_alternative(html_message, 'text/html')

        mail.send()
