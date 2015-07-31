import json

from django.core.urlresolvers import reverse
from django.test import RequestFactory

import mock
from nose.tools import eq_
from slumber.exceptions import HttpClientError

from payments_service.base.tests import AuthenticatedTestCase
from payments_service.braintree.views.paymethod import (
    get_active_user_pay_methods, PayMethod
)


class PayMethodTest(AuthenticatedTestCase):

    def setUp(self):
        super(PayMethodTest, self).setUp()

        # pretend this is a paymethod object
        self.pay_method = {
            'resource_pk': 1,
            'resource_uri': reverse('braintree:mozilla.paymethod',
                                    args=['1']),
        }
        self.solitude.braintree.mozilla.paymethod.get.return_value = [
            self.pay_method,
        ]

        p = mock.patch(
            'payments_service.braintree.views.paymethod.'
            'get_active_user_pay_methods'
        )
        self.get_active_user_pay_methods = p.start()
        self.get_active_user_pay_methods.return_value = [self.pay_method]
        self.addCleanup(p.stop)


class TestPayMethod(PayMethodTest):

    def setUp(self):
        super(TestPayMethod, self).setUp()
        self.url = reverse('braintree:mozilla.paymethod')

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


class TestBraintreePayMethod(PayMethodTest):

    def setUp(self):
        super(TestBraintreePayMethod, self).setUp()
        self.url = reverse('braintree:paymethod')

        self.solitude.braintree.paymethod.post.return_value = {
            'mozilla': self.pay_method,
            'braintree': {'token': 'new-pay-method-token'},
        }

    def post(self, data=None):
        if not data:
            data = {'nonce': 'braintree-client-nonce'}
        return self.json(self.client.post(self.url, data))

    def test_successful_post(self):
        response, data = self.post()
        eq_(response.status_code, 201)

    def test_post_creates_pay_method_for_user(self):
        self.post()
        api_post = self.solitude.braintree.paymethod.post
        eq_(api_post.call_args[0][0]['buyer_uuid'], self.buyer_uuid)

    def test_post_returns_active_user_pay_methods(self):
        response, data = self.post()
        eq_(data['payment_methods'],
            self.get_active_user_pay_methods.return_value)
        assert self.get_active_user_pay_methods.called

    def test_proxy_bad_solitude_request(self):
        self.solitude.braintree.paymethod.post.side_effect = HttpClientError()
        response, data = self.post()
        eq_(response.status_code, 400)


class TestDeletePayMethod(PayMethodTest):

    def setUp(self):
        super(TestDeletePayMethod, self).setUp()
        self.url = reverse('braintree:paymethod.delete')

        self.solitude.braintree.paymethod.delete.post.return_value = {
            'mozilla': self.pay_method,
            'braintree': {'token': 'new-pay-method-token'},
        }

        p = mock.patch('payments_service.braintree.utils.user_owns_resource')
        self.user_owns_resource = p.start()
        self.user_owns_resource.return_value = True
        self.addCleanup(p.stop)

    def post(self):
        return self.json(
            self.client.post(
                self.url, {'pay_method_uri': self.pay_method['resource_uri']})
        )

    def test_post_is_successful(self):
        res, data = self.post()
        eq_(res.status_code, 200, res)

    def test_deny_deleting_other_users_pay_methods(self):
        self.user_owns_resource.return_value = False
        res, data = self.post()
        self.user_owns_resource.assert_called_with(
            self.pay_method['resource_uri'],
            {'braintree_buyer__buyer__uuid': self.buyer_uuid}
        )
        eq_(res.status_code, 400, res)

    def test_paymethod_is_deleted_from_solitude(self):
        self.post()
        self.solitude.braintree.paymethod.delete.post.assert_called_with({
            'paymethod': self.pay_method['resource_uri']
        })

    def test_post_returns_active_user_pay_methods(self):
        response, data = self.post()
        eq_(data['payment_methods'],
            self.get_active_user_pay_methods.return_value)
        assert self.get_active_user_pay_methods.called


class TestGetActiveUserPayMethods(AuthenticatedTestCase):

    def setUp(self):
        super(TestGetActiveUserPayMethods, self).setUp()
        self.pay_methods = [
            {'resource_pk': 1},
            {'resource_pk': 2},
        ]
        getter = self.solitude.braintree.mozilla.paymethod.get
        getter.return_value = self.pay_methods
        self.user = mock.Mock(uuid=self.buyer_uuid)

    def test_returns_only_pay_methods_for_user(self):
        get_active_user_pay_methods(self.user)
        api_get = self.solitude.braintree.mozilla.paymethod.get
        eq_(api_get.call_args[1]['braintree_buyer__buyer__uuid'],
            self.buyer_uuid)

    def test_returns_only_active_pay_methods(self):
        get_active_user_pay_methods(self.user)
        api_get = self.solitude.braintree.mozilla.paymethod.get
        eq_(api_get.call_args[1]['active'], True)

    def test_return_list_of_pay_methods(self):
        pay_methods = get_active_user_pay_methods(self.user)
        eq_(pay_methods, self.pay_methods)
