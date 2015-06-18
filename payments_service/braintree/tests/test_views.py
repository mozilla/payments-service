import urllib

from django.conf import settings
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse

from nose.tools import eq_
from slumber.exceptions import HttpClientError

from payments_service.base.tests import AuthenticatedTestCase, TestCase


class TestTokenGenerator(AuthenticatedTestCase):

    def setUp(self):
        super(TestTokenGenerator, self).setUp()
        self.url = reverse('braintree:token.generate')

    def post(self):
        res = self.client.post(reverse('braintree:token.generate'))
        return self.json(res)

    def test_api_connection(self):
        # This is just a simple test to make sure the endpoint is
        # connected to Solitude.
        self.solitude.braintree.token.generate.post.return_value = {
            'token': 'some-token',
        }
        res, data = self.post()
        eq_(res.status_code, 200, res)
        eq_(data['token'], 'some-token')


class TestPayMethod(AuthenticatedTestCase):

    def setUp(self):
        super(TestPayMethod, self).setUp()
        self.url = reverse('braintree:mozilla.paymethod')
        self.pay_method = {'id': 1}  # pretend this is a paymethod object
        self.solitude.braintree.mozilla.paymethod.get.return_value = [
            self.pay_method,
        ]

    def get(self, query=None):
        url = self.url
        if query:
            url = '{url}?{query}'.format(url=url, query=query)
        return self.json(self.client.get(url))

    def test_arg_replacement(self):
        # Add some throw-away query parameters that will be replaced.
        res, data = self.get(query='braintree_buyer__buyer__uuid=nope')

        eq_(res.status_code, 200, res)
        eq_(data, [self.pay_method])
        call_args = self.solitude.braintree.mozilla.paymethod.get.call_args
        eq_(call_args,
            [tuple(),
             {'active': 1, 'braintree_buyer__buyer__uuid': self.buyer_uuid}])

    def test_override_active_flag(self):
        res, data = self.get(query='active=0')

        eq_(res.status_code, 200, res)
        call_args = self.solitude.braintree.mozilla.paymethod.get.call_args
        eq_(call_args[1]['active'], '0')


class TestSubscribe(AuthenticatedTestCase):
    nonce = 'some-braintree-nonce'
    plan_id = 'some-braintree-plan'

    def post(self, data=None, **overrides):
        if data is None:
            data = {'pay_method_nonce': self.nonce,
                    'plan_id': self.plan_id}
            data.update(overrides)
        return self.json(self.client.post(reverse('braintree:subscriptions'),
                                          data))

    def setup_generic_buyer(self):
        buyer_pk = 1234
        self.solitude.generic.buyer.get_object_or_404.return_value = {
            'resource_pk': buyer_pk,
        }
        return buyer_pk

    def setup_subscription_product(self):
        self.solitude.generic.product.get_object_or_404.return_value = {
            'resource_pk': 123
        }

    def setup_no_subscription_yet(self):
        self.setup_subscription_product()
        self.solitude.braintree.mozilla.subscription.get.return_value = []

    def setup_existing_subscription(self):
        self.setup_subscription_product()
        # Pretend this returns an existing subscription object.
        self.solitude.braintree.mozilla.subscription.get.return_value = [{}]

    def expect_new_pay_method(self):
        pay_method_uri = '/some/paymethod'
        self.solitude.braintree.paymethod.post.return_value = {
            'mozilla': {
                'resource_uri': pay_method_uri,
            }
        }
        return pay_method_uri

    def test_with_existing_customer(self):
        buyer_pk = self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        self.expect_new_pay_method()

        res, data = self.post()
        eq_(res.status_code, 204, res)

        (self.solitude.braintree.mozilla.buyer.get_object_or_404
         .assert_called_with(buyer=buyer_pk))
        assert not self.solitude.braintree.customer.post.called

        self.solitude.braintree.paymethod.post.assert_called_with({
            'buyer_uuid': self.buyer_uuid,
            'nonce': self.nonce,
        })

    def test_with_new_customer(self):
        self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        self.expect_new_pay_method()

        # Set up non-existing braintree customer.
        self.solitude.braintree.mozilla.buyer.get_object_or_404.side_effect = (
            ObjectDoesNotExist)

        res, data = self.post()
        eq_(res.status_code, 204, res)

        assert self.solitude.braintree.customer.post.called

    def test_with_new_pay_method(self):
        self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        pay_method_uri = self.expect_new_pay_method()

        res, data = self.post()
        eq_(res.status_code, 204, res)

        self.solitude.braintree.subscription.post.assert_called_with({
            'paymethod': pay_method_uri,
            'plan': self.plan_id,
        })

    def test_with_existing_pay_method(self):
        self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        pay_method_uri = '/my/saved/paymethod'

        res, data = self.post(data={'pay_method_uri': pay_method_uri,
                                    'plan_id': self.plan_id})
        eq_(res.status_code, 204, res)

        self.solitude.braintree.subscription.post.assert_called_with({
            'paymethod': pay_method_uri,
            'plan': self.plan_id,
        })

    def test_too_many_pay_methods(self):
        self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        pay_method_uri = '/my/saved/paymethod'

        res, data = self.post(data={
            'pay_method_uri': pay_method_uri,
            'pay_method_nonce': self.nonce,
            'plan_id': self.plan_id,
        })
        self.assert_form_error(res, ['__all__'])

    def test_bad_solitude_request(self):
        self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        exc = HttpClientError('bad request')
        exc.content = {'nonce': ['This field is required.']}
        self.solitude.braintree.paymethod.post.side_effect = exc

        res, data = self.post()
        self.assert_form_error(res, ['nonce'])

    def test_missing_pay_method(self):
        self.setup_no_subscription_yet()
        res, data = self.post({'plan_id': self.plan_id})
        self.assert_form_error(res, ['__all__'])

    def test_user_already_subscribed(self):
        self.setup_generic_buyer()
        self.setup_existing_subscription()

        res, data = self.post()
        self.assert_form_error(res, ['__all__'])
        assert self.solitude.braintree.mozilla.subscription.get.called


