from django.conf.urls import include, url


api_patterns = [
    url(r'^auth/',
        include('payments_service.auth.urls', namespace='auth')),
    url(r'^braintree/',
        include('payments_service.braintree.urls', namespace='braintree')),
    url(r'',
        include('payments_service.status.urls', namespace='status')),
]

urlpatterns = [
    url(r'^api/', include(api_patterns))
]

handler500 = 'payments_service.base.views.error_500'
handler404 = 'payments_service.base.views.error_404'
handler403 = 'payments_service.base.views.error_403'
