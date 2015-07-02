============
Contributing
============

If you'd like to contribute a feature to the service, here's how to get set up.

Local Installation
==================

Installation is done through `docker compose`_ from `payments-env`_
but this process is currently in flux. This section will be updated
when the dust settles.

Sending email
=============

To send email set the ``SERVICE_EMAIL_*`` settings that match the `Django settings`_ in your environment. For example::

    export SERVICE_EMAIL_HOST=your.server.com

To avoid sending email to everyone, use a filtered email backend::

    export SERVICE_EMAIL_BACKEND=payments_service.base.email.FilteredEmailBackend

This will read the ``EMAIL_ALLOWED_LIST`` setting and only send email to emails in that list. By default that is::

    EMAIL_ALLOWED_LIST = ['.*@mozilla\.com$']

Running Tests
=============

.. code-block:: shell

    python manage.py test

Bugs and Patches
================

You can submit bug reports and patches at
https://github.com/mozilla/payments-service/


.. _`Django settings`: https://docs.djangoproject.com/en/1.8/ref/settings/#email-host
.. _`docker compose`: http://docs.docker.com/compose/
.. _`payments-env`: https://github.com/mozilla/payments-env
