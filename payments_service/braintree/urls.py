from django.conf.urls import patterns, url

from .views.subscriptions import (
    CancelSubscription, ChangeSubscriptionPayMethod, Subscriptions
)
from .views.token_generator import TokenGenerator
from .views.paymethod import (BraintreePayMethod, DeleteBraintreePayMethod,
                              PayMethod)
from .views.webhook import debug_email, Webhook


urlpatterns = patterns(
    '',
    url(r'^subscriptions/$', Subscriptions.as_view(),
        name='subscriptions'),
    url(r'^subscriptions/cancel/$', CancelSubscription.as_view(),
        name='subscriptions.cancel'),
    url(r'^subscriptions/paymethod/change/$',
        ChangeSubscriptionPayMethod.as_view(),
        name='subscriptions.paymethod.change'),
    url(r'^token/generate/$', TokenGenerator.as_view(), name='token.generate'),
    url(r'^paymethod/$', BraintreePayMethod.as_view(), name='paymethod'),
    url(r'^paymethod/delete/$', DeleteBraintreePayMethod.as_view(),
        name='paymethod.delete'),
    url(r'^mozilla/paymethod/(?P<pk>[^/]+)?/?$', PayMethod.as_view(),
        name='mozilla.paymethod'),
    url(r'^webhook/$', Webhook.as_view(), name='webhook'),
    url(r'^webhook/email/debug/$', debug_email, name='debug-email')
)
