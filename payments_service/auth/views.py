import logging

from django.core.exceptions import ObjectDoesNotExist

from rest_framework.decorators import api_view
from rest_framework.response import Response
from slumber.exceptions import HttpClientError

from .. import solitude
from ..base.views import error_400
from .forms import SignInForm

log = logging.getLogger(__name__)


@api_view(['POST'])
def sign_in(request):
    form = SignInForm(request.DATA)

    if not form.is_valid():
        return error_400(response=form.errors)

    fxa_uuid = u'fxa:{u}'.format(u=form.cleaned_data['access_token']['user'])

    api = solitude.api()
    status = 200
    try:
        try:
            buyer = api.generic.buyer.get_object(uuid=fxa_uuid)
            log.info(u'found solitude buyer {buyer} for FxA user {fxa_uuid}'
                     .format(buyer=buyer['uuid'], fxa_uuid=fxa_uuid))
        except ObjectDoesNotExist:
            buyer = api.generic.buyer.post({'uuid': fxa_uuid})
            log.info(u'created solitude buyer {buyer} for FxA user {fxa_uuid}'
                     .format(buyer=buyer['uuid'], fxa_uuid=fxa_uuid))
            status = 201
    except HttpClientError, exc:
        log.warn(u'error creating solitude buyer; {exc.__class__}: {exc}; '
                 u'FxA user={fxa_uuid}'.format(exc=exc, fxa_uuid=fxa_uuid))
        return error_400(exception=exc)

    return Response({'buyer_uuid': buyer['uuid']}, status=status)
