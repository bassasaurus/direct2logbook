from django.urls import path
from .views import (
    UserUpdateView, EmailView, ConnectionsView, PasswordSetView,
    PasswordChangeView, PasswordResetView, PasswordResetDoneView,
    PasswordResetFromKeyView, PasswordResetFromKeyDoneView
)

urlpatterns = [
    path('accounts/user/update/<int:pk>/',
         UserUpdateView.as_view(), name='user_update'),

    # override allauth urls
    path('accounts/email/', EmailView.as_view(), name='account_email'),
    path('accounts/social/connections/', ConnectionsView.as_view(),
         name='socialaccount_connections'),
    path('accounts/password/set/', PasswordSetView.as_view(),
         name='account_set_passwoçrd'),
    path('accounts/password/change/', PasswordChangeView.as_view(),
         name='account_change_password'),
    path('accounts/password/reset/', PasswordResetView.as_view(),
         name='account_change_password'),
    path('accounts/password/reset/done/', PasswordResetDoneView.as_view(),
         name='account_password_reset_done'),
    path('accounts/password/reset/key/<str:uidb36>-<str:key>/',
         PasswordResetFromKeyView.as_view(), name='account_reset_password_from_key'),
    path('password/reset/key/done/', PasswordResetFromKeyDoneView.as_view(),
         name='account_reset_password_from_key_done'),
]