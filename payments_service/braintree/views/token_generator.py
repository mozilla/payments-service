from payments_service.solitude import SolitudeBodyguard


class TokenGenerator(SolitudeBodyguard):
    """
    Generate a client token to begin processing payments.
    """
    methods = ['post']
    resource = 'braintree.token.generate'
