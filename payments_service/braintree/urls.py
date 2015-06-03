from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url(r'^subscriptions/$', views.Subscriptions.as_view(),
        name='subscriptions'),
    url(r'^token/generate/$', views.TokenGenerator.as_view(),
        name='token.generate'),
    url(r'^mozilla/paymethod/$', views.PayMethod.as_view(),
        name='mozilla.paymethod'),
    url(r'^webhook/$', views.Webhook.as_view(), name='webhook'),
)
