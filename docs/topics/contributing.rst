============
Contributing
============

If you'd like to contribute a feature to the service, here's how to get set up.

Local Installation
==================

Installation is done through `docker compose`_ from `payments-env`_.
As documented in the `payments-env`_ README, follow the instructions for
setting up a development environment then start your development servers with
something like this::

    cd /path/to/payments-env/
    docker-compose up -d

That's it! You are ready to access the API. Try it out by running this with
curl on your host machine (not docker)::

    curl -v http://pay.dev:8000/api/

You should see a successful health check of the :ref:`system`::

    {"solitude":{"connected":true,"error_response":null,"error":"False"},"ok":true}

Running Tests
=============

You also need `payments-env`_ to run the test suite. After starting up all
docker containers, start a shell into the service container. An easy way to do
this is with `docker-utils`_::

    cd /path/to/payments-env/
    docker-utils bash service

Now you can run all tests with the usual Django command::

    python manage.py test

Building Documentation
======================

If you need to make a patch that includes documentation, you should build the
docs to make sure they render without errors. In your docker container shell
run::

    make -C docs html

Then go back to your host machine (not docker) and open ``docs/_build/html/index.html``
from your `payments-service` source directory.

Sending email
=============

To send email set the ``SERVICE_EMAIL_*`` settings that match the `Django settings`_ in your environment. For example::

    export SERVICE_EMAIL_HOST=your.server.com

To avoid sending email to everyone, use a filtered email backend::

    export SERVICE_EMAIL_BACKEND=payments_service.base.email.FilteredEmailBackend

This will read the ``EMAIL_ALLOWED_LIST`` setting and only send email to emails in that list. By default that is::

    EMAIL_ALLOWED_LIST = ['.*@mozilla\.com$']

Debugging email
---------------

Debugging HTML email is hard. To see what an email looks like, you must first:

* complete a subscription with a user
* generate a transaction, either using a real Braintree webhook or the `braintree_webhook`_ command

Ensure that ``DEBUG`` is enabled for payments-service.

Visit: http://pay.dev:8000/api/braintree/webhook/email/debug/

Parameters:
* ``kind``: the kind of email to generate, matches the names of the webhooks for the `braintree_webhook`_ command. Default: ``subscription_charged_successfully``
* ``premailed``: if the HTML should be pre-processed or not, any value turns processing on. Default: no.

Generating processed HTML
-------------------------

Run the command::

    python manage.py premail

This will pre-generate all the HTML for premailed emails so they can be checked into git. It uses the value set in settings at::

    EMAIL_URL_ROOT

To find the CSS.

Bugs and Patches
================

You can submit bug reports and patches at
https://github.com/mozilla/payments-service/


.. _`Django settings`: https://docs.djangoproject.com/en/1.8/ref/settings/#email-host
.. _`docker compose`: http://docs.docker.com/compose/
.. _`docker-utils`: https://github.com/andymckay/docker-utils
.. _`hot reloader mode`: https://github.com/mozilla/payments-ui#hot-module-reloading
.. _`payments-env`: https://github.com/mozilla/payments-env
.. _`braintree_webhook`: http://payments.readthedocs.org/en/latest/testing.html#generating-webhooks
