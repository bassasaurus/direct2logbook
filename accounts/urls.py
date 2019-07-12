from django.conf.urls import url
from accounts.views import signup, ProfileView, ProfileUpdateView, EmailView, ConnectionsView

urlpatterns = [
    url(r'^accounts/signup/$', signup, name='signup'),
    url(r'^accounts/profile/$', ProfileView.as_view(), name='profile'),
    url(r'^accounts/profile/update/(?P<pk>\d+)/$', ProfileUpdateView.as_view(), name='profile_update'),
    #override allauth urls
    url(r'^accounts/email/$', EmailView.as_view(), name='account_email'),
    url(r'^accounts/social/connections/$', ConnectionsView.as_view(), name='socialaccount_connections'),

]
