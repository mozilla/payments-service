import logging

from django.contrib.auth.models import AnonymousUser

from rest_framework import authentication

log = logging.getLogger(__name__)


class SolitudeBuyer(AnonymousUser):
    """
    Fake Django user to represent a generic Solitude buyer.

    Properties:

    * `uuid`: the Solitude generic buyer's UUID.
    * `pk`: the Solitude generic buyer's primary key.
    * `uri`: the Solitude generic buyer's URI.
    """
    id = pk = uuid = None
    is_active = True

    def __init__(self, buyer_uuid, buyer_pk):
        self.pk = self.id = buyer_pk
        self.uuid = buyer_uuid
        self.uri = '/generic/buyer/{0}/'.format(self.pk)

    def __str__(self):
        return '<{cls} {uuid}>'.format(cls=self.__class__.__name__,
                                       uuid=self.uuid)

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True


class SessionUserAuthentication(authentication.SessionAuthentication):
    """
    Ensures that a user has been session-authenticated before running the
    protected view.

    This also adds a `request.user` object.
    """

    def authenticate(self, request):
        if not request.session.get('buyer'):
            log.debug('auth failed: buyer not in session')
            user = None
        else:
            log.debug('auth success: buyer in session')
            user = SolitudeBuyer(request.session['buyer']['uuid'],
                                 request.session['buyer']['pk'])

        self.enforce_csrf(request)

        return (user, None)
