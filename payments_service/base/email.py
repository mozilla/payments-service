import logging
import re

from django.conf import settings
from django.core.mail.backends import locmem
from django.core.mail.backends import smtp

log = logging.getLogger(__name__)


def allowed(email_messages):
    for email_message in email_messages:
        for recipient in email_message.recipients():
            if not settings.EMAIL_ALLOWED_LIST:
                # No explicit list of emails was given.
                return True

            for regex in settings.EMAIL_ALLOWED_LIST:
                # If the regex matched allow the email to be sent.
                if re.match(regex, recipient):
                    break

            else:
                log.warning(u'Email: {} did not match a regex in the '
                            u'EMAIL_ALLOWED_LIST. Email not sent.'
                            .format(recipient))
                return False

    return True


class FilteredEmailBackend(smtp.EmailBackend):

    def send_messages(self, email_messages):
        if allowed(email_messages):
            return (super(FilteredEmailBackend, self)
                    .send_messages(email_messages))
        return False


# Used for tests.
class FilteredLocEmailBackend(locmem.EmailBackend):

    def send_messages(self, email_messages):
        if allowed(email_messages):
            return (super(FilteredLocEmailBackend, self)
                    .send_messages(email_messages))
        return False
