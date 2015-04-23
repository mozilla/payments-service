import logging

from rest_framework.response import Response

from .. import solitude
from ..base import UnprotectedAPIView

log = logging.getLogger(__name__)


class IndexView(UnprotectedAPIView):

    def get(self, request):
        error = False
        try:
            api = solitude.api()
            status = api.services.status.get()
        except Exception, exc:
            log.exception('checking solitude status')
            error = exc

        return Response({'ok': not error,
                         'solitude': {'connected': not error,
                                      'error': str(error)}})
