from django.conf.urls import url

from payments.views import stripe_webhook_view, success_view, subscription_cancel_view, canceled_view

urlpatterns = [

    url(r'^stripe_webhook/$', stripe_webhook_view, name='stripe_webhook'),

    url(r'^payments/success/(?P<user>\d+)/$', success_view, name='payment_success'),
    url(r'^payments/canceled/(?P<user>\d+)/$', canceled_view, name='payment_canceled'),
    url(r'^payments/subscription_canceled/$', subscription_cancel_view, name='subscription_canceled'),
]
