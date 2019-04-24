from django.conf.urls import url
from accounts.views import signup, ProfileView, ProfileUpdateView

urlpatterns = [
    url(r'^accounts/signup/$', signup, name='signup'),
    url(r'^accounts/profile/$', ProfileView.as_view(), name='profile'),
    url(r'^accounts/profile/update/(?P<pk>\d+)/$', ProfileUpdateView.as_view(), name='profile_update'),
]
