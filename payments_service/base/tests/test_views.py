from django.test import RequestFactory

from mock import Mock
from nose.tools import eq_
from slumber.exceptions import HttpServerError

from . import TestCase
from ..views import composed_view, error_404, error_500


class TestErrorHandlers(TestCase):

    def setUp(self):
        self.request = RequestFactory().get('/')

    def test_404(self):
        res, data = self.json(error_404(self.request))
        eq_(res.status_code, 404, res)
        eq_(data['error_message'], 'Not Found')
        eq_(data['error_response'], {})

    def test_500_without_exception(self):
        res, data = self.json(error_500(self.request))
        eq_(res.status_code, 500, res)
        eq_(data['error_message'], 'Internal Error')
        eq_(data['error_response'], {})

    def test_500_with_exception(self):
        exc = HttpServerError()
        exc.content = {'detail': 'some info'}
        res, data = self.json(error_500(self.request, exception=exc))
        eq_(res.status_code, 500, res)
        eq_(data['error_response'], exc.content)

    def test_500_with_custom_response(self):
        exc = HttpServerError()
        exc.content = {'detail': 'some info'}
        response = 'custom response'

        res, data = self.json(error_500(self.request, exception=exc,
                                        response=response))
        eq_(data['error_response'], {'__all__': [response]})

    def test_500_with_custom_object_response(self):
        response = {'thing': 'custom response'}
        res, data = self.json(error_500(self.request, response=response))
        eq_(data['error_response'], response)


class TestComposedView(TestCase):

    def test_handling_a_get(self):
        get = Mock()
        view = composed_view({'get': get})
        request = RequestFactory().get('/')
        view(request)
        assert get.called

    def test_handling_a_post(self):
        post = Mock()
        view = composed_view({'post': post})
        request = RequestFactory().post('/')
        view(request)
        assert post.called

    def test_pass_args_to_view(self):
        post = Mock()
        view = composed_view({'post': post})
        request = RequestFactory().post('/')
        view(request, 'some-primary-key', keyword='word')
        eq_(post.call_args[0][1], 'some-primary-key')
        eq_(post.call_args[1]['keyword'], 'word')

    def test_method_not_allowed(self):
        post = Mock()
        view = composed_view({'post': post})
        request = RequestFactory().get('/')
        response = view(request)
        eq_(response.status_code, 405)
