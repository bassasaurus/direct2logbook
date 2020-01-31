from django.conf.urls import url
from accounts.views import ProfileView, ProfileUpdateView, UserUpdateView, EmailView, ConnectionsView, PasswordSetView, PasswordChangeView, PasswordResetView, PasswordResetDoneView, PasswordResetFromKeyView, PasswordResetFromKeyDoneView


urlpatterns = [
    url(r'^accounts/user/update/(?P<pk>\d+)/$',
        UserUpdateView.as_view(), name='user_update'),
    # override allauth urls
    url(r'^accounts/email/$', EmailView.as_view(), name='account_email'),
    url(r'^accounts/social/connections/$',
        ConnectionsView.as_view(), name='socialaccount_connections'),
    url(r'^accounts/password/set/$', PasswordSetView.as_view(),
        name='account_set_password'),
    url(r'^accounts/password/change/$', PasswordChangeView.as_view(),
        name='account_change_password'),
    url(r'^accounts/password/reset/$', PasswordResetView.as_view(),
        name='account_change_password'),
    url(r'^accounts/password/reset/done/$',
        PasswordResetDoneView.as_view(), name='account_password_reset_done'),
    url(r"^accounts/password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$",
        PasswordResetFromKeyView.as_view(),
        name="account_reset_password_from_key"),
    url(r"^password/reset/key/done/$", PasswordResetFromKeyDoneView.as_view(),
        name="account_reset_password_from_key_done"),
]
