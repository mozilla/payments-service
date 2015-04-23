from rest_framework.permissions import AllowAny
from rest_framework.views import APIView


class UnprotectedAPIView(APIView):
    """
    An APIView that is not protected by global authentication.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
