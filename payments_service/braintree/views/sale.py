import logging

from rest_framework.response import Response

from payments_service.base.views import error_400
from payments_service.solitude import AnonymousSolitudeAPIView
from slumber.exceptions import HttpClientError

from ..forms import SaleForm

log = logging.getLogger(__name__)


class Sale(AnonymousSolitudeAPIView):
    """
    Work with one-off Braintree purchases (called a sale).
    """
    def post(self, request):
        form = SaleForm(request.user, request.DATA)
        if not form.is_valid():
            return error_400(response=form.errors)
        try:
            self.api.braintree.sale.post({
                'amount': form.cleaned_data['amount'],
                'product_id': form.cleaned_data['product_id'],
                'nonce': form.cleaned_data['nonce'],
                'paymethod': form.cleaned_data['paymethod'],
            })
            log.info('posted a sale for user/product: {}/{}'
                     .format(request.user, form.cleaned_data['product_id']))
        except HttpClientError, exc:
            log.debug('caught bad request from solitude: {}'.format(exc))
            return error_400(exception=exc)

        if request.user and form.cleaned_data['nonce']:
            # Since the user is signed in, save this new payment method
            # for use in future payments.
            pay_method = self.api.braintree.paymethod.post({
                'buyer_uuid': request.user.uuid,
                'nonce': form.cleaned_data['nonce'],
            })
            log.info('saved pay method {} for user {}'
                     .format(pay_method, request.user))

        return Response({}, status=204)
