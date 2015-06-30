from django.core import mail
from django.test.utils import override_settings

from nose.tools import eq_

from payments_service.base.tests import TestCase

filtered = 'payments_service.base.email.FilteredLocEmailBackend'


@override_settings(EMAIL_BACKEND=filtered)
class TestAllowedToEmail(TestCase):

    def send(self, recipients):
        mail.send_mail('subject', 'msg', 'a@m.o', recipients,
                       fail_silently=False)

    @override_settings(EMAIL_ALLOWED_LIST=[])
    def test_no_list(self):
        self.send(['a@m.c'])
        eq_(len(mail.outbox), 1)

    @override_settings(EMAIL_ALLOWED_LIST=['a@m.c'])
    def test_allowed(self):
        self.send(['a@m.c'])
        eq_(len(mail.outbox), 1)

    @override_settings(EMAIL_ALLOWED_LIST=['a@m.c'])
    def test_not_allowed(self):
        self.send(['a@m.o'])
        eq_(len(mail.outbox), 0)

    @override_settings(EMAIL_ALLOWED_LIST=['a@m.c'])
    def test_multiple(self):
        self.send(['a@m.o', 'a@m.c'])
        eq_(len(mail.outbox), 0)
