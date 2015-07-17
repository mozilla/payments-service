import json
import urllib

from django.conf import settings
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.template.base import StringOrigin
from django.test import override_settings, RequestFactory

import mock
from nose.tools import eq_
from slumber.exceptions import HttpClientError

from payments_service.braintree.views import PayMethod
from payments_service.base.tests import AuthenticatedTestCase, TestCase


def subscription_notice(kind='subscription_charged_successfully'):
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
        # pretend this is a paymethod object
        self.pay_method = {
            'resource_pk': 1,
            'resource_uri': reverse('braintree:mozilla.paymethod',
                                    args=['1']),
        }
        self.solitude.braintree.mozilla.paymethod.get.return_value = [
            self.pay_method,
        ]

    def get(self, query=None):
        url = self.url
        if query:
            url = '{url}?{query}'.format(url=url, query=query)
        return self.json(self.client.get(url))

    def test_get_does_replace(self):
        request = RequestFactory().get('/')

        class FakeUser:
            uuid = 'nope'

        request.user = FakeUser()
        eq_((['foo'], {'active': 1, 'braintree_buyer__buyer__uuid': 'nope'}),
            PayMethod().replace_call_args(request, request.method,
                                          ['foo'], {'f': 'b'}))

    def test_patch_does_not_replace(self):
        request = RequestFactory().patch('/')
        eq_((['foo'], {'f': 'b'}),
            PayMethod().replace_call_args(request, request.method,
                                          ['foo'], {'f': 'b'}))

    def test_override_active_flag(self):
        res, data = self.get(query='active=0')

        eq_(res.status_code, 200, res)
        call_args = self.solitude.braintree.mozilla.paymethod.get.call_args
        eq_(call_args[1]['active'], '0')

    def test_patch_inactive(self):
        res, pay_methods = self.get()
        pay_method = pay_methods[0]

        resource = mock.Mock()
        resource.get.return_value = {}
        resource.patch.return_value = {}
        self.solitude.braintree.mozilla.paymethod.return_value = resource
        res = self.client.patch(pay_method['resource_uri'],
                                data=json.dumps({'active': False}),
                                content_type='application/json')
        eq_(res.status_code, 200, res)
        resource.patch.assert_called_with({'active': False})

    def test_cannot_patch_another_buyers_paymethod(self):
        res, pay_methods = self.get()
        pay_method = pay_methods[0]

        resource = mock.Mock()
        # Simulate a 404 in case a buyer asks for a paymethod
        # belonging to another user.
        resource.get.side_effect = HttpClientError
        self.solitude.braintree.mozilla.paymethod.return_value = resource

        res = self.client.patch(pay_method['resource_uri'],
                                data=json.dumps({'active': False}),
                                content_type='application/json')
        eq_(res.status_code, 403, res)

        # Check that the filtering occurred like this:
        # braintree.mozilla.paymethod(1).get(braintree_buyer__buyer__uuid=uuid)
        eq_(self.solitude.braintree.mozilla.paymethod.call_args[0][0],
            str(self.pay_method['resource_pk']))
        eq_(resource.get.call_args[1]['braintree_buyer__buyer__uuid'],
            self.buyer_uuid)
        assert 'active' not in resource.get.call_args[1], (
            'should not filter GETs by `active` when patching in case '
            'inactive paymethods need to be patched.'
        )


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


class SubscriptionTest(AuthenticatedTestCase):

    def setUp(self):
        super(SubscriptionTest, self).setUp()
        self.new_pay_method_uri = '/new_pay_method_uri'
        self.subscription_uri = '/subscription_uri'

    def setup_uri_lookups(self, uri_404=None):
        resources = {
            self.subscription_uri: mock.Mock(),
            self.new_pay_method_uri: mock.Mock(),
        }

        def get_api_object(uri):
            res = resources.get(uri)
            if not res:
                raise ValueError('unknown uri {}'.format(uri))
            if uri_404 == uri:
                res.get_object_or_404.side_effect = ObjectDoesNotExist
            else:
                res.get_object_or_404.return_value = {}
            return res

        self.solitude.by_url.side_effect = get_api_object
        return resources


