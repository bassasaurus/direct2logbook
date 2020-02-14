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

    # date view urls
    # Lists all avialable years
    url(r'^flights/by_date/$', FlightArchive.as_view(), name='flight_by_date'),
    # Example: flights/2012/
    url(r'^flights/by_date/(?P<year>[0-9]{4})/$', FlightArchiveYear.as_view(), name='flight_by_year'),
    # Example: flights/2012/nov/
    url(r'^flights/by_date/(?P<year>[0-9]{4})/(?P<month>[-\w]+)/$', FlightArchiveMonth.as_view(), name='flight_by_month'),
    # Example: flights/2012/nov/15
    # url(r'^flights/by_date/(?P<year>[0-9]{4})/(?P<month>[-\w]+)/(?P<day>[0-9]+)/$', FlightArchiveDay.as_view(), name='flight_by_day'),

    # model CRUD urls
    url(r'^logbook/$', FlightList.as_view(), name='flight_list'),
    url(r'^logbook/create/$', FlightCreate.as_view(), name='flight_create'),
    url(r'^logbook/update/(?P<pk>\d+)/$', FlightUpdate.as_view(), name='flight_update'),
    url(r'^logbook/detail/(?P<pk>\d+)/$', FlightDetail.as_view(), name='flight_detail'),
    url(r'^logbook/delete/(?P<pk>\d+)/$', FlightDelete.as_view(), name='flight_delete'),
    url(r'^logbook/remarks$', RemarksList.as_view(), name='remarks'),

    url(r'^aircraft/$', TailNumberList.as_view(), name='aircraft_list'),
    url(r'^aircraft/create', AircraftCreate.as_view(), name='aircraft_create'),
    url(r'^aircraft/update/(?P<pk>\d+)/$', AircraftUpdate.as_view(), name='aircraft_update'),
    url(r'^aircraft/detail/(?P<pk>\d+)/$', AircraftDetail.as_view(), name='aircraft_detail'),
    url(r'^aircraft/delete/(?P<pk>\d+)/$', AircraftDelete.as_view(), name='aircraft_delete'),

    # url(r'^tailnumbers/$', TailNumberList.as_view(), name='tailnumber_list'),
    url(r'^tailnumbers/create/$', TailNumberCreate.as_view(), name='tailnumber_create'),
    url(r'^tailnumbers/update/(?P<pk>\d+)/$', TailNumberUpdate.as_view(), name='tailnumber_update'),
    url(r'^tailnumbers/detail/(?P<pk>\d+)/$', TailNumberDetail.as_view(), name='tailnumber_detail'),
    url(r'^tailnumbers/delete/(?P<pk>\d+)/$', TailNumberDelete.as_view(), name='tailnumber_delete'),

    url(r'^imported/$', ImportedListView.as_view(), name='imported_list'),
    url(r'^imported/create/$', ImportedCreateView.as_view(), name='imported_create'),
    url(r'^imported/detail/(?P<pk>\d+)/$', ImportedDetailView.as_view(), name='imported_detail'),
    url(r'^imported/update/(?P<pk>\d+)/$', ImportedUpdateView.as_view(), name='imported_update'),
    url(r'^imported/delete/(?P<pk>\d+)/$', ImportedDeleteView.as_view(), name='imported_delete'),
]
