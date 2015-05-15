import logging

from rest_framework.response import Response

from .. import solitude
from ..base.views import UnprotectedAPIView

log = logging.getLogger(__name__)


class Index(UnprotectedAPIView):

    def get(self, request):
        error = False
        try:
            api = solitude.api()
            api.services.status.get()
        except Exception, exc:
            log.exception('checking solitude status')
            error = exc

        # Add in JSON error response if we have it.
        error_response = None
        if getattr(error, 'content', None):
            error_response = error.content

        status = 203
        if error:
            status = 500
        return Response({'ok': not error,
                         'solitude': {'connected': not error,
                                      'error': str(error),
                                      'error_response': error_response}},
                        status=status)
