from ..solitude import SolitudeBodyguard


class TokenGenerator(SolitudeBodyguard):
    methods = ['post']
    resource = 'braintree.token.generate'
