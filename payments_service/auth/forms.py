import json
import logging
import urlparse

from django import forms
from django.conf import settings

import requests
from requests.exceptions import HTTPError

log = logging.getLogger(__name__)


class SignInForm(forms.Form):
    """
    Sign in via FxA one of two ways.

    access_token
        A third party Oauth2 access token with proper scopes
    authorization_code
        An internally generated code from a sign-in form that
        will be traded for an access token
    """
    access_token = forms.CharField(max_length=255, required=False)
    authorization_code = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, **kw):
        self.fxa_user_id = None
        self.fxa_email = None
        super(SignInForm, self).__init__(*args, **kw)

    def clean(self):
        data = self.cleaned_data
        if not (data.get('access_token') or data.get('authorization_code')):
            raise forms.ValidationError(
                'access_token or authorization_code is required'
            )
        return data

    def clean_authorization_code(self):
        code = self.cleaned_data['authorization_code']
        if not code:
            return

        url = urlparse.urljoin(settings.FXA_OAUTH_URL, 'v1/token')
        log.info(u'getting token for code at {url}; code={code}; '
                 u'client={client}'
                 .format(url=url, code=self.repr_token(code),
                         client=settings.FXA_CLIENT_ID))

        data = self.fxa_post(url, {
            'code': code,
            'grant_type': 'authorization_code',
            'client_id': settings.FXA_CLIENT_ID,
            'client_secret': settings.FXA_CLIENT_SECRET,
        })
        access_token = data['access_token']

        log.info(u'got access token for code: {} {}'
                 .format(self.repr_token(access_token),
                         self.repr_token(code)))

        self.validate_access_token(access_token)

        return code

    def clean_access_token(self):
        access_token = self.cleaned_data['access_token']
        if not access_token:
            return

        self.validate_access_token(access_token)
        return access_token

    def fxa_post(self, url, data, **kw):
        kw.setdefault('headers', {})
        kw['headers']['Content-Type'] = 'application/json'
        kw['headers']['Accept'] = 'application/json'

        try:
            res = requests.post(url, json.dumps(data), **kw)
            res.raise_for_status()
        except HTTPError, exc:
            log.info(u'FxA client exception: '
                     u'{exc.__class__.__name__}: {exc}; '
                     u'url={url}; status={status}; data={data}'
                     .format(exc=exc, url=res.url, status=res.status_code,
                             data=data))
            raise forms.ValidationError('invalid FxA response')

        return res.json()

    def repr_token(self, token):
        return '{}...'.format(token[0:8])

    def validate_access_token(self, access_token):
        url = urlparse.urljoin(settings.FXA_OAUTH_URL, 'v1/verify')
        log.info(u'verifying access token at {url}; token={token}'
                 .format(url=url, token=self.repr_token(access_token)))

        fxa_token = self.fxa_post(url, {'token': access_token})

        if u'payments' not in fxa_token['scope']:
            log.info(u'FxA access token cannot access the "payments" '
                     u'scope; token={token}; scopes={scopes}'
                     .format(token=self.repr_token(access_token),
                             scopes=fxa_token['scope']))
            raise forms.ValidationError(
                'access token is missing the payments scope')

        has_email_access = any((u'profile' in fxa_token['scope'],
                                u'profile:email' in fxa_token['scope']))
        if not has_email_access:
            log.info(u'FxA access token cannot access the "profile:email" '
                     u'scope; token={token}; scopes={scopes}'
                     .format(token=self.repr_token(access_token),
                             scopes=fxa_token['scope']))
            raise forms.ValidationError(
                'access token is missing the profile:email scope')

        self.fxa_user_id = fxa_token['user']
        self.fxa_email = fxa_token['email']

        log.info(u'FxA token is valid; token={token}; user={user}; '
                 u'email={email}'.format(token=self.repr_token(access_token),
                                         user=self.fxa_user_id,
                                         email=self.fxa_email))
