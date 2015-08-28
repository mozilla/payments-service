import logging

from django.http import HttpResponseNotAllowed, JsonResponse

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

log = logging.getLogger(__name__)


def composed_view(handlers):
    """
    Returns a Django view (for use in URL patterns) that delegates
    processing to other view callables based on request method.

    Example:

        composed_view({'get': list_view, 'post': create_view})

    You can already do this by implementing ``get``, ``post``, etc.
    methods on a class based view but this is helpful for DRF view classes
    since ther authentication scope is at the class level, not the method
    level.
    """

    def delegate_request(request, *args, **kwargs):
        handle_request = handlers.get(request.method.lower())
        if not handle_request:
            permitted_methods = handlers.keys()
            return HttpResponseNotAllowed(permitted_methods)

        return handle_request(request, *args, **kwargs)

    return delegate_request


class UnprotectedAPIView(APIView):
    """
    APIView that does not require the user to be signed in *and*
    does not require CSRF verification.
    """
    authentication_classes = []
    permission_classes = [AllowAny]


def error_400(request=None, **kw):
    return error_response(message='Bad Request', status=400, **kw)


def error_403(request=None, **kw):
    return error_response(message='Forbidden', status=403, **kw)


def error_404(request=None, **kw):
    return error_response(message='Not Found', status=404, **kw)


def error_405(request=None, **kw):
    return error_response(message='Method Not Allowed', status=405, **kw)


def error_500(request=None, **kw):
    return error_response(message='Internal Error', status=500, **kw)


def error_response(message='Unknown error', status=500, response=None,
                   exception=None):
    if not response and getattr(exception, 'content', None):
        # This is a DRF exception response which is probably formatted
        # the way we want it.
        response = exception.content
    if response and isinstance(response, basestring):
        # This is some kind of generic message so make it look like a
        # Django form error.
        response = {'__all__': [response]}
    return JsonResponse({'error_message': message,
                         'error_response': response or {}}, status=status)
