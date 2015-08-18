from django.middleware import csrf

from rest_framework.response import Response

from payments_service import solitude
from payments_service.base.views import UnprotectedAPIView


class TokenGenerator(UnprotectedAPIView):
    """
    Generate a client token to begin processing payments.
    """

    def post(self, request):
        bt_data = solitude.api().braintree.token.generate.post({})

        # Generate a new token for added security.
        csrf.rotate_token(request)

        # This view returns a CSRF token to the client so that it can
        # initialize API usage for anonymous payments (e.g. donations).
        # For added security, we could restrict the scope of that CSRF
        # tokens only to views relating to products that support
        # anonymous payments.

        return Response({
            'token': bt_data['token'],
            'csrf_token': csrf.get_token(request),
        })
