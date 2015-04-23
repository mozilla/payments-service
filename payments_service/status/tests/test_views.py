import json

from django.core.urlresolvers import reverse

from nose.tools import eq_
from slumber.exceptions import HttpServerError

from payments_service.base.tests import SolitudeTest


class TestStatus(SolitudeTest):

    def data(self):
        res = self.client.get(reverse('status.index'))
        return json.loads(res.content)

    def test_solitude_connected(self):
        self.solitude.services.status.get.return_value = {
            'cache': True, 'proxies': True,
            'db': True, 'settings': True,
        }
        data = self.data()
        eq_(data['ok'], True)
        eq_(data['solitude']['connected'], True)

    def test_solitude_500(self):
        exc = HttpServerError('500')
        self.solitude.services.status.get.side_effect = exc
        data = self.data()
        eq_(data['ok'], False)
        eq_(data['solitude']['connected'], False)
        eq_(data['solitude']['error'], str(exc))
