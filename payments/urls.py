from django.conf.urls import url, include

from payments.views import *

urlpatterns = [

    url(r'^stripe_webhook/$', stripe_webhook_view, name='stripe_webhook'),


    url(r'^debug_view/$', debug_view, name='debug_view'),
    url(r'^payments/success/(?P<user>\d+)/$', success_view, name='payment_success'),
    url(r'^payments/canceled/(?P<user>\d+)/$', canceled_view, name='payment_canceled'),
    url(r'^payments/subscription_canceled/$', subscription_cancel_view, name='subscription_canceled'),
    ]
