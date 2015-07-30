from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url(r'^subscriptions/$', views.Subscriptions.as_view(),
        name='subscriptions'),
    url(r'^subscriptions/cancel/$',
        views.CancelSubscription.as_view(),
        name='subscriptions.cancel'),
    url(r'^subscriptions/paymethod/change/$',
        views.ChangeSubscriptionPayMethod.as_view(),
        name='subscriptions.paymethod.change'),
    url(r'^token/generate/$', views.TokenGenerator.as_view(),
        name='token.generate'),
    url(r'^paymethod/?$', views.BraintreePayMethod.as_view(),
        name='braintree.paymethod'),
    url(r'^mozilla/paymethod/(?P<pk>[^/]+)?/?$', views.PayMethod.as_view(),
        name='mozilla.paymethod'),
    url(r'^webhook/$', views.Webhook.as_view(), name='webhook'),
    url(r'^webhook/email/debug/$', views.debug_email, name='debug-email')
)