class TestWebhook(TestCase):

    def get(self, **params):
        params.setdefault('bt_challenge', 'challenge-code')
        url = '{url}?{q}'.format(url=reverse('braintree:webhook'),
                                 q=urllib.urlencode(params))
        return self.client.get(url)

    def post(self, data=None):
        if not data:
            data = {'bt_payload': 'p', 'bt_signature': 's'}
        return self.client.post(reverse('braintree:webhook'), data)

    def subscription_notice(self, kind='subscription_charged_successfully'):
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
                        "kind": "subscription_charged_successfully",
                        "next_billing_date": "2015-07-11T13:20:14.591",
                        "next_billing_period_amount": "10"
                    }
                },
                "subscription": {
                    "resource_pk": 1,
                    "resource_uri": "/braintree/mozilla/subscription/1/",
                    "paymethod": "/braintree/mozilla/paymethod/1/",
                    "seller_product": "/generic/product/1/",
                    "id": 1,
                    "provider_id": "some-bt:id"
                },
                "product": {
                    "seller": "/generic/seller/19/",
                    "resource_uri": "/generic/product/18/",
                    "resource_pk": 18,
                    "public_id": "mozilla-concrete-brick",
                    "external_id": "mozilla-concrete-brick"
                },
            },
            "braintree": {
                "kind": kind
            }
        }

    def test_verify(self):
        self.solitude.braintree.webhook.get.return_value = 'token'
        res = self.get(bt_challenge='f')
        self.solitude.braintree.webhook.get.assert_called_with(
            bt_challenge='f')
        eq_(res['Content-Type'], 'text/plain; charset=utf-8')
        eq_(res.status_code, 200)
        eq_(res.content, 'token')

    def test_bas_solitude_response_for_verify(self):
        self.solitude.braintree.webhook.get.side_effect = HttpClientError
        res = self.get()
        eq_(res.status_code, 400)

    def test_parse(self):
        post = self.solitude.braintree.webhook.post
        post.return_value = self.subscription_notice()

        data = {'bt_payload': 'p', 'bt_signature': 's'}
        res = self.post(data=data)

        self.solitude.braintree.webhook.post.assert_called_with(data)
        eq_(res.status_code, 200)

    def test_bad_solitude_response_for_parse(self):
        self.solitude.braintree.webhook.post.side_effect = HttpClientError
        res = self.post()
        eq_(res.status_code, 400)

    def test_send_email_for_subscription_charge(self):
        notice = self.subscription_notice()
        self.solitude.braintree.webhook.post.return_value = notice
        self.post()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject,
                         "You're subscribed to Brick")
        self.assertEqual(mail.outbox[0].to,
                         [notice['mozilla']['buyer']['email']])
        self.assertEqual(mail.outbox[0].from_email,
                         settings.SUBSCRIPTION_FROM_EMAIL)
        self.assertEqual(mail.outbox[0].reply_to,
                         [settings.SUBSCRIPTION_REPLY_TO_EMAIL])

        msg = mail.outbox[0].body
        assert 'Mozilla Concrete' in msg, 'Unexpected: {}'.format(msg)
        text = 'Receipt #     {}'.format(
            notice['mozilla']['transaction']['generic']['uuid']
        )
        assert text in msg, 'Unexpected: {}'.format(msg)
        assert 'Product       Brick' in msg, 'Unexpected: {}'.format(msg)
        assert 'Amount        $10.00' in msg, 'Unexpected: {}'.format(msg)
        assert 'Visa ending in 1234' in msg, 'Unexpected: {}'.format(msg)
        assert 'Period        11 Jun 2015 - 10 Jul 2015' in msg, (
            'Unexpected: {}'.format(msg)
        )
        assert 'TOTAL: $10.00' in msg, 'Unexpected: {}'.format(msg)
        assert 'Next payment: 11 Jul 2015' in msg, 'Unexpected: {}'.format(msg)

    def test_send_email_for_subscription_charge_failure(self):
        notice = self.subscription_notice(
            kind='subscription_charged_unsuccessfully'
        )
        self.solitude.braintree.webhook.post.return_value = notice
        self.post()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject,
                         'Brick: subscription charge failed')

        msg = mail.outbox[0].body
        assert 'Mozilla Concrete' in msg, 'Unexpected: {}'.format(msg)
        assert 'Visa ending in 1234' in msg, 'Unexpected: {}'.format(msg)
        assert 'Product       Brick' in msg, 'Unexpected: {}'.format(msg)
        assert 'Amount        $10.00' in msg, 'Unexpected: {}'.format(msg)
        assert 'Period        11 Jun 2015 - 10 Jul 2015' in msg, (
            'Unexpected: {}'.format(msg)
        )
        assert 'TOTAL: $10.00' in msg, 'Unexpected: {}'.format(msg)

    def test_ignore_inactionable_webhook(self):
        # Solitude returns a 204 when we do not need to act on the webhook.
        self.solitude.braintree.webhook.post.return_value = ''
        self.post()
        self.assertEqual(len(mail.outbox), 0)
