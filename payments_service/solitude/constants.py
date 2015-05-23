# Pulled from solitude constants.
PROVIDER_BRAINTREE = 4

# Please see the solitue docs for an explanation of these.
STATUS_PENDING = 0
STATUS_COMPLETED = 1
STATUS_CHECKED = 2
STATUS_RECEIVED = 3
STATUS_FAILED = 4
STATUS_CANCELLED = 5
# These are statuses that reflect the transactions state in solitude
# as it is configured by the client.
STATUS_STARTED = 6
STATUS_ERRORED = 7

TYPE_PAYMENT = 0
TYPE_REFUND = 1
TYPE_REVERSAL = 2
TYPE_REFUND_MANUAL = 3
TYPE_REVERSAL_MANUAL = 4
