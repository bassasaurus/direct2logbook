from django.conf.urls import url
from accounts import views

urlpatterns = [
    url(r'^accounts/signup/$', views.signup, name='signup'),
    # url(r'^profile/$', ProfileView.as_view(), name='profile'),
    # url(r'^profile/update/(?P<pk>\d+)/$', ProfileUpdateView.as_view(), name='profile_update'),
]
