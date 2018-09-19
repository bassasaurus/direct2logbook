from django.conf.urls import url
from accounts import views

urlpatterns = [
    url(r'^accounts/signup/$', views.signup, name='signup'),
]
