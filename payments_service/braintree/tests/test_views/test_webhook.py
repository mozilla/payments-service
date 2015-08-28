import urllib

from django.conf import settings
from django.core import mail
from django.core.urlresolvers import reverse
from django.test import override_settings

import mock
from nose.tools import eq_
from slumber.exceptions import HttpClientError

from payments_service.base.tests import TestCase, WithFakePaymentsConfig

from .test_subscriptions import (subscription, seller_product,
                                 ExistingSubscriptionTest)


def subscription_notice(product_public_id,
                        kind='subscription_charged_successfully'):
    return {
        "mozilla": {
            "buyer": {
                "email": "email@example.com",
                "resource_pk": 1,
                "resource_uri": "/generic/buyer/1/",
                "uuid": "d5074761-eb08-4bd2-a08e-85b21f9df407"
            },
            "paymethod": {
                "resource_pk": 1,
                "resource_uri": "/braintree/mozilla/paymethod/1/",
                "braintree_buyer": "/braintree/mozilla/buyer/1/",
                "id": 1,
                "provider_id": "269f061d-d48c-48a9-8e4c-55a4acb3ea08",
                "type": 1,
                "type_name": "Visa",
                "truncated_id": "1234"
            },
            "transaction": {
                "generic": {
                    "amount": "10.00",
                    "buyer": "/generic/buyer/1/",
                    "currency": "USD",
                    "provider": 4,
                    "resource_pk": 1,
                    "resource_uri": "/generic/transaction/1/",
                    "seller": "/generic/seller/1/",
                    "seller_product": "/generic/product/1/",
                    "status": 2,
                    "status_reason": "settled",
                    "type": 0,
                    "created": "2015-06-11T13:20:14.600",
                    "uid_pay": None,
                    "uid_support": "bt:id",
                    "uuid": "553e6540-5bf7-4e23-880e-b656f268a10e"
                },
                "braintree": {
                    "resource_pk": 1,
                    "resource_uri": "/generic/transaction/1/",
                    "paymethod": "/braintree/mozilla/paymethod/1/",
                    "subscription": "/braintree/mozilla/subscription/1/",
                    "transaction": "/generic/transaction/1/",
                    "id": 1,
                    "billing_period_end_date": "2015-07-10T13:20:14.591",
                    "billing_period_start_date": "2015-06-11T13:20:14.591",
                    "kind": kind,
                    "next_billing_date": "2015-07-11T13:20:14.591",
                    "next_billing_period_amount": "10"
                }
            },
            "subscription": subscription(),
            "product": seller_product(product_public_id),
        },
        "braintree": {
            "kind": kind
        }
    }


