from django.urls import path
from django.views.generic import TemplateView
from home.views import HomeView, index_view

urlpatterns = [
    path('', index_view, name='index'),
    path('privacy/', TemplateView.as_view(template_name='home/privacy.html'), name='privacy_policy'),
    path('home/', HomeView.as_view(), name='home'),
]
