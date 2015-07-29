====
API
====

The following sections document the available API endpoints and general API usage.

Errors
======

When any endpoint responds with a 4xx or 5xx status code, the response
will give you some additional details.

.. http:post:: /example-endpoint

    **Response**:

    This is what a 400 response might look like when a required parameter
    called ``first_name`` is missing from the POST.

    .. code-block:: json

        {
            "error_message": "Bad Request",
            "error_response": {"first_name": ["This field is required"]}
        }

    You might see an error response that pertains to all fields,
    like this:

    .. code-block:: json

        {
            "error_message": "Forbidden",
            "error_response": {"__all__": ["User is not authenticated"]}
        }

    :>json string error_message: brief summary of the error
    :>json object error_response:
        object with more information. This might be empty.

    :status 400: problem with the request
    :status 403:
        * user not authenticated
        * CSRF token (from `sign-in`_) is missing or invalid
    :status 404: endpoint doesn't exist
    :status 405: endpoint doesn't support this method
    :status 500: unexpected error

System
======

These are endpoints that give you information about the system.

Status
~~~~~~

Retrieve overall status of the service.

.. http:get:: /api/

    **Response**:

    .. code-block:: json

        {
            "ok": true,
            "solitude": {
                "connected": true,
                "error": null,
                "error_response": null
            }
        }

    :>json boolean ok: either ``true`` or ``false``
    :>json boolean solitude.connected: ``true`` if `Solitude`_ is connected.
    :>json string solitude.error:
        Exception encountered when trying to connect to Solitude.
    :>json string solitude.error_response:
        Object describing the error, as returned from `Solitude`_.
    :status 203: the system is OK.
    :status 500: the system has errors.

User Auth
=========

These endpoints deal with user authentication and authorization.

.. sign-in:

Sign-In
~~~~~~~

Authenticates the user and saves state to a session cookie (delivered in the
response). You can sign in either with an `authorization code`_ or an
`access token`_, as explained below. If you sign in with an
`authorization code`_, it will be exchanged for an `access token`_
which will then be verified.
The access token derived from any sign-in method must be scoped for
**payments** and **profile:email** otherwise the sign-in will fail.

.. http:post:: /api/auth/sign-in/

    **Request**

    :param string authorization_code:
        An internally created `Firefox Accounts`_ OAuth `authorization code`_.
        This would typically be generated using an internal client ID from
        a login screen on the payments management app.
    :param string access_token:
        A third party generated `Firefox Accounts`_ OAuth `access token`_.
        This would typically be generated from an initial sign-in flow
        triggered by an external app that is selling the product.

    :>json string buyer_uuid: `Solitude buyer`_ uuid identifier
    :>json string buyer_pk: `Solitude buyer`_ pk identifier
    :>json string buyer_email:
        `Firefox Accounts`_ email address that the buyer signed in with
    :>json array payment_methods:
        A list of the user's pre-saved `Solitude payment method`_ objects.
        If the user hasn't saved any payment methods yet, this will be an
        empty list.
    :>json string csrf_token: `Django CSRF`_ token string to protect against
        cross site request forgery. You must include this in all subsequent
        requests using the ``X-CSRFToken`` request header.

    :status 200: returning buyer authenticated successfully.
    :status 201: first time buyer authenticated successfully.

.. _`access token`: https://github.com/mozilla/fxa-oauth-server/blob/master/docs/api.md#post-v1token
.. _`authorization code`: https://github.com/mozilla/fxa-oauth-server/blob/master/docs/api.md#post-v1authorization
.. _`Solitude buyer`: https://solitude.readthedocs.org/en/latest/topics/generic.html#buyers
.. _`Solitude payment method`: https://solitude.readthedocs.org/en/latest/topics/braintree.html#get--braintree-mozilla-paymethod--method%20id--
.. _`Django CSRF`: https://docs.djangoproject.com/en/1.8/ref/csrf/
.. _`Firefox Accounts`: https://wiki.mozilla.org/Identity/Firefox_Accounts

Sign-Out
~~~~~~~~

Destroys the signed-in user's session.

.. http:post:: /api/auth/sign-out/

    :status 204: user signed out successfully.

Braintree
=========

These are endpoints that let you work with `braintree`_.

.. _braintree: https://www.braintreepayments.com/

Token Generator
~~~~~~~~~~~~~~~

To begin a payment you need to call this endpoint to `retrieve a token`_
for the client.

.. _`retrieve a token`: https://developers.braintreepayments.com/javascript+python/reference/request/client-token/generate

.. http:post:: /api/braintree/token/generate/

    **Response**:

    .. code-block:: json

        {
            "token": "ABC123"
        }

    This response is exactly the same as Solitude's
    `token generator`_

.. _`token generator`: https://solitude.readthedocs.org/en/latest/topics/braintree.html#generate-a-token
.. _`Solitude`: https://github.com/mozilla/solitude/

Payment Methods
~~~~~~~~~~~~~~~

This endpoint lets you retrieve saved `Braintree payment methods`_
for the currently logged in user. After a user submits payment,
their method of payment (e.g. a credit card) is saved for future purchases.

