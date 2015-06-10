from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse

import mock
from nose.tools import eq_
from slumber.exceptions import HttpClientError

from . import AuthTest


class SignInTest(AuthTest):

    def setUp(self):
        super(SignInTest, self).setUp()
        self.url = reverse('auth:sign-in')
        self.set_fxa_response()

    def post(self, data=None):
        if data is None:
            data = {'access_token': self.access_token}
        return self.json(self.client.post(self.url, data))

    def set_no_payment_methods_yet(self):
        self.solitude.braintree.mozilla.paymethod.get.return_value = []

    def set_solitude_buyer_getter(self):
        buyer = {
            'uuid': 'buyer-uuid',
            'resource_pk': 1
        }
        self.solitude.generic.buyer.get_object.return_value = buyer
        return buyer

    def set_solitude_buyer_patcher(self):
        # Set up support for solitude.generic.buyer(user_id).patch(...)
        buyer = mock.Mock()
        self.solitude.generic.buyer.return_value = buyer
        return buyer.patch


class TestSignInView(SignInTest):

    def setUp(self):
        super(TestSignInView, self).setUp()
        self.set_no_payment_methods_yet()

    def test_form_error(self):
        res, data = self.post(data={})
        self.assert_form_error(res, fields=['access_token'])

    def test_existing_solitude_buyer(self):
        buyer = self.set_solitude_buyer_getter()
        buyer_patcher = self.set_solitude_buyer_patcher()

        res, data = self.post()
        eq_(res.status_code, 200, res)
        eq_(data['buyer_uuid'], buyer['uuid'])
        eq_(data['buyer_pk'], buyer['resource_pk'])

        self.solitude.generic.buyer.get_object.assert_called_with(
            uuid='fxa:{u}'.format(u=self.fxa_user_id))
        buyer_patcher.assert_called_with({
            'email': self.fxa_email,
        })

    def test_create_solitude_buyer(self):
        self.solitude.generic.buyer.get_object.side_effect = ObjectDoesNotExist
        self.solitude.generic.buyer.post.return_value = {
            'uuid': 'buyer-uuid',
            'resource_pk': 1
        }

        res, data = self.post()
        eq_(res.status_code, 201, res)
        eq_(data['buyer_uuid'], 'buyer-uuid')
        eq_(data['buyer_pk'], 1)
        self.solitude.generic.buyer.post.assert_called_with({
            'uuid': 'fxa:{u}'.format(u=self.fxa_user_id),
            'email': self.fxa_email,
        })
        eq_(self.client.session.get('buyer_uuid'), data['buyer_uuid'])
        eq_(self.client.session.get('buyer_pk'), data['buyer_pk'])

    def test_bad_solitude_response(self):
        err = HttpClientError('Bad Request')
        self.solitude.generic.buyer.get_object.side_effect = err

        res, data = self.post()
        self.assert_form_error(res)

    def test_expose_csrf_token(self):
        self.set_solitude_buyer_getter()
        res, data = self.post()
        assert 'csrf_token' in data, 'Unexpected: {}'.format(data)


class TestPayMethodsOnSignIn(SignInTest):

    def setUp(self):
        super(TestPayMethodsOnSignIn, self).setUp()
        self.set_solitude_buyer_getter()

    def test_no_saved_payment_methods(self):
        self.set_no_payment_methods_yet()
        res, data = self.post()
        eq_(res.status_code, 200, res)
        eq_(data['payment_methods'], [])

    def test_with_saved_payment_methods(self):
        methods = [{'provider_id': 'bkhm42'}]  # etc.
        self.solitude.braintree.mozilla.paymethod.get.return_value = methods
        res, data = self.post()
        eq_(res.status_code, 200, res)
        eq_(data['payment_methods'], methods)
