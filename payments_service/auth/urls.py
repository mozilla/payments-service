from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url(r'^sign-in/$', views.SignInView.as_view(), name='sign-in'),
    url(r'^sign-out/$', views.SignOutView.as_view(), name='sign-out'),
)
