import logging

from payments_service import solitude
from payments_service.solitude import constants

log = logging.getLogger(__name__)


class Transaction(object):
    key = 'transaction_pk'

    def __init__(self, session):
        self.session = session
        self.id = self.session.get(self.key, None)
        self.api = solitude.api()

    def create(self, user, plan_id, **kwargs):
        """
        Creates the session in solitude and stores the id in the session.
        """
        if self.id:
            raise ValueError('Transaction already exists in session.')

        # TODO: We could make this cleaner with mozilla/payments#57
        product = self.api.generic.product.get_object_or_404(
            external_id=plan_id)

        data = {
            'buyer': user.uri,
            'provider': constants.PROVIDER_BRAINTREE,
            'seller_product': product['resource_uri'],
            'seller': product['seller'],
            'status': constants.STATUS_STARTED,
            'type': constants.TYPE_PAYMENT
        }
        data.update(**kwargs)
        res = self.api.generic.transaction.post(data)

        self.id = self.session[self.key] = res['resource_pk']
        log.debug('Created transaction: {0}'.format(self.id))

    def succeeded(self):
        """
        Updates the transaction as a success.
        """
        self.update(status=constants.STATUS_COMPLETED)

    def errored(self, reason):
        """
        Updates the transaction as a failure.
        """
        self.update(status=constants.STATUS_ERRORED, status_reason=reason)

    def update(self, **kwargs):
        """
        Updates the session in solitude.
        """
        if not self.id:
            raise ValueError('Transaction id not set.')

        log.debug('Updating transaction: {0} with args: {1}'
                  .format(self.id, kwargs))
        self.api.generic.transaction(self.id).patch(kwargs)

    def reset(self):
        """
        Removes the transaction key from the session.
        """
        try:
            del self.session[self.key]
            log.debug('Removed existing transaction from the session.')
        except KeyError:
            pass
