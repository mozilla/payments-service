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
        return Response('some response')


class TestDefaultViewProtection(TestCase, WithDynamicEndpoints):

    def get(self):
        self.endpoint(DefaultView)
        return self.json(self.client.get('/dynamic-endpoint'))

    def test_view_access_denied(self):
        res, data = self.get()
        eq_(res.status_code, 403, res)
        eq_(data['detail'],
            'You do not have permission to perform this action.')

    def test_view_access_granted(self):
        self.prepare_session(buyer_uuid='some-uuid', buyer_pk=1)
        res, data = self.get()
        eq_(res.status_code, 200, res)
