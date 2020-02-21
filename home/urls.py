from django.conf.urls import url
from home.views import HomeView, index_view

urlpatterns = [

    url(r'^$', index_view, name='index'),
    url(r'^home/$', HomeView.as_view(), name='home'),
    ]
