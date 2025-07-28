from django.test import SimpleTestCase
from django.urls import resolve
from django.contrib import admin
from api import views as api_views


class TestProjectURLs(SimpleTestCase):
    def test_admin_url_resolves(self):
        url = '/admin/'
        resolver = resolve(url)
        self.assertEqual(resolver.func.__module__,
                         admin.site.get_urls()[0].callback.__module__)

    def test_api_users_url_resolves(self):
        url = '/api/users/'
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, api_views.UserViewSet)

    def test_api_flights_url_resolves(self):
        url = '/api/flights/'
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, api_views.FlightViewSet)

    def test_api_aircraft_url_resolves(self):
        url = '/api/aircraft/'
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, api_views.AircraftViewSet)

    def test_api_tailnumbers_url_resolves(self):
        url = '/api/tailnumbers/'
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, api_views.TailNumberViewSet)

    def test_sentry_debug_url_resolves(self):
        url = '/sentry-debug/'
        resolver = resolve(url)
        self.assertEqual(resolver.func.__name__, 'trigger_error')
