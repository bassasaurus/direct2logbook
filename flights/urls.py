
from django.urls import path
from flights.views import (
    AircraftAutocomplete, TailNumberAutocomplete,
    geoJSON_routes_view, geoJSON_airports_view,
    FlightArchive, FlightArchiveYear, FlightArchiveMonth,
    FlightList, FlightCreate, FlightUpdate, FlightDetail, FlightDelete, RemarksList,
    TailNumberList, TailNumberCreate, TailNumberUpdate, TailNumberDetail, TailNumberDelete,
    AircraftCreate, AircraftUpdate, AircraftDetail, AircraftDelete,
    ImportedListView, ImportedCreateView, ImportedUpdateView, ImportedDetailView, ImportedDeleteView
)

urlpatterns = [
    # GeoJSON API endpoints
    path('geojson/airports/<int:user_id>/',
         geoJSON_airports_view, name='geojson_airports'),
    path('geojson/routes/<int:user_id>/',
         geoJSON_routes_view, name='geojson_routes'),


    # autocomplete urls
    path('aircraft-autocomplete/', AircraftAutocomplete.as_view(),
         name='aircraft-autocomplete'),
    path('tailnumber-autocomplete/', TailNumberAutocomplete.as_view(),
         name='tailnumber-autocomplete'),

    # Archive views
    path('by_date/', FlightArchive.as_view(), name='flight_by_date'),
    path('by_date/<int:year>/',
         FlightArchiveYear.as_view(), name='flight_by_year'),
    path('flights/by_date/<int:year>/<str:month>/',
         FlightArchiveMonth.as_view(), name='flight_by_month'),

    # Flight CRUD
    path('logbook/', FlightList.as_view(), name='flight_list'),
    path('logbook/create/', FlightCreate.as_view(), name='flight_create'),
    path('logbook/update/<int:pk>/', FlightUpdate.as_view(), name='flight_update'),
    path('logbook/detail/<int:pk>/', FlightDetail.as_view(), name='flight_detail'),
    path('logbook/delete/<int:pk>/', FlightDelete.as_view(), name='flight_delete'),
    path('logbook/remarks/', RemarksList.as_view(), name='remarks'),

    # Aircraft CRUD (note: path might better be /aircrafts/ for plural consistency)
    path('aircraft/', TailNumberList.as_view(), name='aircraft_list'),
    path('aircraft/create/', AircraftCreate.as_view(), name='aircraft_create'),
    path('aircraft/update/<int:pk>/',
         AircraftUpdate.as_view(), name='aircraft_update'),
    path('aircraft/detail/<int:pk>/',
         AircraftDetail.as_view(), name='aircraft_detail'),
    path('aircraft/delete/<int:pk>/',
         AircraftDelete.as_view(), name='aircraft_delete'),

    # Tail Number CRUD
    path('tailnumbers/', TailNumberList.as_view(), name='tailnumber_list'),
    path('tailnumbers/create/', TailNumberCreate.as_view(),
         name='tailnumber_create'),
    path('tailnumbers/update/<int:pk>/',
         TailNumberUpdate.as_view(), name='tailnumber_update'),
    path('tailnumbers/detail/<int:pk>/',
         TailNumberDetail.as_view(), name='tailnumber_detail'),
    path('tailnumbers/delete/<int:pk>/',

         TailNumberDelete.as_view(), name='tailnumber_delete'),

    # Imported Data CRUD
    path('imported/', ImportedListView.as_view(), name='imported_list'),
    path('imported/create/', ImportedCreateView.as_view(), name='imported_create'),
    path('imported/detail/<int:pk>/',
         ImportedDetailView.as_view(), name='imported_detail'),
    path('imported/update/<int:pk>/',
         ImportedUpdateView.as_view(), name='imported_update'),
    path('imported/delete/<int:pk>/',
         ImportedDeleteView.as_view(), name='imported_delete'),
]
