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

.. _system:

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
    :param string client_id:
        The `Firefox Accounts`_ client ID that was used to generate the
        `authorization code`_. This must be one of the internally supported
        client IDs (which correspond to server domain).
    :param string access_token:
        A third party generated `Firefox Accounts`_ OAuth `access token`_.
        This would typically be generated from an initial sign-in flow
        triggered by an external app that is selling the product.
        When signing in with an `access_token` there is no need to post an
        `authorization_code` or `client_id`.

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

.. _`access token`: https://github.com/mozilla/fxa-oauth-server/blob/master/docs/api.md#user-content-post-v1token
.. _`authorization code`: https://github.com/mozilla/fxa-oauth-server/blob/master/docs/api.md#user-content-post-v1authorization
.. _`Solitude buyer`: https://solitude.readthedocs.org/en/latest/topics/generic.html#buyers
.. _`Solitude payment method`: https://solitude.readthedocs.org/en/latest/topics/braintree.html#get--braintree-mozilla-paymethod--method%20id--
.. _`Firefox Accounts`: https://developer.mozilla.org/en-US/docs/Mozilla/Tech/Firefox_Accounts

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
for the client. To support anonymous payments such as donations, this endpoint
does not require user authentication.

.. http:post:: /api/braintree/token/generate/

    **Response**:

    .. code-block:: json

        {
            "token": "ABC123",
            "csrf_token": "b026324c6904b2a9cb4b88d6d61c81d1"
        }

    :>json string token: Braintree token, returned from Solitude's
        `token generator`_, that can be used to initialize a payment form.
    :>json string csrf_token: `Django CSRF`_ token string to protect against
        cross site request forgery. You must include this in all subsequent
        requests using the ``X-CSRFToken`` request header.


.. _`retrieve a token`: https://developers.braintreepayments.com/javascript+python/reference/request/client-token/generate
.. _`token generator`: https://solitude.readthedocs.org/en/latest/topics/braintree.html#post--braintree-token-generate-
.. _`Solitude`: https://github.com/mozilla/solitude/

Payment Methods
~~~~~~~~~~~~~~~

These endpoints let you work with `Braintree payment methods`_
for the currently signed in user.

.. http:get:: /api/braintree/mozilla/paymethod/

    Retrieve all of the user's saved `payment methods`_.
    After a user submits payment, their method of payment
    (e.g. a credit card) is saved for future purchases.

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

    :status 200: results returned successfully.

.. http:post:: /api/braintree/paymethod/

    Create a new `payment method`_ for the signed in user.

    :param string nonce:
        A single use token representing the buyer's submitted payment method.
        The Braintree JS client intercepts a form
        submission (e.g. credit card numbers), obfuscates it, and gives us
        this string.

    :>json array payment_methods:
        A list of all the user's active payment methods including the one just
        created.

    Example:

    .. code-block:: json

        {
            "payment_methods": [{
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
            }]
        }

    :status 201: object created successfully.

.. http:post:: /api/braintree/paymethod/delete/

    Delete a `payment method`_ belonging to the signed in user.

    :param string pay_method_uri:
        Solitude URI to the `payment method`_ that should be deleted.

    :>json array payment_methods:
        An updated list of all the user's active payment methods after deletion.

    Example:

    .. code-block:: json

        {
            "payment_methods": [{
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
            }]
        }

    :status 200: object deleted successfully.

.. _`Braintree payment methods`: https://developers.braintreepayments.com/javascript+python/guides/payment-methods

.. http:patch:: /api/braintree/mozilla/paymethod/:id/

    This endpoint allows you to alter a payment method belonging to the signed
    in user.

    **Request**

    To make the payment method inactive:

    .. code-block:: json

        {"active": false}

    **Response**

    :status 200: response processed successfully.


Sale
~~~~

.. http:post:: /api/braintree/sale/

    This endpoint lets you create a one-time payment with the Braintree API.

    The input parameters are exactly the same as the `Solitude Sale API`_.
    Here are some additional notes:

    - This is not an auth protected end point. The user may make a payment
      anonymously as long as the product supports it.
    - If paying with a ``paymethod`` URI (a saved payment method) then the user
      must be signed in and must be the owner of that payment method.

    :status 204: sale submitted successfully

.. _`Solitude Sale API`: http://solitude.readthedocs.org/en/latest/topics/braintree.html#post--braintree-sale-

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

