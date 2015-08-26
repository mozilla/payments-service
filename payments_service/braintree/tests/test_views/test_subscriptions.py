from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse

import mock
from nose.tools import eq_, raises
from slumber.exceptions import HttpClientError

from payments_service.base.tests import AuthenticatedTestCase


def subscription():
    return {
        "resource_pk": 1,
        "resource_uri": "/braintree/mozilla/subscription/1/",
        "paymethod": "/braintree/mozilla/paymethod/1/",
        "seller_product": "/generic/product/1/",
        "id": 1,
        "provider_id": "some-bt:id"
    }


def seller_product():
    return {
        "seller": "/generic/seller/19/",
        "resource_uri": "/generic/product/18/",
        "resource_pk": 18,
        "public_id": "mozilla-concrete-brick",
        "external_id": "mozilla-concrete-brick"
    }


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

    def test_with_new_pay_method(self):
        self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        pay_method_uri = self.expect_new_pay_method()

        res, data = self.post()
        eq_(res.status_code, 204, res)

        args = self.solitude.braintree.subscription.post.call_args[0][0]
        eq_(args['paymethod'], pay_method_uri)
        eq_(args['plan'], self.plan_id)

    def test_with_existing_pay_method(self):
        self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        pay_method_uri = '/my/saved/paymethod'

        res, data = self.post(data={'pay_method_uri': pay_method_uri,
                                    'plan_id': self.plan_id})
        eq_(res.status_code, 204, res)

        args = self.solitude.braintree.subscription.post.call_args[0][0]
        eq_(args['paymethod'], pay_method_uri)
        eq_(args['plan'], self.plan_id)

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

    def test_pay_a_custom_amount(self):
        self.setup_generic_buyer()
        self.setup_no_subscription_yet()
        self.expect_new_pay_method()

        res, data = self.post(amount='1.99')
        eq_(res.status_code, 204, res)

        args = self.solitude.braintree.subscription.post.call_args[0][0]
        eq_(args['amount'], Decimal('1.99'))


class SubscriptionTest(AuthenticatedTestCase):

    def setUp(self):
        super(SubscriptionTest, self).setUp()
        self.new_pay_method_uri = '/new_pay_method_uri'
        self.subscription_uri = '/subscription_uri'

        p = mock.patch('payments_service.braintree.views.webhook.premail',
                       autospec=True)
        self.premail = p.start()
        self.addCleanup(p.stop)

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


class TestGetSubscriptions(AuthenticatedTestCase):

    def setUp(self):
        super(TestGetSubscriptions, self).setUp()
        self.subscription_obj = subscription()
        self.seller_product = seller_product()

        bt = self.solitude.braintree
        bt.mozilla.subscription.get.return_value = [self.subscription_obj]

        url_getter = mock.Mock()
        # Respond to expanding the subscription.seller_product URI attribute.
        self.solitude.by_url.return_value = url_getter
        url_getter.get_object.return_value = self.seller_product

    def get(self):
        return self.json(
            self.client.get(reverse('braintree:subscriptions'))
        )

    def test_return_subscriptions(self):
        response, data = self.get()

        eq_(data['subscriptions'][0]['resource_uri'],
            self.subscription_obj['resource_uri'])
        eq_(response.status_code, 200)

    def test_expand_seller_product(self):
        response, data = self.get()

        eq_(data['subscriptions'][0]['seller_product'],
            self.seller_product)
        eq_(response.status_code, 200)

    def test_only_get_user_subscriptions(self):
        self.get()

        get = self.solitude.braintree.mozilla.subscription.get
        eq_(get.call_args[1]['paymethod__braintree_buyer__buyer'],
            self.buyer_pk)

    def test_only_get_active_subscriptions(self):
        self.get()

        get = self.solitude.braintree.mozilla.subscription.get
        eq_(get.call_args[1]['active'], True)

    @raises(HttpClientError)
    def test_bad_solitude_response(self):
        get = self.solitude.braintree.mozilla.subscription.get
        get.side_effect = HttpClientError
        # Since we're not accepting user input, a solitude 400 should
        # raise an exception.
        self.get()


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
