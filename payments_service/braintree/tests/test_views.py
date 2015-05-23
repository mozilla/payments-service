from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse

import mock
from nose.tools import eq_
from slumber.exceptions import HttpClientError

from payments_service.solitude import constants
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

    def setup_transaction(self):
        self.solitude.generic.product.get_object_or_404.return_value = {
            'seller': '/generic/seller/123/',
            'resource_uri': '/generic/product/456/'
        }
        self.solitude.generic.transaction.post.return_value = {
            'resource_pk': '/generic/transaction/789/'
        }
        transaction_mock = mock.Mock(name='transaction.mock')
        self.solitude.generic.transaction.return_value = transaction_mock
        return transaction_mock

    def expect_new_pay_method(self):
        pay_method_uri = '/some/paymethod'
        self.solitude.braintree.paymethod.post.return_value = {
            'mozilla': {
                'resource_uri': pay_method_uri,
            }
        }
        return pay_method_uri

    def test_with_existing_customer(self):
        self.setup_transaction()
        buyer_pk = self.setup_generic_buyer()
        self.expect_new_pay_method()

        res, data = self.post()
        eq_(res.status_code, 204, res)

        self.solitude.braintree.mozilla.buyer.assert_called_with(buyer_pk)
        assert not self.solitude.braintree.customer.post.called

        self.solitude.braintree.paymethod.post.assert_called_with({
            'buyer_uuid': self.buyer_uuid,
            'nonce': self.nonce,
        })

    def test_with_new_customer(self):
        self.setup_transaction()
        self.setup_generic_buyer()
        self.expect_new_pay_method()

        # Set up non-existing braintree customer.
        buyer_resource = mock.Mock()
        self.solitude.braintree.mozilla.buyer.return_value = buyer_resource
        buyer_resource.get_object_or_404.side_effect = ObjectDoesNotExist

        res, data = self.post()
        eq_(res.status_code, 204, res)

        assert self.solitude.braintree.customer.post.called

    def test_with_new_pay_method(self):
        self.setup_transaction()
        self.setup_generic_buyer()
        pay_method_uri = self.expect_new_pay_method()

        res, data = self.post()
        eq_(res.status_code, 204, res)

        self.solitude.braintree.subscription.post.assert_called_with({
            'paymethod': pay_method_uri,
            'plan': self.plan_id,
        })

    def test_with_existing_pay_method(self):
        self.setup_transaction()
        self.setup_generic_buyer()
        pay_method_uri = '/my/saved/paymethod'

        res, data = self.post(data={'pay_method_uri': pay_method_uri,
                                    'plan_id': self.plan_id})
        eq_(res.status_code, 204, res)

        self.solitude.braintree.subscription.post.assert_called_with({
            'paymethod': pay_method_uri,
            'plan': self.plan_id,
        })

    def test_too_many_pay_methods(self):
        self.setup_transaction()
        self.setup_generic_buyer()
        pay_method_uri = '/my/saved/paymethod'

        res, data = self.post(data={
            'pay_method_uri': pay_method_uri,
            'pay_method_nonce': self.nonce,
            'plan_id': self.plan_id,
        })
        self.assert_form_error(res, ['__all__'])

    def test_bad_solitude_request(self):
        self.setup_transaction()
        self.setup_generic_buyer()
        exc = HttpClientError('bad request')
        exc.content = {'nonce': ['This field is required.']}
        self.solitude.braintree.paymethod.post.side_effect = exc

        res, data = self.post()
        self.assert_form_error(res, ['nonce'])

    def test_transaction_errored(self):
        transaction_mock = self.setup_transaction()
        self.setup_generic_buyer()
        exc = HttpClientError('bad request')
        exc.content = {'nonce': ['This field is required.']}
        self.solitude.braintree.paymethod.post.side_effect = exc

        res, data = self.post()
        self.solitude.generic.transaction.post
        transaction_mock.patch.assert_called_with({
            'status': constants.STATUS_ERRORED,
            'status_reason': 'SETUP_ERROR'})

    def test_transaction_created(self):
        transaction_mock = self.setup_transaction()
        self.setup_generic_buyer()
        self.expect_new_pay_method()

        res, data = self.post()
        eq_(res.status_code, 204, res)
        self.solitude.generic.transaction.post.assert_called_with({
            'status': constants.STATUS_STARTED,
            'seller_product': '/generic/product/456/',
            'provider': constants.PROVIDER_BRAINTREE,
            'buyer': '/generic/buyer/1234/',
            'seller': '/generic/seller/123/',
            'type': constants.TYPE_PAYMENT
        })

    def test_transaction_succeeded(self):
        transaction_mock = self.setup_transaction()
        self.setup_generic_buyer()
        self.expect_new_pay_method()

        res, data = self.post()
        eq_(res.status_code, 204, res)
        transaction_mock.patch.assert_called_with({
            'status': constants.STATUS_COMPLETED})

    def test_missing_pay_method(self):
        res, data = self.post({'plan_id': self.plan_id})
        self.assert_form_error(res, ['__all__'])


class TestWebhook(TestCase):

    def test_verify(self):
        self.solitude.braintree.webhook.get.return_value = 'token'
        res = self.client.get(reverse('braintree:webhook'))
        eq_(res['Content-Type'], 'text/plain; charset=utf-8')
        eq_(res.status_code, 200)
        eq_(res.content, 'token')

    def test_parse(self):
        self.solitude.braintree.webhook.post.return_value = ''
        res = self.client.post(reverse('braintree:webhook'))
        eq_(res.status_code, 200)
