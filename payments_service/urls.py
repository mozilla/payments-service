from django.conf.urls import include, url


urlpatterns = [
    url(r'', include('payments_service.status.urls')),
]
