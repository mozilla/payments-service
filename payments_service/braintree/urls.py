from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url(r'^subscriptions/$', views.Subscriptions.as_view(),
        name='subscriptions'),
    url(r'^token/generate/$', views.TokenGenerator.as_view(),
        name='token.generate'),
    url(r'^webhook/$', views.Webhook.as_view(), name='webhook'),
)
