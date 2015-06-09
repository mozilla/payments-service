from django.http import HttpRequest, HttpResponse
from django.middleware import csrf

from rest_framework.response import Response
from rest_framework.views import APIView
from mock import Mock
from nose.tools import eq_

from payments_service.base.tests import TestCase, WithDynamicEndpoints

from .. import SessionUserAuthentication


class TestSessionUserAuth(TestCase):

    def authenticate(self, **session_kw):
        request = Mock()
        request.session = {}
        request.session.update(session_kw)
        return SessionUserAuthentication().authenticate(request)

    def test_no_auth_without_buyer_uuid(self):
        user, auth = self.authenticate()
        eq_(user, None)

    def test_auth_with_buyer_uuid(self):
        uuid = 'some-uuid'
        pk = 1
        user, auth = self.authenticate(buyer_uuid=uuid, buyer_pk=pk)
        eq_(user.uuid, uuid)
        eq_(user.pk, pk)
        eq_(user.id, pk)


class DefaultView(APIView):
    """
    A view that inherits default DRF permissions.
    """
    def get(self, request):
        return Response('some get response')

    def post(self, request):
        return Response('some post response')


class TestDefaultViewProtection(TestCase, WithDynamicEndpoints):

    def request(self, method, *args, **kw):
        self.endpoint(DefaultView)
        return self.json(
            getattr(self.client, method)('/dynamic-endpoint', *args, **kw)
        )

    def get(self, *args, **kw):
        return self.request('get', *args, **kw)

    def post(self, *args, **kw):
        return self.request('post', *args, **kw)

    def login(self, **extra_session):
        self.prepare_session(buyer_uuid='some-uuid', buyer_pk=1,
                             **extra_session)

    def test_view_access_denied(self):
        res, data = self.get()
        eq_(res.status_code, 403, res)
        eq_(data['detail'],
            'You do not have permission to perform this action.')

    def test_view_access_granted(self):
        self.login()
        res, data = self.get()
        eq_(res.status_code, 200, res)

    def test_view_requires_csrf_token(self):
        self.login()
        self.client.handler.enforce_csrf_checks = True
        res, data = self.post({})
        eq_(res.status_code, 403, res)

    def test_can_access_view_with_csrf_token(self):
        self.login()
        self.client.handler.enforce_csrf_checks = True

        # Simulate CSRF middleware processing within Django.
        fake_request = HttpRequest()
        fake_response = HttpResponse()
        middleware = csrf.CsrfViewMiddleware()
        # Generate a CSRF token.
        middleware.process_view(fake_request, lambda: None, [], {})
        # Simulate exposing a CSRF token on a web form. This has a
        # side effect of preparing the middleware for response processing
        # since CSRF processing is enabled lazily.
        csrf_token = csrf.get_token(fake_request)
        # Set a CSRF cookie.
        middleware.process_response(fake_request, fake_response)
        # Prepare to send the cookie in our test client's request.
        self.client.cookies.update(fake_response.cookies)

        res, data = self.post({}, HTTP_X_CSRFTOKEN=csrf_token)
        eq_(res.status_code, 200, res)
