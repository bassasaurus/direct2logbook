from django.urls import re_path

from payments.views import stripe_webhook_view, success_view, subscription_cancel_view, canceled_view

urlpatterns = [

    re_path(r'^stripe_webhook/$', stripe_webhook_view, name='stripe_webhook'),

    re_path(r'^payments/success/(?P<user>\d+)/$',
            success_view, name='payment_success'),
    re_path(r'^payments/canceled/(?P<user>\d+)/$',
            canceled_view, name='payment_canceled'),
    re_path(r'^payments/subscription_canceled/$',
            subscription_cancel_view, name='subscription_canceled'),
]
