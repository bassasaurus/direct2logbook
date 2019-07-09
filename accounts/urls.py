from django.conf.urls import url
from accounts.views import ProfileView, ProfileUpdateView

urlpatterns = [
    url(r'^accounts/profile/$', ProfileView.as_view(), name='profile'),
    url(r'^accounts/profile/update/(?P<pk>\d+)/$', ProfileUpdateView.as_view(), name='profile_update'),
]
