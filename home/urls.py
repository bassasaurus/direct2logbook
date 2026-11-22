from django.urls import path
from django.views.generic import TemplateView
from home.views import HomeView, index_view
from profile.views import MedicalUpdateView

from home.reminder_views import (
    web_reminder_action, dismiss_dashboard_medical_warning, dismiss_dashboard_reminder, manage_reminders, remove_reminder, restore_dashboard_reminder,
)

urlpatterns = [
    path('', index_view, name='index'),
    path('privacy/', TemplateView.as_view(template_name='home/privacy.html'), name='privacy_policy'),
    path('home/reminders/medical/', MedicalUpdateView.as_view(), name='medical_update'),
    path('home/reminders/flight-review/', manage_reminders, {'reminder_kind': 'flight_review'}, name='flight_review_reminder'),
    path('home/reminders/ipc/', manage_reminders, {'reminder_kind': 'ipc'}, name='ipc_reminder'),
    path('home/reminders/instructor-renewal/', manage_reminders, {'reminder_kind': 'instructor_renewal'}, name='instructor_renewal'),
    path('home/reminders/', manage_reminders, name='manage_reminders'),
    path('home/reminders/<int:pk>/', manage_reminders, name='edit_reminder'),
    path('home/reminders/<int:pk>/remove/', remove_reminder, name='remove_reminder'),
    path('home/reminders/<int:pk>/restore/', restore_dashboard_reminder, name='restore_dashboard_reminder'),
    path('home/reminders/<int:pk>/dismiss/', dismiss_dashboard_reminder, name='dismiss_dashboard_reminder'),
    path('home/reminders/medical/dismiss/', dismiss_dashboard_medical_warning, name='dismiss_dashboard_medical_warning'),
    path('home/reminders/alerts/action/', web_reminder_action, name='web_reminder_action'),
    path('home/', HomeView.as_view(), name='home'),
]
