from django.urls import path, re_path
from home.views import HomeView, index_view

urlpatterns = [

    path(r'^$', index_view, name='index'),
    path(r'^home/$', HomeView.as_view(), name='home'),
]
