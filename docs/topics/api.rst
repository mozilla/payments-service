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
    :status 403: user not authenticated
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

Sign-In
~~~~~~~

.. http:post:: /api/auth/sign-in/

    **Request**

    :param string access_token:
        Firefox Accounts OAuth `access token`_. This would typically be
        generated from an initial sign-in flow triggered by the app that
        wishes to sell a product. The token must be scoped for **payments**
        otherwise you will receive an error response.

    :>json string buyer_uuid: `Solitude buyer`_ identifier

    :status 200: returning buyer authenticated successfully.
    :status 201: first time buyer authenticated successfully.

.. _`access token`: https://github.com/mozilla/fxa-oauth-server/blob/master/docs/api.md#post-v1token
.. _`Solitude buyer`: https://solitude.readthedocs.org/en/latest/topics/generic.html#buyers

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
