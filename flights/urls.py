from django.urls import re_path

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

    re_path(r'^geojson/airports/(?P<user_id>\d+)/$',
            geoJSON_airports_view, name='geojson_airports'),
    re_path(r'^geojson/routes/(?P<user_id>\d+)/$',
            geoJSON_routes_view, name='geojson_routes'),

    # autocomplete urls
    re_path('aircraft-autocomplete/', AircraftAutocomplete.as_view(),
            name='aircraft-autocomplete'),
    re_path('tailnumber-autocomplete/', TailNumberAutocomplete.as_view(),
            name='tailnumber-autocomplete'),

    # date view paths
    # Lists all avialable years
    re_path('flights/by_date/', FlightArchive.as_view(), name='flight_by_date'),
    # Example: flights/2012/
    re_path('flights/by_date/<year>',
            FlightArchiveYear.as_view(), name='flight_by_year'),
    # Example: flights/2012/nov/
    re_path('flights/by_date/<year>/<month>',
            FlightArchiveMonth.as_view(), name='flight_by_month'),
    # Example: flights/2012/nov/15
    # re_path(r'^flights/by_date/(?P<year>[0-9]{4})/(?P<month>[-\w]+)/(?P<day>[0-9]+)/$', FlightArchiveDay.as_view(), name='flight_by_day'),

    # model CRUD paths
    re_path('logbook/', FlightList.as_view(), name='flight_list'),
    re_path('logbook/create/', FlightCreate.as_view(), name='flight_create'),
    re_path('logbook/update/<pk>', FlightUpdate.as_view(), name='flight_update'),
    re_path('logbook/detail/<pk>', FlightDetail.as_view(), name='flight_detail'),
    re_path('logbook/delete/<pk>', FlightDelete.as_view(), name='flight_delete'),
    re_path('logbook/remarks/', RemarksList.as_view(), name='remarks'),

    re_path('aircraft/', TailNumberList.as_view(), name='aircraft_list'),
    re_path('aircraft/create', AircraftCreate.as_view(), name='aircraft_create'),
    re_path('aircraft/update/<pk>', AircraftUpdate.as_view(),
            name='aircraft_update'),
    re_path('aircraft/detail/<pk>', AircraftDetail.as_view(),
            name='aircraft_detail'),
    re_path('aircraft/delete/<pk>', AircraftDelete.as_view(),
            name='aircraft_delete'),

    re_path('tailnumbers/', TailNumberList.as_view(), name='tailnumber_list'),
    re_path('tailnumbers/create/', TailNumberCreate.as_view(),
            name='tailnumber_create'),
    re_path('tailnumbers/update/<pk>',
            TailNumberUpdate.as_view(), name='tailnumber_update'),
    re_path('tailnumbers/detail/<pk>',
            TailNumberDetail.as_view(), name='tailnumber_detail'),
    re_path('tailnumbers/delete/<pk>',
            TailNumberDelete.as_view(), name='tailnumber_delete'),

    re_path('imported/', ImportedListView.as_view(), name='imported_list'),
    re_path('imported/create/', ImportedCreateView.as_view(),
            name='imported_create'),
    re_path('imported/detail/<pk>', ImportedDetailView.as_view(),
            name='imported_detail'),
    re_path('imported/update/<pk>', ImportedUpdateView.as_view(),
            name='imported_update'),
    re_path('imported/delete/<pk>', ImportedDeleteView.as_view(),
            name='imported_delete'),
]
