import urlparse

from django.conf import settings

import mock

from payments_service.base.tests import TestCase


class AuthTest(TestCase):

    def setUp(self):
        super(AuthTest, self).setUp()

        p = mock.patch('payments_service.auth.forms.requests.post')
        self.fxa_post = p.start()
        self.fxa_post_results = {}

        def get_stub_result(url, *args, **kw):
            return self.fxa_post_results[url]

        self.fxa_post.side_effect = get_stub_result
        self.addCleanup(p.stop)

        self.access_token = 'some-oauth-token'
        self.fxa_user_id = '54321abcde'
        self.fxa_email = 'some-user@somewhere.com'

    def set_fxa_url_result(self, url, result):
        full_url = urlparse.urljoin(settings.FXA_OAUTH_URL, url)
        self.fxa_post_results[full_url] = result

    def set_fxa_verify_response(self, scope=None):
        if scope is None:
            scope = ['profile:email', 'payments']
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            'user': self.fxa_user_id,
            'client_id': '12345ab',
            'email': self.fxa_email,
            'scope': scope,
        }
        self.set_fxa_url_result('v1/verify', mock_response)

    def set_fxa_token_response(self, scope=None):
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            'access_token': self.access_token,
        }
        self.set_fxa_url_result('v1/token', mock_response)

    def set_fxa_post_side_effect(self, side_effect):
        mock_response = mock.Mock()
        mock_response.raise_for_status.side_effect = side_effect

        # Reset the post() result side effect.
        self.fxa_post.side_effect = None

        # Install our mock response object.
        self.fxa_post.return_value = mock_response
