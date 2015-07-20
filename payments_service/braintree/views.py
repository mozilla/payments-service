import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMultiAlternatives, get_connection
from django.http import HttpResponse
from django.template import Context
from django.template.loader import get_template

from dateutil.parser import parse as parse_date
from payments_config import products
from premailer import Premailer
from rest_framework.views import APIView
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from slumber.exceptions import HttpClientError

from .. import solitude
from ..base.views import error_400, error_403, UnprotectedAPIView
from ..solitude import SolitudeBodyguard
from .forms import (ChangeSubscriptionPayMethodForm, ManageSubscriptionForm,
                    SubscriptionForm)

log = logging.getLogger(__name__)


def parsed_date(date):
    return '{d.day} {d:%b} {d.year}'.format(d=parse_date(date))


class TokenGenerator(SolitudeBodyguard):
    """
    Generate a client token to begin processing payments.
    """
    methods = ['post']
    resource = 'braintree.token.generate'


def premail(source):
    p = Premailer(
        html=source,
        preserve_internal_links=True,
        exclude_pseudoclasses=False,
        keep_style_tags=False,
        include_star_selectors=True,
        remove_classes=False,
        strip_important=False,
        method='html',
        base_path=settings.EMAIL_URL_ROOT,
        base_url=settings.EMAIL_URL_ROOT,
        disable_basic_attributes=[],
        disable_validation=True
    )
    return p.transform(pretty_print=True)


class PayMethod(SolitudeBodyguard):
    """
    Get saved payment methods for the logged in buyer.
    """
    methods = ['get', 'patch']
    resource = 'braintree.mozilla.paymethod'

    def replace_call_args(self, request, method, args, kw):
        """
        Replace the GET parameters with custom values.

        This sets the right default parameters that we
        want to send to Solitude, allowing for some overrides.
        The important part is that it only lets you get
        payment methods for the logged in user.
        """
        if method.lower() != 'get':
            return args, kw

        replaced_kw = {
            'braintree_buyer__buyer__uuid': request.user.uuid,
        }
        if request.method.lower() == 'get':
            # When getting payment methods, default to active payment methods.
            # However, when doing a get *within* something like a patch
            # handler, do not restrict to active/inactive.
            replaced_kw['active'] = kw.get('active', True)

        return args, replaced_kw

    def patch(self, request, pk=None):
        """
        Allow patching of payment methods.

        * verify that the user wanting to make a patch is allowed too
        * send through the patch
        """
        # Get the active paymethod filtered by logged in user.
        res = self.get(request, pk=pk)

        if res.status_code != 200:
            # This would be a 404 if the user is trying to patch a
            # paymethod they do not own.
            log.warning(
                '_api_request returned: {} when trying to '
                'access paymethod: {}, user: {}'
                .format(res.status_code, pk, request.user.uuid)
            )
            return error_403('Not allowed')

        return super(PayMethod, self).patch(request, pk=pk)


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


class ChangeSubscriptionPayMethod(APIView):

    def post(self, request):
        form = ChangeSubscriptionPayMethodForm(request.user, request.DATA)
        if not form.is_valid():
            return error_400(response=form.errors)

        solitude.api().braintree.subscription.paymethod.change.post({
            'paymethod': form.cleaned_data['new_pay_method_uri'],
            'subscription': form.cleaned_data['subscription_uri'],
        })
        log.info('changed paymethod to {} for subscription {} belonging to '
                 'user {}'.format(form.cleaned_data['new_pay_method_uri'],
                                  form.cleaned_data['subscription_uri'],
                                  request.user))
        return Response({}, status=204)


