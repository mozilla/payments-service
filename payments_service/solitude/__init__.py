import logging

from django.conf import settings

from curling.lib import API
from rest_framework.response import Response
from rest_framework.views import APIView
from slumber.exceptions import HttpClientError

from ..base.views import error_400, error_405

log = logging.getLogger(__name__)


def api():
    conn = API(settings.SOLITUDE_URL)
    conn.activate_oauth(settings.SOLITUDE_KEY,
                        settings.SOLITUDE_SECRET)
    return conn


class SolitudeBodyguard(APIView):
    """
    API view that proxies a single call downstream to Solitude
    with some restrictions.

    In other words, it's like Solitude's bodyguard because
    Solitude is firewalled off from direct Internet connections.
    """
    # A list of allowed methods, as lowercase Curling properties.
    # Example: methods=['get', 'post']
    methods = []
    # Path to a resource, as a dot-separated Curling attribute path.
    # Example:
    # GET /services/status/
    # would be:
    # resource = 'services.status'
    resource = None

    def _api_request(self, method, *args, **kw):
        if method.lower() not in self.methods:
            return error_405()

        # Get the endpoint + method, such as api.services.status.get
        api_request = getattr(self._resource(), method)

        log.info('solitude: about to request %(method) on %(api)'
                 .format(method=method, api=api_request))
        try:
            result = api_request(*args, **kw)
        except HttpClientError, exc:
            log.warn('%(api): solitude returned 400: %(details)'
                     .format(api=api_request, details=exc))
            return error_400(exception=exc)
        return Response(result)

    def _resource(self):
        """
        Returns the Curling API resource object, i.e. minus the
        request method.

        For example, when

            resource = 'services.status'

        this returns

            api().services.status
        """
        resource = api()
        url_paths = self.resource.split('.')
        while len(url_paths):
            resource = getattr(resource, url_paths.pop(0))
        return resource

    def get(self, request, **kw):
        return self._api_request('get', **kw)

    def post(self, request, **kw):
        return self._api_request('post', request.data or {}, **kw)
