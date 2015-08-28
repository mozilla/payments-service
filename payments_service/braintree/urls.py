from django.conf.urls import patterns, url

from payments_service.base.views import composed_view

from .views.subscriptions import (
    CancelSubscription, ChangeSubscriptionPayMethod, CreateSubscriptions,
    RetrieveSubscriptions,
)
from .views.token_generator import TokenGenerator
from .views.paymethod import (BraintreePayMethod, DeleteBraintreePayMethod,
                              PayMethod)
from .views.sale import Sale
from .views.transactions import Transactions
from .views.webhook import debug_email, Webhook


urlpatterns = patterns(
    '',
    url(r'^sale/$', Sale.as_view(), name='sale'),
    url(r'^subscriptions/$',
        composed_view({
            'get': RetrieveSubscriptions.as_view(),
            'post': CreateSubscriptions.as_view(),
            # TODO: I think I need 'options' for CORS. This is a note to self
            # so I can test it before merging.
        }), name='subscriptions'),
    url(r'^subscriptions/cancel/$', CancelSubscription.as_view(),
        name='subscriptions.cancel'),
    url(r'^subscriptions/paymethod/change/$',
        ChangeSubscriptionPayMethod.as_view(),
        name='subscriptions.paymethod.change'),
    url(r'^transactions/$', Transactions.as_view(),
        name='transactions'),
    url(r'^token/generate/$', TokenGenerator.as_view(), name='token.generate'),
    url(r'^paymethod/$', BraintreePayMethod.as_view(), name='paymethod'),
    url(r'^paymethod/delete/$', DeleteBraintreePayMethod.as_view(),
        name='paymethod.delete'),
    url(r'^mozilla/paymethod/(?P<pk>[^/]+)?/?$', PayMethod.as_view(),
        name='mozilla.paymethod'),
    url(r'^webhook/$', Webhook.as_view(), name='webhook'),
    url(r'^webhook/email/debug/$', debug_email, name='debug-email')
)
