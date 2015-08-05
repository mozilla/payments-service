from django.http import HttpResponse
from django.test import RequestFactory

from nose.tools import eq_

from payments_service.base.tests import TestCase

from ..middleware import CORSMiddleware


class TestCORSMiddleware(TestCase):

    def test_ignore_options_when_disabled(self):
        req = RequestFactory().options('/')
        with self.settings(ENABLE_CORS_FOR_ORIGIN=None):
            eq_(CORSMiddleware().process_request(req), None)

    def test_ignore_non_options_requests(self):
        req = RequestFactory().get('/')
        with self.settings(ENABLE_CORS_FOR_ORIGIN='http://some.site'):
            eq_(CORSMiddleware().process_request(req), None)

    def test_respond_to_options_request(self):
        req = RequestFactory().options('/')
        origin = 'http://some.site'
        with self.settings(ENABLE_CORS_FOR_ORIGIN=origin):
            res = CORSMiddleware().process_request(req)
            eq_(res['Access-Control-Allow-Origin'], origin)

    def test_add_cors_headers_to_response(self):
        req = RequestFactory().post('/')
        res = HttpResponse()
        origin = 'http://some.site'
        with self.settings(ENABLE_CORS_FOR_ORIGIN=origin):
            new_res = CORSMiddleware().process_response(req, res)
            eq_(new_res['Access-Control-Allow-Origin'], origin)

    def test_ignore_responses_when_disabled(self):
        req = RequestFactory().post('/')
        res = HttpResponse()
        with self.settings(ENABLE_CORS_FOR_ORIGIN=None):
            new_res = CORSMiddleware().process_response(req, res)
            assert 'Access-Control-Allow-Origin' not in new_res
