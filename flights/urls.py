from django.urls import path
from django.conf.urls import url

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

    # autocomplete urls
    url(r'^aircraft-autocomplete/$', AircraftAutocomplete.as_view(), name='aircraft-autocomplete'),
    url(r'^tailnumber-autocomplete/$', TailNumberAutocomplete.as_view(), name='tailnumber-autocomplete'),
    url(r'^geojson/airports/(?P<user_id>\d+)/$', geoJSON_airports_view, name='geojson_airports'),
    url(r'^geojson/routes/(?P<user_id>\d+)/$', geoJSON_routes_view, name='geojson_routes'),

    # date view paths
    # Lists all avialable years
    path(r'^flights/by_date/$', FlightArchive.as_view(), name='flight_by_date'),
    # Example: flights/2012/
    path(r'^flights/by_date/(?P<year>[0-9]{4})/$', FlightArchiveYear.as_view(), name='flight_by_year'),
    # Example: flights/2012/nov/
    path(r'^flights/by_date/(?P<year>[0-9]{4})/(?P<month>[-\w]+)/$', FlightArchiveMonth.as_view(), name='flight_by_month'),
    # Example: flights/2012/nov/15
    # path(r'^flights/by_date/(?P<year>[0-9]{4})/(?P<month>[-\w]+)/(?P<day>[0-9]+)/$', FlightArchiveDay.as_view(), name='flight_by_day'),

    # model CRUD paths
    path('logbook/', FlightList.as_view(), name='flight_list'),
    path('logbook/create/', FlightCreate.as_view(), name='flight_create'),
    path('logbook/update/<pk>', FlightUpdate.as_view(), name='flight_update'),
    path('logbook/detail/<pk>', FlightDetail.as_view(), name='flight_detail'),
    path('logbook/delete/<pk>', FlightDelete.as_view(), name='flight_delete'),
    path('logbook/remarks/', RemarksList.as_view(), name='remarks'),

    path('aircraft/', TailNumberList.as_view(), name='aircraft_list'),
    path('aircraft/create', AircraftCreate.as_view(), name='aircraft_create'),
    path('aircraft/update/<pk>', AircraftUpdate.as_view(), name='aircraft_update'),
    path('aircraft/detail/<pk>', AircraftDetail.as_view(), name='aircraft_detail'),
    path('aircraft/delete/<pk>', AircraftDelete.as_view(), name='aircraft_delete'),

    # path(r'^tailnumbers/$', TailNumberList.as_view(), name='tailnumber_list'),
    path('tailnumbers/create/$', TailNumberCreate.as_view(), name='tailnumber_create'),
    path('tailnumbers/update/<pk>', TailNumberUpdate.as_view(), name='tailnumber_update'),
    path('tailnumbers/detail/<pk>', TailNumberDetail.as_view(), name='tailnumber_detail'),
    path('tailnumbers/delete/<pk>', TailNumberDelete.as_view(), name='tailnumber_delete'),

    path(r'^imported/$', ImportedListView.as_view(), name='imported_list'),
    path(r'^imported/create/$', ImportedCreateView.as_view(), name='imported_create'),
    path(r'^imported/detail/(?P<pk>\d+)/$', ImportedDetailView.as_view(), name='imported_detail'),
    path(r'^imported/update/(?P<pk>\d+)/$', ImportedUpdateView.as_view(), name='imported_update'),
    path(r'^imported/delete/(?P<pk>\d+)/$', ImportedDeleteView.as_view(), name='imported_delete'),
]
