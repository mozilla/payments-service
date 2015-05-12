import json
import logging
import urlparse

from django import forms
from django.conf import settings

import requests
from requests.exceptions import HTTPError

log = logging.getLogger(__name__)


class SignInForm(forms.Form):
    # Oauth2 access token.
    access_token = forms.CharField(max_length=255)

    def clean_access_token(self):
        access_token = self.cleaned_data['access_token']

        url = urlparse.urljoin(settings.FXA_OAUTH_URL, 'v1/verify')
        log.info(u'verifying access token at {url}; token={token}'
                 .format(url=url, token=access_token))

        res = requests.post(
            url, data=json.dumps({'token': access_token}),
            headers={'Content-Type': 'application/json',
                     'Accept': 'application/json'})
        try:
            res.raise_for_status()
        except HTTPError, exc:
            log.info(u'FxA access token exception: '
                     u'{exc.__class__.__name__}: {exc}; token={token}; '
                     u'url={url}; status={status}'
                     .format(exc=exc, url=res.url, status=res.status_code,
                             token=access_token))
            log.debug(u'FxA access token response: {res}; token={token}'
                      .format(res=res.content, token=access_token))
            raise forms.ValidationError('invalid FxA response')

        fxa_token = res.json()
        if u'payments' not in fxa_token['scope']:
            log.info(u'FxA access token cannot access the "payments" '
                     u'scope; token={token}; scopes={scopes}'
                     .format(token=access_token, scopes=fxa_token['scope']))
            raise forms.ValidationError('incorrect scope')

        log.info(u'FxA token is valid; token={token}; fxa_token={fxa}'
                 .format(token=access_token, fxa=fxa_token))
        return fxa_token
