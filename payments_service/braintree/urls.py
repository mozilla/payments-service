from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url(r'^token/generate/$', views.TokenGenerator.as_view(),
        name='token.generate'),
)
