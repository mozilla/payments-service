import logging

from rest_framework.response import Response
from rest_framework.views import APIView
from slumber.exceptions import HttpClientError

from payments_service import solitude
from payments_service.base.views import error_400, error_403
from payments_service.solitude import SolitudeBodyguard

from ..forms import DeletePayMethodForm

log = logging.getLogger(__name__)


class PayMethod(SolitudeBodyguard):
    """
    Work with saved payment methods for the signed in buyer.
    This connects to the Mozilla data store of payment
    methods.
    """
    methods = ['get', 'patch']
    resource = 'braintree.mozilla.paymethod'

    def replace_call_args(self, request, method, args, kw):
        """
        Replace the GET parameters with custom values.

        This sets the right default parameters that we
        want to send to Solitude, allowing for some overrides.
        The important part is that it only lets you get
        payment methods for the logged in user.
        """
        if method.lower() != 'get':
            return args, kw

        replaced_kw = {
            'braintree_buyer__buyer__uuid': request.user.uuid,
        }
        if request.method.lower() == 'get':
            # When getting payment methods, default to active payment methods.
            # However, when doing a get *within* something like a patch
            # handler, do not restrict to active/inactive.
            replaced_kw['active'] = kw.get('active', True)

        return args, replaced_kw

    def patch(self, request, pk=None):
        """
        Allow patching of payment methods.

        * verify that the user wanting to make a patch is allowed too
        * send through the patch
        """
        # Get the active paymethod filtered by logged in user.
        res = self.get(request, pk=pk)

        if res.status_code != 200:
            # This would be a 404 if the user is trying to patch a
            # paymethod they do not own.
            log.warning(
                '_api_request returned: {} when trying to '
                'access paymethod: {}, user: {}'
                .format(res.status_code, pk, request.user.uuid)
            )
            return error_403('Not allowed')

        return super(PayMethod, self).patch(request, pk=pk)


class BraintreePayMethod(APIView):
    """
    Work with payment methods for the signed in in buyer.
    This connects to the Braintree API directly.
    """
    def post(self, request):
        api = solitude.api()

        data = request.data.copy()
        data['buyer_uuid'] = request.user.uuid
        try:
            result = api.braintree.paymethod.post(data)
        except HttpClientError, exc:
            log.warn('post: solitude returned 400: {}'.format(exc))
            return error_400(exception=exc)

        log.info('created payment method {} for user {}'
                 .format(result['mozilla']['resource_pk'],
                         request.user.uuid))

        payment_methods = get_active_user_pay_methods(request.user)
        return Response({'payment_methods': payment_methods}, status=201)


class DeleteBraintreePayMethod(APIView):

    def post(self, request):
        form = DeletePayMethodForm(request.user, request.data)
        if not form.is_valid():
            return error_400(response=form.errors)

        pay_method = form.cleaned_data.get('pay_method_uri')
        log.info('deleting payment method for user: {} {}'
                 .format(pay_method, request.user))
        solitude.api().braintree.paymethod.delete.post({
            'paymethod': pay_method,
        })

        payment_methods = get_active_user_pay_methods(request.user)
        return Response({'payment_methods': payment_methods}, status=200)


def get_active_user_pay_methods(user):
    api = solitude.api()
    return api.braintree.mozilla.paymethod.get(
        braintree_buyer__buyer__uuid=user.uuid,
        active=True,
    )
