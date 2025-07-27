from django.urls import path, re_path
from .views import UserUpdateView, EmailView, ConnectionsView, PasswordSetView, PasswordChangeView, PasswordResetView, PasswordResetDoneView, PasswordResetFromKeyView, PasswordResetFromKeyDoneView


urlpatterns = [
    re_path(r'^accounts/user/update/(?P<pk>\d+)/$',
            UserUpdateView.as_view(), name='user_update'),
    # override allauth urls
    path(r'^accounts/email/$', EmailView.as_view(), name='account_email'),
    path(r'^accounts/social/connections/$',
         ConnectionsView.as_view(), name='socialaccount_connections'),
    path(r'^accounts/password/set/$', PasswordSetView.as_view(),
         name='account_set_password'),
    path(r'^accounts/password/change/$', PasswordChangeView.as_view(),
         name='account_change_password'),
    path(r'^accounts/password/reset/$', PasswordResetView.as_view(),
         name='account_change_password'),
    path(r'^accounts/password/reset/done/$',
         PasswordResetDoneView.as_view(), name='account_password_reset_done'),
    re_path(r"^accounts/password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$",
            PasswordResetFromKeyView.as_view(),
            name="account_reset_password_from_key"),
    path(r"^password/reset/key/done/$", PasswordResetFromKeyDoneView.as_view(),
         name="account_reset_password_from_key_done"),
]
