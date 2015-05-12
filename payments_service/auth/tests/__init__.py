import mock

from payments_service.base.tests import SolitudeTest


class AuthTest(SolitudeTest):

    def setUp(self):
        super(AuthTest, self).setUp()
        p = mock.patch('payments_service.auth.forms.requests.post')
        self.fxa_post = p.start()
        self.addCleanup(p.stop)
        self.access_token = 'some-oauth-token'
        self.fxa_user_id = '54321abcde'

    def set_fxa_response(self, scope=None):
        if scope is None:
            scope = ['profile', 'payments']
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            'user': self.fxa_user_id,
            'client_id': '12345ab',
            'email': 'some-user@somewhere.com',
            'scope': scope,
        }
        self.fxa_post.return_value = mock_response
