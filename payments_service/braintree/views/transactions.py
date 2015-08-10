from rest_framework.response import Response

from payments_service.solitude import SolitudeAPIView


class Transactions(SolitudeAPIView):
    """
    Deals with Braintree related transactions.
    """
    def get(self, request):
        transactions = self.api.braintree.mozilla.transaction.get(
            transaction__buyer__uuid=self.request.user.uuid,
        )
        return Response({
            'transactions': self.expand_api_objects(
                transactions,
                [{'transaction': ['seller_product']}],
            ),
        }, status=200)
