from api.mobile_reminders import (
    MobileReminderDismissView, MobileRemindersView, MobileSavedRemindersView, MobileSavedReminderView,
)
from api.mobile_signature import MobileSignatureView
from api.mobile_profile import MobileProfileView
from api.tailnumber_sync import MobileTailnumberSyncView
from api.mobile_recency import MobileRecencyView
from api.mobile_stats import MobileStatsView
from api.aircraft_default import MobileDefaultAircraftView
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from api.airport_checks import RouteAirportCheckView
from api.aircraft_sync import MobileAircraftSyncView
from api.mobile_sync import MobileSessionView, MobileFlightSyncView

urlpatterns = [
    path('mobile/reminders/', MobileRemindersView.as_view(), name='mobile_reminders'),
    path('mobile/reminders/manage/', MobileSavedRemindersView.as_view(), name='mobile_manage_reminders'),
    path('mobile/reminders/manage/<int:pk>/', MobileSavedReminderView.as_view(), name='mobile_manage_reminder'),
    path('mobile/reminders/<int:pk>/dismiss/', MobileReminderDismissView.as_view(), name='mobile_reminder_dismiss'),
    path('mobile/signature/', MobileSignatureView.as_view(), name='mobile_signature'),
    path('mobile/profile/', MobileProfileView.as_view(), name='mobile_profile'),
    path('mobile/default-aircraft/', MobileDefaultAircraftView.as_view(), name='mobile_default_aircraft'),
    path('mobile/recency/', MobileRecencyView.as_view(), name='mobile_recency'),
    path('mobile/stats/', MobileStatsView.as_view(), name='mobile_stats'),
    path('mobile/tailnumber-sync/', MobileTailnumberSyncView.as_view(), name='mobile_tailnumber_sync'),
    path('mobile/route-airport-check/', RouteAirportCheckView.as_view(), name='mobile_route_airport_check'),
    path('mobile/aircraft-sync/', MobileAircraftSyncView.as_view(), name='mobile_aircraft_sync'),
    path('mobile/session/', MobileSessionView.as_view(), name='mobile_session'),
    path('mobile/flight-sync/', MobileFlightSyncView.as_view(), name='mobile_flight_sync'),
    path('token-auth/', obtain_auth_token,
         name='api_token_auth'),
]