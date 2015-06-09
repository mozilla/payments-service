import logging

from django.core.exceptions import ObjectDoesNotExist
from django.middleware import csrf

from rest_framework.response import Response
from slumber.exceptions import HttpClientError

from .. import solitude
from ..base.views import error_400, UnprotectedAPIView
from .forms import SignInForm

log = logging.getLogger(__name__)


class SignInView(UnprotectedAPIView):

    def post(self, request):
        form = SignInForm(request.DATA)

        if not form.is_valid():
            return error_400(response=form.errors)

        fxa_uuid = u'fxa:{a[user]}'.format(a=form.cleaned_data['access_token'])

        api = solitude.api()
        status = 200
        try:
            try:
                buyer = api.generic.buyer.get_object(uuid=fxa_uuid)
                log.info(
                    u'found solitude buyer {buyer} for FxA user {fxa_uuid}'
                    .format(buyer=buyer['uuid'], fxa_uuid=fxa_uuid))
            except ObjectDoesNotExist:
                buyer = api.generic.buyer.post({'uuid': fxa_uuid})
                log.info(
                    u'created solitude buyer {buyer} for FxA user {fxa_uuid}'
                    .format(buyer=buyer['uuid'], fxa_uuid=fxa_uuid))
                status = 201
        except HttpClientError, exc:
            log.warn(
                u'error creating solitude buyer; {exc.__class__}: {exc}; '
                u'FxA user={fxa_uuid}'.format(exc=exc, fxa_uuid=fxa_uuid))
            return error_400(exception=exc)

        request.session['buyer_pk'] = buyer['resource_pk']
        request.session['buyer_uuid'] = buyer['uuid']

        # As a convenience, put any saved payment methods in the response
        # if the user has them.
        pay_methods = api.braintree.mozilla.paymethod.get(
            active=True, braintree_buyer__buyer__uuid=buyer['uuid'])

        # Generate a new token for added security.
        csrf.rotate_token(request)

        return Response({
            'buyer_uuid': buyer['uuid'],
            'buyer_pk': buyer['resource_pk'],
            'payment_methods': pay_methods,
            'csrf_token': csrf.get_token(request),
        }, status=status)
