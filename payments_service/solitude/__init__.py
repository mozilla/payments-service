import logging

from django.conf import settings

from curling.lib import API
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from slumber.exceptions import HttpClientError

from ..base.views import error_400, error_405

log = logging.getLogger(__name__)


def api():
    conn = SolitudeAPI(settings.SOLITUDE_URL)
    conn.activate_oauth(settings.SOLITUDE_KEY,
                        settings.SOLITUDE_SECRET)
    return conn


def url_parser(url):
    """
    Curling URL parser for resources with numeric primary keys.

    It helps convert URLs into Slumber resources like:

    /service/category/thing/1/ -> service.category.thing(1)
    """
    # Split all URL parts ignoring empties (from slashes).
    parts = [p for p in url.split('/') if p != '']

    pk = None
    if parts[-1].isdigit():
        pk = parts.pop()

    return parts, pk


class SolitudeAPI(API):

    def by_url(self, url, **kw):
        kw.setdefault('parser', url_parser)
        return super(SolitudeAPI, self).by_url(url, **kw)


class SolitudeAPIView(APIView):

    def __init__(self, *args, **kw):
        super(SolitudeAPIView, self).__init__(*args, **kw)
        # Get a sys.modules reference so that mocking from tests is easier.
        from payments_service import solitude
        self.api = solitude.api()

    def expand_api_objects(self, objects, to_expand):
        """
        Given a list of API result dictionaries, expand URIs to sub-objects.

        For example, this API result:

            {
                "resource_pk": 1,
                "transaction_uri": "/api/transaction/1234/",
            }

        will be expanded to:

            {
                "resource_pk": 1,
                "transaction_uri": {
                    "resource_pk": 1234,
                    ...
                }
            }

        `to_expand` is a list or dict of result attributes that are
        solitude URIs. Each one will be loaded so that the final value
        contains the sub-object.

        Example of expanding two columns:

            self.expand_api_objects(objects, ['transaction_uri',
                                              'seller_uri'])

        Example of expanding the 'product_uri' column which is nested within
        the transaction_uri response:

            self.expand_api_objects(objects,
                                    [{'transaction_uri': ['product_uri']}])

        """

        def expand(leaf, to_expand):
            log.debug('expanding {} within {}'.format(to_expand, leaf))
            # Make a map of attributes that we need to expand and their
            # corresponding value. If the value is a dict, it will
            # indicate nested expansion.
            attr_map = {}
            for a in to_expand:
                if isinstance(a, dict):
                    for sub_key in a:
                        attr_map[sub_key] = a
                else:
                    attr_map[a] = None

            for attr, uri in leaf.iteritems():
                if attr in attr_map:
                    # TODO: adjust Solitude's output so that we don't have to
                    # make sub requests.
                    log.info('expanding object result by calling URI "{}": {}'
                             .format(attr, uri))
                    sub_objects = self.api.by_url(uri).get_object()
                    leaf[attr] = sub_objects

                    # Check if the mapped attribute has nested expansions.
                    if isinstance(attr_map[attr], dict):
                        # To detect nesting easier, the attribute mapping links
                        # to the actual expansion.
                        # For example, to expand product within transaction,
                        # it would be mapped like:
                        # {"transaction": {"transaction": ["product"]}}
                        # This is different from a single level
                        # attribute (no nesting) which would look like:
                        # {"transaction": None}
                        expand(sub_objects, attr_map[attr][attr])

        if not isinstance(objects, list):
            raise TypeError('expected a list of objects to expand')
        for sub in objects:
            expand(sub, to_expand)

        return objects


class AnonymousSolitudeAPIView(SolitudeAPIView):
    """
    A Solitude API view that can be accessed with or without sign-in.

    The view is still CSRF protected.
    """
    permission_classes = [AllowAny]


class SolitudeBodyguard(SolitudeAPIView):
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
        resource = self.api
        url_paths = self.resource.split('.')
        while len(url_paths):
            resource = getattr(resource, url_paths.pop(0))

        if pk:
            resource = resource(pk)
        return resource