class TestChangeSubscriptionPayMethod(SubscriptionTest):

    def setUp(self):
        super(TestChangeSubscriptionPayMethod, self).setUp()
        self.url = reverse('braintree:subscriptions.paymethod.change')

    def setup_subscription_post(self):
        bt = self.solitude.braintree
        bt.subscription.paymethod.change.post.return_value = {}
        return bt.subscription.paymethod.change.post

    def post(self):
        return self.json(self.client.post(self.url, {
            'new_pay_method_uri': self.new_pay_method_uri,
            'subscription_uri': self.subscription_uri,
        }))

    def test_change_paymethod(self):
        self.setup_uri_lookups()
        api_post = self.setup_subscription_post()

        res, data = self.post()
        eq_(res.status_code, 204, res)

        eq_(api_post.call_args[0][0]['paymethod'], self.new_pay_method_uri)
        eq_(api_post.call_args[0][0]['subscription'], self.subscription_uri)


class TestCancelSubscription(SubscriptionTest):

    def setUp(self):
        super(TestCancelSubscription, self).setUp()
        self.url = reverse('braintree:subscriptions.cancel')

    def setup_subscription_post(self):
        bt = self.solitude.braintree
        bt.subscription.cancel.post.return_value = {}
        return bt.subscription.cancel.post

    def post(self):
        return self.json(self.client.post(self.url, {
            'subscription_uri': self.subscription_uri,
        }))

    def test_change_paymethod(self):
        self.setup_uri_lookups()
        api_post = self.setup_subscription_post()

        res, data = self.post()
        eq_(res.status_code, 204, res)

        eq_(api_post.call_args[0][0]['subscription'], self.subscription_uri)


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
        post.return_value = subscription_notice()

        data = {'bt_payload': 'p', 'bt_signature': 's'}
        res = self.post(data=data)

        self.solitude.braintree.webhook.post.assert_called_with(data)
        eq_(res.status_code, 200)

    def test_bad_solitude_response_for_parse(self):
        self.solitude.braintree.webhook.post.side_effect = HttpClientError
        res = self.post()
        eq_(res.status_code, 400)

    def test_email_for_subscription_charge(self):
        notice = subscription_notice()
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

    def test_email_for_subscription_charge_failure(self):
        notice = subscription_notice(
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

    def test_html_for_subscription_charge_failure(self):
        notice = subscription_notice(
            kind='subscription_charged_unsuccessfully'
        )
        self.solitude.braintree.webhook.post.return_value = notice
        response = self.post()
        email = mail.outbox[0]
        eq_(email.alternatives[0][1], 'text/html')
        self.assertTemplateUsed(
            response,
            'braintree/emails/'
            'subscription_charged_unsuccessfully.premailed.html')

    def test_email_for_subscription_canceled(self):
        notice = subscription_notice(
            kind='subscription_canceled'
        )
        self.solitude.braintree.webhook.post.return_value = notice
        self.post()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject,
                         'Brick: subscription canceled')

        msg = mail.outbox[0].body
        assert 'Product       Brick' in msg, 'Unexpected: {}'.format(msg)
        assert 'Amount        $10.00' in msg, 'Unexpected: {}'.format(msg)
        assert 'TOTAL' not in msg, 'Unexpected: {}'.format(msg)

    def test_ignore_inactionable_webhook(self):
        # Solitude returns a 204 when we do not need to act on the webhook.
        self.solitude.braintree.webhook.post.return_value = ''
        self.post()
        self.assertEqual(len(mail.outbox), 0)


class TestDebug(TestCase):

    def setUp(self):
        self.url = reverse('braintree:debug-email')
        super(TestDebug, self).setUp()
        notice = subscription_notice()
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
        # The debug page compiles the premailed html and runs
        # it through the Template parser.
        eq_(len(res.templates), 1)
        assert isinstance(res.templates[0].origin, StringOrigin)
