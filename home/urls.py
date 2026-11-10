from django.urls import path
from django.views.generic import TemplateView
from home.views import HomeView, index_view

from home.reminder_views import manage_reminders, remove_reminder, dismiss_dashboard_reminder

urlpatterns = [
    path('', index_view, name='index'),
    path('privacy/', TemplateView.as_view(template_name='home/privacy.html'), name='privacy_policy'),
    path('home/reminders/', manage_reminders, name='manage_reminders'),
    path('home/reminders/<int:pk>/', manage_reminders, name='edit_reminder'),
    path('home/reminders/<int:pk>/remove/', remove_reminder, name='remove_reminder'),
    path('home/reminders/<int:pk>/dismiss/', dismiss_dashboard_reminder, name='dismiss_dashboard_reminder'),
    path('home/', HomeView.as_view(), name='home'),
]
