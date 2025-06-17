from django.urls import path
from home.views import HomeView, index_view

urlpatterns = [

    path('', index_view, name='index'),
    path('home/', HomeView.as_view(), name='home'),
]
