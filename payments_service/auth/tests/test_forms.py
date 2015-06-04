import mock
from requests.exceptions import HTTPError

from ..forms import SignInForm
from . import AuthTest


class TestSignInForm(AuthTest):

    def submit(self, data=None):
        if data is None:
            data = {'access_token': self.access_token}
        return SignInForm(data)

    def test_missing_token(self):
        form = self.submit(data={})
        assert 'access_token' in form.errors.as_data(), form.errors

    def test_bad_fxa_response(self):
        mock_response = mock.Mock()
        mock_response.raise_for_status.side_effect = HTTPError('Bad Request')
        self.fxa_post.return_value = mock_response

        form = self.submit()
        assert 'access_token' in form.errors.as_data(), form.errors
        assert self.fxa_post.called

    def test_missing_scope(self):
        self.set_fxa_response(scope=[])
        form = self.submit()
        assert 'access_token' in form.errors.as_data(), form.errors
        assert self.fxa_post.called

    def test_missing_email_scope(self):
        self.set_fxa_response(scope=['payments'])
        form = self.submit()
        assert 'access_token' in form.errors.as_data(), form.errors
        assert self.fxa_post.called

    def test_honor_full_profile_access(self):
        self.set_fxa_response(scope=['payments', 'profile'])
        assert self.submit().is_valid()

    def test_form_ok(self):
        self.set_fxa_response()
        assert self.submit().is_valid()
