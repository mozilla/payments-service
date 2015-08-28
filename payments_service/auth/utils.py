import logging

from django.core.exceptions import ObjectDoesNotExist

from .. import solitude

log = logging.getLogger(__name__)


def set_up_braintree_customer(buyer):
    """
    Make sure this user has a braintree customer which is needed for
    pretty much all subsequent API interactions involving braintree.
    """
    api = solitude.api()
    try:
        api.braintree.mozilla.buyer.get_object_or_404(
            buyer=buyer['resource_pk'])
        log.info('using existing braintree customer tied to buyer {b}'
                 .format(b=buyer))
    except ObjectDoesNotExist:
        log.info('creating new braintree customer for {buyer}'
                 .format(buyer=buyer['resource_pk']))
        api.braintree.customer.post({'uuid': buyer['uuid']})
