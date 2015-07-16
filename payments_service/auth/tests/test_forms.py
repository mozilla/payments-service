from nose.tools import eq_
from requests.exceptions import HTTPError

from ..forms import SignInForm
from . import AuthTest


class TestSignInForm(AuthTest):

    def submit(self, data=None):
        if data is None:
            data = {'access_token': self.access_token}
        return SignInForm(data)

    def test_missing_token_or_code(self):
        form = self.submit(data={})
        assert '__all__' in form.errors, form.errors.as_text()

    def test_bad_fxa_response(self):
        self.set_fxa_post_side_effect(HTTPError('Bad Request'))

        form = self.submit()
        assert 'access_token' in form.errors, form.errors.as_text()
        assert self.fxa_post.called

    def test_missing_scope(self):
        self.set_fxa_verify_response(scope=[])
        form = self.submit()
        assert 'access_token' in form.errors, form.errors.as_text()
        assert self.fxa_post.called

    def test_missing_email_scope(self):
        self.set_fxa_verify_response(scope=['payments'])
        form = self.submit()
        assert 'access_token' in form.errors, form.errors.as_text()
        assert self.fxa_post.called

    def test_honor_full_profile_access(self):
        self.set_fxa_verify_response(scope=['payments', 'profile'])
        assert self.submit().is_valid()

    def test_form_ok(self):
        self.set_fxa_verify_response()
        form = self.submit()
        assert form.is_valid(), form.errors.as_text()

        eq_(form.fxa_user_id, self.fxa_user_id)
        eq_(form.fxa_email, self.fxa_email)

        assert self.fxa_post.called


class TestSignInFormWithCode(AuthTest):

    def setUp(self):
        super(TestSignInFormWithCode, self).setUp()
        self.code = 'fxa-auth-code'

    def submit(self, data=None):
        if data is None:
            data = {'authorization_code': self.code}
        return SignInForm(data)

    def test_form_ok(self):
        self.set_fxa_token_response()
        self.set_fxa_verify_response()

        form = self.submit()
        assert form.is_valid(), form.errors.as_text()

        eq_(form.fxa_user_id, self.fxa_user_id)
        eq_(form.fxa_email, self.fxa_email)

        assert self.fxa_post.called

    def test_bad_token_response(self):
        self.set_fxa_post_side_effect(HTTPError('Bad Request'))

        form = self.submit()
        assert 'authorization_code' in form.errors, form.errors.as_text()
        assert self.fxa_post.called

    def test_token_is_verified(self):
        self.set_fxa_token_response()
        # Set up a scope with a missing email just as a smoke test to make
        # sure the token is validated.
        self.set_fxa_verify_response(scope=['payments'])
        form = self.submit()

        assert 'authorization_code' in form.errors, form.errors.as_text()
        assert self.fxa_post.called
