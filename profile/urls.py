from django.urls import re_path
from profile.views import ProfileView, ProfileUpdateView


urlpatterns = [
    # url(r'^accounts/signup/$', signup, name='signup'),
    re_path(r'^accounts/profile/$', ProfileView.as_view(), name='profile'),
    re_path(r'^accounts/profile/update/(?P<pk>\d+)/$',
            ProfileUpdateView.as_view(), name='profile_update'),
]
