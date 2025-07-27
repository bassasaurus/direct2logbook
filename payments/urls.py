
from django.urls import path
from payments.views import stripe_webhook_view, success_view, subscription_cancel_view, canceled_view

urlpatterns = [
    path('stripe_webhook/', stripe_webhook_view, name='stripe_webhook'),
    path('payments/success/<int:user>/', success_view, name='payment_success'),
    path('payments/canceled/<int:user>/',
         canceled_view, name='payment_canceled'),
    path('payments/subscription_canceled/',
         subscription_cancel_view, name='subscription_canceled'),
]
