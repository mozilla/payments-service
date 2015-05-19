import logging

from django.contrib.auth.models import AnonymousUser

from rest_framework import authentication

log = logging.getLogger(__name__)


class SolitudeBuyer(AnonymousUser):
    """
    Fake Django user to represent a Solitude buyer.

    You can access `user.pk` to get the Solitude UUID.
    """
    id = None
    pk = None
    is_active = True

    def __init__(self, buyer_uuid):
        self.id = self.pk = buyer_uuid

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True


class SessionUserAuthentication(authentication.BaseAuthentication):
    """
    Ensures that a user has been session-authenticated before running the
    protected view.

    This also adds a `request.user` object.
    """

    def authenticate(self, request):
        if not request.session.get('buyer_uuid'):
            log.debug('auth failed: buyer_uuid not in session')
            user = None
        else:
            log.debug('auth success: buyer_uuid in session')
            user = SolitudeBuyer(request.session['buyer_uuid'])

        return (user, None)
