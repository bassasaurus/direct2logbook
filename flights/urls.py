from django.conf.urls import url, include

from flights.views import *

urlpatterns = [

    url(r'^home/$', HomeView.as_view(), name='home'),
    url(r'^$', IndexView.as_view(), name='index'),

    #autocomplete urls
    url(r'^aircraft-autocomplete/$', AircraftAutocomplete.as_view(), name='aircraft-autocomplete'),
    url(r'^tailnumber-autocomplete/$', TailNumberAutocomplete.as_view(), name='tailnumber-autocomplete'),
    url(r'^geojson/airports$', geoJSON_airports_view, name='geojson_airports'),
    url(r'^geojson/routes$', geoJSON_routes_view, name='geojson_routes'),

    url(r'^profile/$', ProfileView.as_view(), name='profile'),
    url(r'^profile/update/(?P<pk>\d+)/$', ProfileUpdateView.as_view(), name='profile_update'),
    #date view urls
    # Lists all avialable years
    url(r'^flights/by_date/$', FlightArchive.as_view(), name='flight_by_date'),
    # Example: flights/2012/
    url(r'^flights/by_date/(?P<year>[0-9]{4})/$', FlightArchiveYear.as_view(), name='flight_by_year'),
    # Example: flights/2012/nov/
    url(r'^flights/by_date/(?P<year>[0-9]{4})/(?P<month>[-\w]+)/$', FlightArchiveMonth.as_view(), name='flight_by_month'),

    #model CRUD urls
    url(r'^logbook/$', FlightList.as_view(), name='flight_list'),
    url(r'^logbook/create/$', FlightCreate.as_view(), name='flight_create'),
    url(r'^logbook/update/(?P<pk>\d+)/$', FlightUpdate.as_view(), name='flight_update'),
    url(r'^logbook/detail/(?P<pk>\d+)/$', FlightDetail.as_view(), name='flight_detail'),
    url(r'^logbook/delete/(?P<pk>\d+)/$', FlightDelete.as_view(), name='flight_delete'),
    url(r'^logbook/remarks$', RemarksList.as_view(), name='remarks'),


    url(r'^aircraft/$', AircraftList.as_view(), name='aircraft_list'),
    url(r'^aircraft/create', AircraftCreate.as_view(), name='aircraft_create'),
    url(r'^aircraft/update/(?P<pk>\d+)/$', AircraftUpdate.as_view(), name='aircraft_update'),
    url(r'^aircraft/detail/(?P<pk>\d+)/$', AircraftDetail.as_view(), name='aircraft_detail'),
    url(r'^aircraft/delete/(?P<pk>\d+)/$', AircraftDelete.as_view(), name='aircraft_delete'),

    url(r'^approaches/$', ApproachList.as_view(), name='approach_list'),
    url(r'^approaches/create/$', ApproachCreate.as_view(), name='approach_create'),
    url(r'^approaches/update/(?P<pk>\d+)/$', ApproachUpdate.as_view(), name='approach_update'),
    url(r'^approaches/detail/(?P<pk>\d+)/$', ApproachDetail.as_view(), name='approach_detail'),
    url(r'^approaches/delete/(?P<pk>\d+)/$', ApproachDelete.as_view(), name='approach_delete'),

    url(r'^tailnumbers/$', TailNumberList.as_view(), name='tailnumber_list'),
    url(r'^tailnumbers/create/$', TailNumberCreate.as_view(), name='tailnumber_create'),
    url(r'^tailnumbers/update/(?P<pk>\d+)/$', TailNumberUpdate.as_view(), name='tailnumber_update'),
    url(r'^tailnumbers/detail/(?P<pk>\d+)/$', TailNumberDetail.as_view(), name='tailnumber_detail'),
    url(r'^tailnumbers/delete/(?P<pk>\d+)/$', TailNumberDelete.as_view(), name='tailnumber_delete'),

]
