from django.http import JsonResponse


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