class TestWebhook(WithFakePaymentsConfig, ExistingSubscriptionTest):

    def get(self, **params):
        params.setdefault('bt_challenge', 'challenge-code')
        url = '{url}?{q}'.format(url=reverse('braintree:webhook'),
                                 q=urllib.urlencode(params))
        return self.client.get(url)

    def post(self, data=None):
        if not data:
            data = {'bt_payload': 'p', 'bt_signature': 's'}
        return self.client.post(reverse('braintree:webhook'), data)

    def test_verify(self):
        self.solitude.braintree.webhook.get.return_value = 'token'
        res = self.get(bt_challenge='f')
        self.solitude.braintree.webhook.get.assert_called_with(
            bt_challenge='f')
        eq_(res['Content-Type'], 'text/plain; charset=utf-8')
        eq_(res.status_code, 200)
        eq_(res.content, 'token')

    def test_bad_solitude_response_for_verify(self):
        self.solitude.braintree.webhook.get.side_effect = HttpClientError
        res = self.get()
        eq_(res.status_code, 400)

    def test_parse(self):
        post = self.solitude.braintree.webhook.post
        post.return_value = subscription_notice('service-subscription')

        data = {'bt_payload': 'p', 'bt_signature': 's'}
        res = self.post(data=data)

        self.solitude.braintree.webhook.post.assert_called_with(data)
        eq_(res.status_code, 200)

    def test_bad_solitude_response_for_parse(self):
        self.solitude.braintree.webhook.post.side_effect = HttpClientError
        res = self.post()
        eq_(res.status_code, 400)

    def test_email_for_subscription_charge(self):
        notice = subscription_notice('service-subscription')
        self.solitude.braintree.webhook.post.return_value = notice
        self.post()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject,
                         "You're subscribed to Fake Subscription")
        self.assertEqual(mail.outbox[0].to,
                         [notice['mozilla']['buyer']['email']])
        self.assertEqual(mail.outbox[0].from_email,
                         settings.SUBSCRIPTION_FROM_EMAIL)
        self.assertEqual(mail.outbox[0].reply_to,
                         [settings.SUBSCRIPTION_REPLY_TO_EMAIL])

        msg = mail.outbox[0].body
        assert 'Fake Service Provider' in msg, 'Unexpected: {}'.format(msg)
        text = 'Receipt #     {}'.format(
            notice['mozilla']['transaction']['generic']['uuid']
        )
        assert text in msg, 'Unexpected: {}'.format(msg)
        assert 'Product       Fake Subscription' in msg, (
            'Unexpected: {}'.format(msg)
        )
        assert 'Amount        $10.00' in msg, 'Unexpected: {}'.format(msg)
        assert 'Visa ending in 1234' in msg, 'Unexpected: {}'.format(msg)
        assert 'Period        11 Jun 2015 - 10 Jul 2015' in msg, (
            'Unexpected: {}'.format(msg)
        )
        assert 'TOTAL: $10.00' in msg, 'Unexpected: {}'.format(msg)
        assert 'Next payment: 11 Jul 2015' in msg, 'Unexpected: {}'.format(msg)

    def test_email_for_subscription_charge_failure(self):
        notice = subscription_notice(
            'service-subscription',
            kind='subscription_charged_unsuccessfully'
        )
        self.solitude.braintree.webhook.post.return_value = notice
        self.post()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject,
                         'Fake Subscription: subscription charge failed')

        msg = mail.outbox[0].body
        assert 'Fake Service Provider' in msg, 'Unexpected: {}'.format(msg)
        assert 'Visa ending in 1234' in msg, 'Unexpected: {}'.format(msg)
        assert 'Product       Fake Subscription' in msg, (
            'Unexpected: {}'.format(msg)
        )
        assert 'Amount        $10.00' in msg, 'Unexpected: {}'.format(msg)
        assert 'Period        11 Jun 2015 - 10 Jul 2015' in msg, (
            'Unexpected: {}'.format(msg)
        )
        assert 'TOTAL: $10.00' in msg, 'Unexpected: {}'.format(msg)

    def test_html_for_subscription_charge_failure(self):
        notice = subscription_notice(
            'service-subscription',
            kind='subscription_charged_unsuccessfully'
        )
        self.solitude.braintree.webhook.post.return_value = notice
        response = self.post()
        email = mail.outbox[0]
        eq_(email.alternatives[0][1], 'text/html')
        self.assertTemplateUsed(
            response,
            'braintree/emails/'
            'subscription_charged_unsuccessfully.html')

    def test_email_for_subscription_canceled(self):
        notice = subscription_notice(
            'service-subscription',
            kind='subscription_canceled'
        )
        self.solitude.braintree.webhook.post.return_value = notice
        self.post()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject,
                         'Fake Subscription: subscription canceled')

        msg = mail.outbox[0].body
        assert 'Product       Fake Subscription' in msg, (
            'Unexpected: {}'.format(msg)
        )
        assert 'Amount        $10.00' in msg, 'Unexpected: {}'.format(msg)
        assert 'TOTAL' not in msg, 'Unexpected: {}'.format(msg)

    def test_html_for_subscription_canceled(self):
        notice = subscription_notice(
            'service-subscription',
            kind='subscription_canceled'
        )
        self.solitude.braintree.webhook.post.return_value = notice
        response = self.post()
        email = mail.outbox[0]
        eq_(email.alternatives[0][1], 'text/html')
        self.assertTemplateUsed(
            response,
            'braintree/emails/'
            'subscription_canceled.html')

    def test_ignore_inactionable_webhook(self):
        # Solitude returns a 204 when we do not need to act on the webhook.
        self.solitude.braintree.webhook.post.return_value = ''
        self.post()
        self.assertEqual(len(mail.outbox), 0)


class TestDebug(WithFakePaymentsConfig, TestCase):

    def setUp(self):
        self.url = reverse('braintree:debug-email')
        super(TestDebug, self).setUp()
        notice = subscription_notice('service-subscription')
        # Mocking things out is the best.
        self.solitude.braintree.mozilla.transaction.get.return_value = (
            [notice['mozilla']['transaction']['braintree']]
        )

        results = {
            '/generic/transaction/1/': (
                notice['mozilla']['transaction']['generic']),
            '/braintree/mozilla/paymethod/1/': notice['mozilla']['paymethod'],
            '/generic/product/1/': notice['mozilla']['product']
        }

        def by_url(url, parser=None):
            res = mock.Mock()
            res.get.return_value = results[url]
            return res

        self.solitude.by_url = by_url

    def test_not_available(self):
        eq_(self.client.get(self.url).status_code, 403)

    @override_settings(DEBUG=True)
    def test_string_template(self):
        res = self.client.get(self.url)
        eq_(res.status_code, 200)
        self.assertTemplateUsed(
            res, 'braintree/emails/subscription_charged_successfully.html')
