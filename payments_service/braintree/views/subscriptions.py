import logging

from rest_framework.response import Response

from payments_service.solitude import AnonymousSolitudeAPIView, SolitudeAPIView
from payments_service.base.views import error_400
from slumber.exceptions import HttpClientError

from ..forms import (ChangeSubscriptionPayMethodForm, ManageSubscriptionForm,
                     SubscriptionForm)

log = logging.getLogger(__name__)


class RetrieveSubscriptions(SolitudeAPIView):
    """
    Deals with retrieving Braintree plan subscriptions.
    """

    def get(self, request):
        subscriptions = self.api.braintree.mozilla.subscription.get(
            active=True,
            paymethod__braintree_buyer__buyer=self.request.user.pk,
        )

        return Response({
            'subscriptions': self.expand_api_objects(subscriptions,
                                                     ['seller_product']),
        }, status=200)


class CreateSubscriptions(AnonymousSolitudeAPIView):
    """
    Deals with creating Braintree plan subscriptions.
    """

    def post(self, request):
        # TODO: make this not require sign-in.
        form = SubscriptionForm(request.user, request.DATA)
        if not form.is_valid():
            return error_400(response=form.errors)

        # TODO: remove this after
        # https://github.com/mozilla/solitude/issues/466
        product = self.api.generic.product.get_object_or_404(
            public_id=form.cleaned_data['plan_id'],
        )
        # Check if the user is already subscribed to this plan.
        result = self.api.braintree.mozilla.subscription.get(
            paymethod__braintree_buyer__buyer=form.user.pk,
            seller_product=product['resource_pk'],
        )
        if len(result):
            log.info(
                'buyer {buyer} is already subscribed to product {product}'
                .format(buyer=form.user.pk,
                        product=product['resource_pk']))
            return error_400(
                response='user is already subscribed to this product')

        try:
            pay_method_uri = self.get_pay_method(
                form.user,
                form.cleaned_data['pay_method_uri'],
                form.cleaned_data['pay_method_nonce']
            )
            self.api.braintree.subscription.post({
                'paymethod': pay_method_uri,
                'plan': form.cleaned_data['plan_id'],
                'amount': form.cleaned_data['amount'],
            })
        except HttpClientError, exc:
            log.debug('caught bad request from solitude: {e}'.format(e=exc))
            return error_400(exception=exc)

        return Response({}, status=204)

    def get_pay_method(self, buyer, pay_method_uri, pay_method_nonce):
        if not pay_method_uri:
            log.info('creating new payment method for buyer {b}'
                     .format(b=buyer.uuid))
            pay_method = self.api.braintree.paymethod.post({
                'buyer_uuid': buyer.uuid,
                'nonce': pay_method_nonce,
            })
            pay_method_uri = pay_method['mozilla']['resource_uri']
        else:
            log.info('paying with saved payment method {m} for buyer {b}'
                     .format(b=buyer.uuid, m=pay_method_uri))

        return pay_method_uri


class ChangeSubscriptionPayMethod(SolitudeAPIView):

    def post(self, request):
        form = ChangeSubscriptionPayMethodForm(request.user, request.DATA)
        if not form.is_valid():
            return error_400(response=form.errors)

        self.api.braintree.subscription.paymethod.change.post({
            'paymethod': form.cleaned_data['new_pay_method_uri'],
            'subscription': form.cleaned_data['subscription_uri'],
        })
        log.info('changed paymethod to {} for subscription {} belonging to '
                 'user {}'.format(form.cleaned_data['new_pay_method_uri'],
                                  form.cleaned_data['subscription_uri'],
                                  request.user))
        return Response({}, status=204)


class CancelSubscription(SolitudeAPIView):

    def post(self, request):
        form = ManageSubscriptionForm(request.user, request.DATA)
        if not form.is_valid():
            return error_400(response=form.errors)

        self.api.braintree.subscription.cancel.post({
            'subscription': form.cleaned_data['subscription_uri'],
        })
        log.info('user {} cancelled subscription {}'.format(
            request.user,
            form.cleaned_data['subscription_uri'],
        ))
        return Response({}, status=204)
