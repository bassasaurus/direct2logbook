from django.conf.urls import url, include

from payments.views import *

urlpatterns = [

    url(r'^stripe_webhook/$', stripe_webhook_view, name='stripe_webhook'),

    # url(r'^payments/subscription_completed_webhook$', subscription_completed_webhook_view, name='subscription_completed_webhook'),
    # url(r'^payments/subscription_canceled_webhook$', subscription_canceled_webhook_view, name='subscription_canceled_webhook'),
    #
    url(r'^debug_view/$', debug_view, name='debug_view'),
    url(r'^payments/success$', success_view, name='payment_success'),
    url(r'^payments/canceled$', canceled_view, name='payment_canceled'),
    ]
