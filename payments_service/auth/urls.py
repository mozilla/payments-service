from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url(r'^sign-in/$', views.SignInView.as_view(), name='sign-in'),
)