.. http:post:: /api/braintree/subscriptions/

    Create a new buyer subscription.
    To pay using a new credit card, submit ``pay_method_nonce``. To pay
    with a saved credit card, submit ``pay_method_uri``.

    There are currently two types of subscriptions supported, which
    vary the way this API endpoint can be used:

    **service subscriptions**

    - The user must be signed in.
    - ``amount`` cannot be used because these types of subscriptions have a
      fixed price.
    - ``email`` cannot be used because the user is already signed in.

    **recurring donations**

    - The user doesn't have to be signed in.
    - To subscribe a user without sign-in, pass in their ``email``.
    - The recurring donation ``amount`` is customizable.

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
    :param string amount:
        Custom payment amount as a decimal string.
        This only applies to subscription plans that allow
        custom amounts such as recurring donations.
    :param string email:
        Email of the person who is subscribing to the plan.
        This only applies to requests where the user has not already been
        signed in. Not all plans can be subscribed anonymously like this.
        For example, recurring donations can be created this way but
        service subscriptions cannot.

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

.. http:post:: /api/braintree/subscriptions/cancel/

    Cancel a `subscription`_. The subscription object must belong to the signed in user.

    **Request**

    :param string subscription_uri:
        Solitude URI to the `subscription`_ you want to cancel.

    **Response**

    :status 204: subscription cancelled successfully

.. _`subscription`: http://solitude.readthedocs.org/en/latest/topics/braintree.html#subscriptions


Transactions
~~~~~~~~~~~~~

These endpoints allow you to work with Braintree transactions.

.. http:get:: /api/braintree/transactions/

    Get all transactions for the currently signed in user.

    :>json array transactions:
        array of solitude transactions with the `transaction` attribute
        expanded to the `braintree transaction object`_ and the
        `seller_product` attribute expanded to the `generic product object`_.

    Example:

    .. code-block:: json

        {
            "transactions": [
                {
                    "id": 1,
                    "resource_pk": 1,
                    "resource_uri": "/braintree/mozilla/transaction/1/",
                    "created": "2015-08-07T14:53:23.966",
                    "modified": "2015-08-07T14:53:23.966",
                    "kind": "subscription_charged_successfully",
                    "transaction": {
                        "resource_pk": 1,
                        "resource_uri": "/generic/transaction/1/"
                        "seller_product": {
                            "resource_pk": 1,
                            "public_id": "mozilla-concrete-brick",
                            "seller": "/generic/seller/8/",
                            "external_id": "mozilla-concrete-brick",
                            "resource_uri": "/generic/product/1/"
                        },
                        "uuid": "bt-b-cLt3FD",
                        "seller": "/generic/seller/8/",
                        "provider": 4,
                        "type": 0,
                        "status": 2,
                        "buyer": "/generic/buyer/8/",
                        "created": "2015-08-07T14:53:24",
                        "currency": "USD",
                        "amount": "10.00"
                    },
                    "next_billing_period_amount": "10.00",
                    "paymethod":"/braintree/mozilla/paymethod/1/",
                    "billing_period_end_date": "2015-09-06T00:00:00",
                    "next_billing_date":"2015-09-06T00:00:00",
                    "billing_period_start_date": "2015-08-07T00:00:00",
                    "subscription": "/braintree/mozilla/subscription/1/"
                }
            ]
        }

    :status 200: transactions returned successfully

Webhooks
~~~~~~~~

When Braintree completes certain actions, webhooks will be sent. For more information
see the `Braintree documentation <https://developers.braintreepayments.com/javascript+python/reference/general/webhooks/overview>`_.

.. http:get:: /api/braintree/webhook/

    This request and response is the same as Solitudes `webhook API`_,
    with one exception. The Braintree server sends a HTTP Accept header of `*/*`,
    which Django Rest Framework interprets as allowing JSON. That's not the
    case and Braintree needs the token echoed back as `text/plain`. No matter
    what is set in the Accept headers, this end point will always return
    `text/plain` to satisfy Braintree.

.. http:post:: /api/braintree/webhook/

    This request and response is the same as Solitudes `webhook API`_.

.. _`Django CSRF`: https://docs.djangoproject.com/en/1.8/ref/csrf/
.. _`generic product object`: http://solitude.readthedocs.org/en/latest/topics/generic.html#product
.. _`braintree transaction object`: http://solitude.readthedocs.org/en/latest/topics/braintree.html#get--braintree-mozilla-transaction--transaction%20id--
.. _`payment method`: https://solitude.readthedocs.org/en/latest/topics/braintree.html#id2
.. _`payment methods`: https://solitude.readthedocs.org/en/latest/topics/braintree.html#id2
.. _`webhook API`: http://solitude.readthedocs.org/en/latest/topics/braintree.html#webhook
