====
API
====

The following API endpoints are available.

Status
======

Retrieve overall status of the service.

.. http:get:: /

    **Response**

    Example:

    .. code-block:: json

        {
            "ok": true,
            "solitude": {
                "connected": true,
                "error": null
            }
        }

    :>json boolean ok: either ``true`` or ``false``
    :>json boolean solitude.connected: ``true`` if `Solitude`_ is connected.
    :>json string solitude.error:
        Exception encountered when trying to connect to Solitude.
    :status 200: success.

.. _`Solitude`: https://github.com/mozilla/solitude/
