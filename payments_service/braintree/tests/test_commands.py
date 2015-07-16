from django.conf import settings
from django.template import TemplateDoesNotExist
from django.test import TestCase

import mock
from nose.tools import eq_

from payments_service.braintree.management.commands import premail


class TestPremail(TestCase):

    def test_transform(self):
        eq_(premail.post_transform('http://pay.dev/email-placeholder'),
            '{{ product.img }}')

    def test_get_template_source(self):
        filename = premail.join('subscription_charged_successfully.html')
        res = premail.get_template_source(filename)
        assert '<head>' in res  # From the header.
        # Something suitably fragile from the main body.
        assert '{{ transaction.uuid }}' in res
        assert '</head>' in res  # From the footer.

    def test_get_no_regenerate(self):
        res = premail.get_email('subscription_charged_successfully.html')
        assert '<head>' in res

    def test_get_stored(self):
        try:
            premail.get_email('foo.html', premailed='stored')
        except TemplateDoesNotExist, err:
            assert 'foo.premailed.html' in err.message

    def test_get_regenerate(self):
        # Premail is slow and make lots of external HTTP request
        # so lets mock that library.
        with mock.patch('payments_service.braintree.management.'
                        'commands.premail.Premailer') as mocked:
            premail.get_email('subscription_charged_successfully.html',
                              premailed='regenerate')

        kw = mocked.call_args[1]
        assert '<html>' in kw['html']
        eq_(kw['method'], 'html')
        eq_(kw['base_url'], settings.EMAIL_URL_ROOT)
