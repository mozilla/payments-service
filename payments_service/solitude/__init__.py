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

    def replace_call_args(self, django_request, method, args, kw):
        """
        Optional hook to replace the arguments before executing the
        slumber callable.

        Arguments:

        *django_request*
            Original Django request object.

        *method*
            Effective request method. This might be different
            than django_request.method in the case where one method
            handler makes sub-requests.

        *args*
            Original slumber API call arguments.
            Example: some.api.endpoint.get(id) or some.api.endpoint.post(data)

        *kw*
            Original slumber API call keyword arguments.
            Example: some.api.endpoint.get(query_param='value')

        Return value: a tuple of (args, kw) that should be
        passed to the API callable.

        By default this just returns the original arguments.
        """
        return args, kw

    def get(self, request, pk=None):
        return self._api_request(request, 'get', resource_pk=pk,
                                 **request.REQUEST)

    def patch(self, request, pk=None):
        if pk is None:
            log.info('{}: PATCH requires a primary key'.format(request.path))
            return error_400()
        return self._api_request(request, 'patch', request.data or {},
                                 resource_pk=pk)

    def post(self, request, pk=None):
        return self._api_request(request, 'post', request.data or {})

    def _api_request(self, django_request, method, *args, **kw):
        resource_pk = kw.pop('resource_pk', None)
        if method.lower() not in self.methods:
            log.debug('{}: ignoring method: {}'.format(self.__class__.__name__,
                                                       method.upper()))
            return error_405()

        # Get the endpoint + method, such as api.services.status.get
        api_request = getattr(self._resource(pk=resource_pk), method)

        # Allow this view to replace call args if it wants to.
        args, kw = self.replace_call_args(django_request, method.lower(),
                                          args, kw)

        log.info('solitude: about to request '
                 '{resource}{instance}.{method}{args}{kw}'
                 .format(method=method, resource=self.resource,
                         args=args, kw=kw,
                         instance='({})'.format(resource_pk)
                                  if resource_pk else ''))
        try:
            result = api_request(*args, **kw)
        except HttpClientError, exc:
            log.warn('{api}: solitude returned 400: {details}'
                     .format(api=api_request, details=exc))
            return error_400(exception=exc)

        return Response(result)

    def _resource(self, pk=None):
        """
        Returns the Curling API resource object, i.e. minus the
        request method.

        For example, when

            resource = 'services.status'

        this returns

            api().services.status

        For object instances, you can also pass in a pk (primary key)
        which results in something like:

            api().services.object(pk)

        """
        resource = api()
        url_paths = self.resource.split('.')
        while len(url_paths):
            resource = getattr(resource, url_paths.pop(0))

        if pk:
            resource = resource(pk)
        return resource