class CancelSubscription(APIView):

    def post(self, request):
        form = ManageSubscriptionForm(request.user, request.DATA)
        if not form.is_valid():
            return error_400(response=form.errors)

        solitude.api().braintree.subscription.cancel.post({
            'subscription': form.cleaned_data['subscription_uri'],
        })
        log.info('user {} cancelled subscription {}'.format(
            request.user,
            form.cleaned_data['subscription_uri'],
        ))
        return Response({}, status=204)


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
                # Solitude is configured to return a 204 when we do
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

    def build_context(self, bt_trans, moz_trans, paymethod, product, kind):
        return {
            'bill_start': parsed_date(bt_trans['billing_period_start_date']),
            'bill_end': parsed_date(bt_trans['billing_period_end_date']),
            'cc_truncated_id': paymethod['truncated_id'],
            'cc_type': paymethod['type_name'],
            'date': parsed_date(moz_trans['created']),
            'kind': kind,
            'management_url': settings.MANAGEMENT_URL,
            'moz_trans': moz_trans,
            'next_pay_date': parsed_date(bt_trans['next_billing_date']),
            'product': product,
            'root_url': settings.EMAIL_URL_ROOT,
            'seller': product.seller,
            'transaction': moz_trans,
        }

    def render_txt(self, data, kind):
        template = get_template('braintree/emails/{}.txt'.format(kind))
        return template.render(Context(data))

    def render_html(self, data, kind, premailed):
        template = get_template('braintree/emails/{}.html'.format(kind))
        response = template.render(Context(data))
        if premailed:
            response = premail(response)
        return response

    def notify_buyer(self, result):
        log.debug('about to handle webhook: {s}'
                  .format(s=result))

        notice_kind = result['braintree']['kind']
        log.info('notifying buyer {b} about webhook of kind: {k}'
                 .format(b=result['mozilla']['buyer'],
                         k=notice_kind))

        product = products[result['mozilla']['product']['public_id']]
        bt_trans = result['mozilla']['transaction']['braintree']
        moz_trans = result['mozilla']['transaction']['generic']

        # TODO: link to terms and conditions for the payment.
        # https://github.com/mozilla/payments/issues/78
        # TODO: maybe localize the email?
        # This will default to English.

        if notice_kind == 'subscription_charged_successfully':
            subject = "You're subscribed to {prod.description}".format(
                prod=product,
            )
        elif notice_kind == 'subscription_charged_unsuccessfully':
            subject = '{prod.description}: subscription charge failed'.format(
                prod=product,
            )
        elif notice_kind == 'subscription_canceled':
            subject = '{prod.description}: subscription canceled'.format(
                prod=product,
            )
        else:
            raise ValueError(
                'No email configured for webhook notice: {}'
                .format(notice_kind)
            )

        data = self.build_context(
            bt_trans, moz_trans, result['mozilla']['paymethod'], product,
            notice_kind)
        connection = get_connection(fail_silently=False)

        mail = EmailMultiAlternatives(
            subject,
            self.render_txt(data, notice_kind),
            settings.SUBSCRIPTION_FROM_EMAIL,
            [result['mozilla']['buyer']['email']],
            reply_to=[settings.SUBSCRIPTION_REPLY_TO_EMAIL],
            connection=connection)

        if notice_kind in [
                'subscription_charged_successfully',
                'subscription_charged_unsuccessfully',
                'subscription_canceled']:
            mail.attach_alternative(
                self.render_html(data, notice_kind, True),
                'text/html')
        mail.send()


def debug_email(request):
    if not settings.DEBUG:
        return error_403('Only available in debug mode.')

    kind = request.GET.get('kind', 'subscription_charged_successfully')
    premailed = bool(request.GET.get('premailed', 0))
    log.info('Generating email with pre-mailed setting: {}'.format(premailed))
    webhook = Webhook()
    api = solitude.api()

    # Just get the last transaction.
    try:
        bt = api.braintree.mozilla.transaction.get()[0]
    except IndexError:
        raise IndexError(
            'No latest transaction found, ensure you buy a subscription and '
            'complete a webhook from braintree (or use the braintree_webhook '
            'command).'
        )
    moz = api.by_url(bt['transaction']).get()
    method = api.by_url(bt['paymethod']).get()
    product = products[api.by_url(moz['seller_product']).get()['public_id']]

    # Render the HTML.
    data = webhook.build_context(bt, moz, method, product, kind)
    response = webhook.render_html(data, kind, premailed)

    return HttpResponse(response, status=200)
