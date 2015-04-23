from django.test import TestCase

import mock


class SolitudeTest(TestCase):

    def setUp(self):
        p = mock.patch('payments_service.solitude.api')
        api = p.start()
        self.addCleanup(p.stop)
        self.solitude = mock.Mock()
        api.return_value = self.solitude