.. http:get:: /api/braintree/mozilla/paymethod/

    **Request**

    :param boolean active:
        When true (the default), only retrieve active payment methods.

    **Response**

    .. code-block:: json

        [
            {
                "id": 1,
                "resource_pk": 1,
                "resource_uri": "/braintree/mozilla/paymethod/1/",
                "type": 1,
                "type_name": "Visa",
                "truncated_id": "1111",
                "provider_id": "49fv4m",
                "braintree_buyer": "/braintree/mozilla/buyer/1/",
                "counter": 0,
                "active": true,
                "created": "2015-06-02T15:20:03",
                "modified": "2015-06-02T15:20:03"
            }
        ]

    See the Solitude docs on `payment methods`_ for detailed documentation of
    this return value.

.. _`Braintree payment methods`: https://developers.braintreepayments.com/javascript+python/guides/payment-methods
.. _`payment methods`: https://solitude.readthedocs.org/en/latest/topics/braintree.html#id2

Limited ability to alter the pay method is available. To set the payment method
to inactive:

.. http:patch:: /api/braintree/mozilla/paymethod/:id/

    **Request**

    .. code-block:: json

        {"active": false}

    **Response**

    :status 200: response processed successfully.


Subscriptions
~~~~~~~~~~~~~

These endpoints allow you to work with Braintree plan subscriptions.

.. http:get:: /api/braintree/subscriptions/

    Get all active subscriptions for the currently signed in user.

    :>json array subscriptions:
        array of `solitude subscriptions`_ with the `seller_product` attribute
        expanded to the target `generic product object`_.

    Example:

    .. code-block:: json

        {
            "subscriptions": [{
                "id": 1,
                "resource_uri": "/braintree/mozilla/subscription/1/",
                "resource_pk": 1,
                "provider_id": "4r2fh6",
                "paymethod": "/braintree/mozilla/paymethod/1/",
                "seller_product":{
                    "resource_pk": 1,
                    "resource_uri": "/generic/product/1/",
                    "public_id": "mozilla-concrete-brick",
                    "external_id": "mozilla-concrete-brick",
                    "seller": "/generic/seller/8/",
                    "seller_uuids": {
                        "bango": null,
                        "reference": null
                    },
                    "access": 1,
                    "secret": null
                },
                "active": true,
                "counter": 0,
                "created": "2015-07-29T11:41:09",
                "modified": "2015-07-29T11:41:09"
            }]
        }

    :status 200: subscriptions returned successfully

.. _`solitude subscriptions`: http://solitude.readthedocs.org/en/latest/topics/braintree.html#get--braintree-mozilla-subscription--subscription%20id--
.. _`generic product object`: http://solitude.readthedocs.org/en/latest/topics/generic.html#product

.. http:post:: /api/braintree/subscriptions/

    Create a new buyer subscription.
    To pay using a new credit card, submit ``pay_method_nonce``. To pay
    with a saved credit card, submit ``pay_method_uri``.

    **Request**

    :param string pay_method_nonce:
        A single use token representing the buyer's submitted payment method.
        In the buy flow, the Braintree JS client intercepts a form
        submission (e.g. credit card numbers), obfuscates it, and gives us
        this string.
    :param string pay_method_uri:
        Solitude URI to an existing `payment method`_ for this buyer.
        When paying with a saved card, post this value instead of a nonce.
    :param string plan_id:
        Braintree subscription `plan ID`_. If the logged in user is already
        subscribed to this plan, you'll get an error.

    **Response**

    :status 204: subscription created successfully

.. _`plan ID`: https://developers.braintreepayments.com/javascript+python/reference/response/plan

.. http:post:: /api/braintree/subscriptions/paymethod/change/

    Change the `payment method`_ for a given subscription.
    The subscription and payment method objects must belong
    to the signed in user.

    **Request**

    :param string new_pay_method_uri:
        Solitude URI to the new `payment method`_ for the subscription.
    :param string subscription_uri:
        Solitude URI to the `subscription`_ you want to change.

    **Response**

    :status 204: subscription changed successfully

.. _`payment method`: https://solitude.readthedocs.org/en/latest/topics/braintree.html#id2

.. http:post:: /api/braintree/subscriptions/cancel/

    Cancel a `subscription`_. The subscription object must belong to the signed in user.

    **Request**

    :param string subscription_uri:
        Solitude URI to the `subscription`_ you want to cancel.

    **Response**

    :status 204: subscription cancelled successfully

.. _`subscription`: http://solitude.readthedocs.org/en/latest/topics/braintree.html#subscriptions

Webhooks
~~~~~~~~

When Braintree completes certain actions, webhooks will be sent. For more information
see the `Braintree documentation <https://developers.braintreepayments.com/javascript+python/reference/general/webhooks>`_.

.. http:get:: /api/braintree/webhook/

    This request and response is the same as Solitudes `webhook API`_,
    with one exception. The Braintree server sends a HTTP Accept header of `*/*`,
    which Django Rest Framework interprets as allowing JSON. That's not the
    case and Braintree needs the token echoed back as `text/plain`. No matter
    what is set in the Accept headers, this end point will always return
    `text/plain` to satisfy Braintree.

.. http:post:: /api/braintree/webhook/

    This request and response is the same as Solitudes `webhook API`_.

.. _`webhook API`: http://solitude.readthedocs.org/en/latest/topics/braintree.html#webhook
