import logging

from django.conf import settings
from django.http import HttpResponse

log = logging.getLogger(__name__)


class CORSMiddleware(object):
    """
    Middleware the enables wide open CORS access to every API
    call based on settings.
    """

    def process_request(self, request):
        if request.method.upper() != 'OPTIONS':
            return None
        if not settings.ENABLE_CORS_FOR_ORIGIN:
            return None

        log.info('CORS middleware: responding to OPTIONS')
        response = HttpResponse(status='204')
        return self.corsify_response(response)

    def corsify_response(self, response):
        headers = {
            'Access-Control-Allow-Origin': settings.ENABLE_CORS_FOR_ORIGIN,
            # Allow credentials so that our cookie session will work.
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Allow-Methods': '*',
            'Access-Control-Allow-Headers': 'x-csrftoken',
        }
        for hdr, val in headers.items():
            response[hdr] = val
        return response

    def process_response(self, request, response):
        if not settings.ENABLE_CORS_FOR_ORIGIN:
            return response

        log.warn('CORS requests are enabled for {}'
                 .format(settings.ENABLE_CORS_FOR_ORIGIN))
        return self.corsify_response(response)
