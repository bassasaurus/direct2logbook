from django.urls import path
from profile.views import ProfileView, ProfileUpdateView

urlpatterns = [
    path('accounts/profile/', ProfileView.as_view(), name='profile'),
    path('accounts/profile/update/<int:pk>/',
         ProfileUpdateView.as_view(), name='profile_update'),
]
