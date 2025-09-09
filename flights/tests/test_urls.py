from django.test import SimpleTestCase
from django.urls import reverse, resolve
from flights.views import (
    AircraftAutocomplete, TailNumberAutocomplete,
    geoJSON_routes_view, geoJSON_airports_view,
    FlightArchive, FlightArchiveYear, FlightArchiveMonth,
    FlightList, FlightCreate, FlightUpdate, FlightDetail, FlightDelete, RemarksList,
    TailNumberList, TailNumberCreate, TailNumberUpdate, TailNumberDetail, TailNumberDelete,
    AircraftCreate, AircraftUpdate, AircraftDetail, AircraftDelete,
    ImportedListView, ImportedCreateView, ImportedUpdateView, ImportedDetailView, ImportedDeleteView
)


class TestFlightsURLs(SimpleTestCase):

    def test_geojson_airports_url_resolves(self):
        url = reverse('geojson_airports', kwargs={'user_id': 1})
        self.assertEqual(resolve(url).func, geoJSON_airports_view)

    def test_geojson_routes_url_resolves(self):
        url = reverse('geojson_routes', kwargs={'user_id': 1})
        self.assertEqual(resolve(url).func, geoJSON_routes_view)

    def test_aircraft_autocomplete_url_resolves(self):
        url = reverse('aircraft-autocomplete')
        self.assertEqual(resolve(url).func.view_class, AircraftAutocomplete)

    def test_tailnumber_autocomplete_url_resolves(self):
        url = reverse('tailnumber-autocomplete')
        self.assertEqual(resolve(url).func.view_class, TailNumberAutocomplete)

    def test_flight_archive_index_url_resolves(self):
        url = reverse('flight_by_date')
        self.assertEqual(resolve(url).func.view_class, FlightArchive)

    def test_flight_archive_year_url_resolves(self):
        url = reverse('flight_by_year', kwargs={'year': 2024})
        self.assertEqual(resolve(url).func.view_class, FlightArchiveYear)

    def test_flight_archive_month_url_resolves(self):
        url = reverse('flight_by_month', kwargs={'year': 2024, 'month': 'jan'})
        self.assertEqual(resolve(url).func.view_class, FlightArchiveMonth)

    def test_flight_list_url_resolves(self):
        url = reverse('flight_list')
        self.assertEqual(resolve(url).func.view_class, FlightList)

    def test_flight_create_url_resolves(self):
        url = reverse('flight_create')
        self.assertEqual(resolve(url).func.view_class, FlightCreate)

    def test_flight_update_url_resolves(self):
        url = reverse('flight_update', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, FlightUpdate)

    def test_flight_detail_url_resolves(self):
        url = reverse('flight_detail', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, FlightDetail)

    def test_flight_delete_url_resolves(self):
        url = reverse('flight_delete', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, FlightDelete)

    def test_remarks_url_resolves(self):
        url = reverse('remarks')
        self.assertEqual(resolve(url).func.view_class, RemarksList)

    def test_aircraft_list_url_resolves(self):
        url = reverse('aircraft_list')
        self.assertEqual(resolve(url).func.view_class, TailNumberList)

    def test_aircraft_create_url_resolves(self):
        url = reverse('aircraft_create')
        self.assertEqual(resolve(url).func.view_class, AircraftCreate)

    def test_aircraft_update_url_resolves(self):
        url = reverse('aircraft_update', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, AircraftUpdate)

    def test_aircraft_detail_url_resolves(self):
        url = reverse('aircraft_detail', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, AircraftDetail)

    def test_aircraft_delete_url_resolves(self):
        url = reverse('aircraft_delete', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, AircraftDelete)

    def test_tailnumber_list_url_resolves(self):
        url = reverse('tailnumber_list')
        self.assertEqual(resolve(url).func.view_class, TailNumberList)

    def test_tailnumber_create_url_resolves(self):
        url = reverse('tailnumber_create')
        self.assertEqual(resolve(url).func.view_class, TailNumberCreate)

    def test_tailnumber_update_url_resolves(self):
        url = reverse('tailnumber_update', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, TailNumberUpdate)

    def test_tailnumber_detail_url_resolves(self):
        url = reverse('tailnumber_detail', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, TailNumberDetail)

    def test_tailnumber_delete_url_resolves(self):
        url = reverse('tailnumber_delete', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, TailNumberDelete)

    def test_imported_list_url_resolves(self):
        url = reverse('imported_list')
        self.assertEqual(resolve(url).func.view_class, ImportedListView)

    def test_imported_create_url_resolves(self):
        url = reverse('imported_create')
        self.assertEqual(resolve(url).func.view_class, ImportedCreateView)

    def test_imported_detail_url_resolves(self):
        url = reverse('imported_detail', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, ImportedDetailView)

    def test_imported_update_url_resolves(self):
        url = reverse('imported_update', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, ImportedUpdateView)

    def test_imported_delete_url_resolves(self):
        url = reverse('imported_delete', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, ImportedDeleteView)
