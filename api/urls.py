from api.tailnumber_sync import MobileTailnumberSyncView
from api.mobile_recency import MobileRecencyView
from api.mobile_stats import MobileStatsView
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from api.airport_checks import RouteAirportCheckView
from api.aircraft_sync import MobileAircraftSyncView
from api.mobile_sync import MobileSessionView, MobileFlightSyncView

urlpatterns = [
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