from django.urls import path
from profile.views import ProfileView, ProfileUpdateView, BillingStatusView

urlpatterns = [
    path('accounts/profile/billing-status/', BillingStatusView.as_view(), name='billing_status'),
    path('accounts/profile/', ProfileView.as_view(), name='profile'),
    path('accounts/profile/update/<int:pk>/',
         ProfileUpdateView.as_view(), name='profile_update'),
]
