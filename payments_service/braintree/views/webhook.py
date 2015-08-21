import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.http import HttpResponse
from django.template import Context
from django.template.loader import get_template

from dateutil.parser import parse as parse_date
from payments_config import products
from premailer import Premailer
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from slumber.exceptions import HttpClientError

from payments_service import solitude
from payments_service.base.views import error_403, UnprotectedAPIView
from payments_service.braintree.utils import recurring_amount

log = logging.getLogger(__name__)


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
            'recurring_amount': recurring_amount,
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


def parsed_date(date):
    return '{d.day} {d:%b} {d.year}'.format(d=parse_date(date))


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
