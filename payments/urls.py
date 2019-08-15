from django.conf.urls import url, include

from payments.views import *

urlpatterns = [

    url(r'^payments/stripe_webhook$', stripe_webhook_view, name='stripe_webhook'),
    ]
