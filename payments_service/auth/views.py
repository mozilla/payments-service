import logging

from django.core.exceptions import ObjectDoesNotExist
from django.middleware import csrf

from rest_framework.response import Response
from slumber.exceptions import HttpClientError

from . import utils
from .. import solitude
from ..base.views import APIView, error_400, UnprotectedAPIView
from .forms import SignInForm

log = logging.getLogger(__name__)


class SignInView(UnprotectedAPIView):

    def post(self, request):
        form = SignInForm(request.DATA)

        if not form.is_valid():
            return error_400(response=form.errors)

        fxa_uuid = u'fxa:{}'.format(form.fxa_user_id)
        email = form.fxa_email

        api = solitude.api()
        created = False
        locale = request.META.get('HTTP_ACCEPT_LANGUAGE')
        try:
            try:
                buyer = api.generic.buyer.get_object(uuid=fxa_uuid)
                log.info(
                    u'found solitude buyer {buyer} for FxA user {fxa_uuid}'
                    .format(buyer=buyer['uuid'], fxa_uuid=fxa_uuid))
            except ObjectDoesNotExist:
                buyer = api.generic.buyer.post({
                    'email': email,
                    'locale': locale,
                    'uuid': fxa_uuid,
                })
                log.info(
                    u'created solitude buyer {buyer} for FxA user {fxa_uuid}'
                    .format(buyer=buyer['uuid'], fxa_uuid=fxa_uuid))
                created = True

            utils.set_up_braintree_customer(buyer)

        except HttpClientError, exc:
            log.warn(
                u'error setting up solitude buyers; {exc.__class__}: {exc}; '
                u'FxA user={fxa_uuid}'.format(exc=exc, fxa_uuid=fxa_uuid))
            return error_400(exception=exc)

        if not created:
            log.info('updating email to {} for user {}'
                     .format(email, locale, buyer['resource_pk']))
            # Pretty soon we can hopefully stop storing the email address.
            # This patch request exists mainly to ease local development but
            # could theoretically handle changing email addresses.
            data = {'email': email}
            # Similarly we can update the locale until we can find a way to
            # access that from FxA.
            if locale:
                log.info('Updating locale to {} for user {}'
                         .format(locale, buyer['resource_pk']))
                data['locale'] = locale
            api.generic.buyer(buyer['resource_pk']).patch(data)

        request.session['buyer'] = {
            'pk': buyer['resource_pk'],
            'uuid': buyer['uuid'],
        }

        # As a convenience, put any saved payment methods in the response
        # if the user has them.
        pay_methods = api.braintree.mozilla.paymethod.get(
            active=True, braintree_buyer__buyer__uuid=buyer['uuid'])

        # Generate a new token for added security.
        csrf.rotate_token(request)

        return Response({
            'buyer_uuid': buyer['uuid'],
            'buyer_pk': buyer['resource_pk'],
            'buyer_email': email,
            'payment_methods': pay_methods,
            'csrf_token': csrf.get_token(request),
        }, status=201 if created else 200)


class SignOutView(APIView):

    def post(self, request):
        log.info('signing out user: {}'.format(request.user))
        del request.session['buyer']
        return Response({}, status=204)
