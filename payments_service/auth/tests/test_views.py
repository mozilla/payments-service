from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.test import RequestFactory

import mock
from nose.tools import eq_
from slumber.exceptions import HttpClientError

from payments_service.base.tests import AuthenticatedTestCase
from . import AuthTest
from .. import SessionUserAuthentication


class BaseSignInTest(AuthTest):

    def setUp(self):
        super(BaseSignInTest, self).setUp()
        self.client_id = 'some-fxa-client-id'
        p = mock.patch.object(settings, 'FXA_CREDENTIALS', {
            self.client_id: 'some-fxa-secret',
        })
        p.start()
        self.addCleanup(p.stop)


class SignInTest(BaseSignInTest):

    def setUp(self):
        super(SignInTest, self).setUp()
        self.url = reverse('auth:sign-in')
        self.set_fxa_verify_response()

    def post(self, data=None, headers=None):
        headers = headers or {'HTTP_ACCEPT_LANGUAGE': 'en-US'}
        if data is None:
            data = {'access_token': self.access_token}
        return self.json(
            self.client.post(self.url, data, **headers)
        )

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
        p = mock.patch(
            'payments_service.auth.utils.set_up_braintree_customer'
        )
        self.set_up_braintree_customer = p.start()
        self.addCleanup(p.stop)

    def test_return_buyer_ids(self):
        buyer = self.set_solitude_buyer_getter()

        res, data = self.post()
        eq_(res.status_code, 200, res)
        eq_(data['buyer_uuid'], buyer['uuid'])
        eq_(data['buyer_pk'], buyer['resource_pk'])

    def test_create_buyer_after_authorization(self):
        self.set_fxa_token_response()
        buyer = self.set_solitude_buyer_getter()

        res, data = self.post(data={
            'authorization_code': 'some-fxa-auth-code',
            'client_id': self.client_id,
        })
        eq_(res.status_code, 200, res)
        eq_(data['buyer_uuid'], buyer['uuid'])
        self.set_up_braintree_customer.assert_called_with(buyer)

    def test_return_buyer_email(self):
        self.set_solitude_buyer_getter()

        res, data = self.post()
        eq_(res.status_code, 200, res)
        eq_(data['buyer_email'], self.fxa_email)

    def test_get_existing_solitude_buyer(self):
        self.set_solitude_buyer_getter()

        res, data = self.post()
        eq_(res.status_code, 200, res)

        self.solitude.generic.buyer.get_object.assert_called_with(
            uuid='fxa:{u}'.format(u=self.fxa_user_id))

    def test_patch_existing_buyer_with_data(self):
        self.set_solitude_buyer_getter()
        buyer_patcher = self.set_solitude_buyer_patcher()

        res, data = self.post()
        eq_(res.status_code, 200, res)

        buyer_patcher.assert_called_with({
            'email': self.fxa_email,
            'locale': 'en-US'
        })

    def test_patch_existing_buyer_without_locale(self):
        self.set_solitude_buyer_getter()
        buyer_patcher = self.set_solitude_buyer_patcher()

        res, data = self.post(headers={'HTTP_ACCEPT_LANGUAGE': ''})
        eq_(res.status_code, 200, res)

        buyer_patcher.assert_called_with({'email': self.fxa_email})

    def test_create_solitude_buyer(self):
        self.solitude.generic.buyer.get_object.side_effect = ObjectDoesNotExist
        buyer = {
            'uuid': 'buyer-uuid',
            'resource_pk': 1
        }
        self.solitude.generic.buyer.post.return_value = buyer

        res, data = self.post()
        eq_(res.status_code, 201, res)
        self.solitude.generic.buyer.post.assert_called_with({
            'email': self.fxa_email,
            'locale': 'en-US',
            'uuid': 'fxa:{u}'.format(u=self.fxa_user_id),
        })
        self.set_up_braintree_customer.assert_called_with(buyer)

    def test_save_buyer_data_to_session(self):
        self.set_solitude_buyer_getter()

        res, data = self.post()
        eq_(res.status_code, 200, res)
        buyer = self.client.session.get('buyer')
        eq_(buyer['uuid'], data['buyer_uuid'])
        eq_(buyer['pk'], data['buyer_pk'])

    def test_bad_solitude_response(self):
        err = HttpClientError('Bad Request')
        self.solitude.generic.buyer.get_object.side_effect = err

        res, data = self.post()
        self.assert_error_response(res)

    def test_expose_csrf_token(self):
        self.set_solitude_buyer_getter()
        res, data = self.post()
        assert 'csrf_token' in data, 'Unexpected: {}'.format(data)


class TestSignOut(AuthenticatedTestCase):

    def test_sign_out(self):
        res = self.client.post(reverse('auth:sign-out'))
        eq_(res.status_code, 204, res)

        request = RequestFactory().get('/')
        request.session = self.client.session

        # Make sure the middleware now thinks they are signed out.
        user, auth = SessionUserAuthentication().authenticate(request)
        eq_(user, None)


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
