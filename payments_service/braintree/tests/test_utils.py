from django.core.exceptions import ObjectDoesNotExist

import mock
from nose.tools import eq_

from payments_service.base.tests import TestCase
from payments_service.braintree.utils import user_owns_resource


class TestUserOwnsResource(TestCase):

    def setUp(self):
        super(TestUserOwnsResource, self).setUp()
        resource = mock.Mock()
        self.solitude.by_url.return_value = resource
        self.getter = resource.get_object_or_404
        self.getter.return_value = {}

    def test_true_for_successful_lookup(self):
        uri = '/some/object/'
        lookup = {'user_uuid': 'user-uuid'}
        result = user_owns_resource(uri, lookup)
        eq_(result, True)
        self.solitude.by_url.assert_called_with(uri)
        self.getter.assert_called_with(**lookup)

    def test_false_for_failed_lookup(self):
        self.getter.side_effect = ObjectDoesNotExist
        result = user_owns_resource(
            '/some/object/', {'user_uuid': 'user-uuid'}
        )
        eq_(result, False)
