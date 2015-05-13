from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url(r'^sign-in/$', views.sign_in, name='sign-in'),
)
