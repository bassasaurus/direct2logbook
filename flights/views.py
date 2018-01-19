from flights.models import *
from django.contrib.auth.models import User, Group


from flights.forms import *
from django.db.models import Sum, Q

from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView
from django.views.generic.dates import YearArchiveView, MonthArchiveView, ArchiveIndexView, DayArchiveView
from django.contrib.auth.mixins import LoginRequiredMixin

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
import json
from django.views.decorators.cache import cache_page
from django.core.cache import cache

from dal import autocomplete

from django.core.paginator import Paginator

from flights.get_map_data import get_map_data
import flights.currency as currency
from flights.errors import *

class UserObjectsMixin():

    def get_queryset(self):
        user = self.request.user
        return super(UserObjectsMixin, self).get_queryset().filter(user=user)

class LoginRequiredMixin(LoginRequiredMixin):
    login_url = '/accounts/login'
    # redirect_field_name = None


def geoJSON_airports_view(request):
    if request.method == 'GET':

        data = cache.get('airports')

        # return HttpResponse(data, content_type='text/html')
        return JsonResponse(data, content_type='application/json', safe=False)

def geoJSON_routes_view(request):
    if request.method == 'GET':

        data = cache.get('routes')
        return HttpResponse(data, content_type='text/html')

class AircraftAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):

    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated():
            return Aircraft.objects.none()

        user = self.request.user
        qs = Aircraft.objects.filter(user=user)

        if self.q:
            qs = qs.filter(aircraft_type__istartswith=self.q)

        return qs

class TailNumberAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):

    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated():
            return TailNumber.objects.none()

        user = self.request.user
        qs = TailNumber.objects.filter(user=user)

        if self.q:
            qs = qs.filter(registration__istartswith=self.q)

        return qs

class SplashScreen(TemplateView):
    template_name = 'index.html'

class HomeView(LoginRequiredMixin, UserObjectsMixin, TemplateView):
    template_name='home.html'

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)

        context['asel_total'] = Total.objects.get(total="ASEL")
        context['amel_total'] = Total.objects.get(total="AMEL")
        context['ases_total'] = Total.objects.get(total="ASES")
        context['ames_total'] = Total.objects.get(total="AMES")
        context['helo_total'] = Total.objects.get(total="HELO")
        context['gyro_total'] = Total.objects.get(total="GYRO")

        context['amel_vfr_night'] = currency.amel_vfr_night()
        context['amel_vfr_day'] = currency.amel_vfr_day()
        context['asel_vfr_night'] = currency.asel_vfr_night()
        context['asel_vfr_day'] = currency.asel_vfr_day()
        context['ases_vfr_day'] = currency.ases_vfr_day()
        context['ases_vfr_night'] = currency.ases_vfr_night()
        context['ames_vfr_day'] = currency.ames_vfr_day()
        context['ames_vfr_night'] = currency.ames_vfr_night()
        context['helo_vfr_day'] = currency.asel_vfr_day()
        context['helo_vfr_night'] = currency.helo_vfr_night()
        context['gyro_vfr_day'] = currency.gyro_vfr_day()
        context['gyro_vfr_night'] = currency.gyro_vfr_night()

        context['totals'] = Total.objects.exclude(total_time__lte=.1)
        context['stats'] = Stat.objects.exclude(total_time__lte=.1)
        context['regs'] = Regs.objects.all()
        context['weights'] = Weight.objects.exclude(total__lte=.1)
        context['powers'] = Power.objects.all()
        context['endorsements'] = Endorsement.objects.exclude(total__lte=.1)
        context['title'] = 'D-> | Home'
        context['page_title'] = "Home"
        return context

class FlightErrorView(LoginRequiredMixin, UserObjectsMixin, TemplateView):

    def get(self, request):
        user = self.request.user

        return render(request, 'flights/flight_errors.html', {
            'map_duplicate_error':  map_duplicate_error(Flight.objects.filter(user=user).values_list('route', flat=True)),
            'map_identifier_error': map_identifier_error(Flight.objects.filter(user=user).values_list('route', flat=True)),
            'flight_aircraft_error':flight_aircraft_error(Flight.objects.filter(user=user)),
            'flight_tailnumber_error':flight_tailnumber_error(Flight.objects.filter(user=user)),
            'flight_role_error':flight_role_error(Flight.objects.filter(user=user)),
            'flight_cross_country_error':flight_cross_country_error(Flight.objects.filter(user=user)),
            'title': "D-> | Logbook Errors",
            'page_title': "Logbook Errors"
            })

class AircraftErrorView(LoginRequiredMixin, UserObjectsMixin, TemplateView):

    def get(self, request):
        user = self.request.user

        return render(request, 'aircraft/aircraft_errors.html', {
            'tailnumber_reg_error': tailnumber_reg_error(TailNumber.objects.filter(user=user)),
            'tailnumber_aircraft_error':tailnumber_aircraft_error(TailNumber.objects.filter(user=user)),
            'aircraft_power_error':aircraft_power_error(Aircraft.objects.filter(user=user)),
            'aircraft_weight_error':aircraft_weight_error(Aircraft.objects.filter(user=user)),
            'aircraft_endorsement_error':aircraft_endorsement_error(Aircraft.objects.filter(user=user)),
            'aircraft_category_error':aircraft_category_error(Aircraft.objects.filter(user=user)),
            'aircraft_class_error':aircraft_class_error(Aircraft.objects.filter(user=user)),
            'title': "D-> | Aircraft Errors",
            'page_title': "Aircraft Errors"
            })

class FlightArchive(LoginRequiredMixin, UserObjectsMixin, ArchiveIndexView):
    model = Flight
    date_field = 'date'
    make_object_list = True
    allow_empty = True
    allow_future = False

    def get_context_data(self, **kwargs):
        context = super(FlightArchive, self).get_context_data(**kwargs)
        get_map_data(self.object_list)
        context['title'] = "D-> | Map"
        context['page_title'] = 'Map'
        return context

class FlightArchiveYear(LoginRequiredMixin, UserObjectsMixin, YearArchiveView):
    model = Flight
    date_field = 'date'
    make_object_list = True
    allow_empty = False #ok since url can't be used until ArchiveIndexView is populated
    allow_future = False

    def get_context_data(self, **kwargs):
        context = super(FlightArchiveYear, self).get_context_data(**kwargs)
        get_map_data(self.object_list)
        context['title'] = "D-> | Flights by Year"
        context['page_title'] = "Flights by Year"
        return context

class FlightArchiveMonth(LoginRequiredMixin, UserObjectsMixin, MonthArchiveView):
    model = Flight
    date_field = 'date'
    make_object_list = True
    allow_empty = False #ok since url can't be used until ArchiveIndexView is populated
    allow_future = False

    def get_context_data(self, **kwargs):
        context = super(FlightArchiveMonth, self).get_context_data(**kwargs)
        get_map_data(self.object_list)
        context['title'] = "D-> | Flights by Month"
        context['page_title'] = "Flights by Month"
        return context

# class FlightArchiveDay(LoginRequiredMixin, UserObjectsMixin, DayArchiveView):
# 	queryset = Flight.objects.all()
# 	date_field = 'date'
# 	allow_future = False
#     year = '2017'

#-------------------Flight CRUD-------------------------

class FlightList(LoginRequiredMixin, UserObjectsMixin, ListView):
    model = Flight
    template_name = "flight_list.html"
    paginate_by = 40

    def get_context_data(self, **kwargs):
        context = super(FlightList, self).get_context_data(**kwargs)

        context['title'] = "D-> | Logbook"
        context['page_title'] = "Logbook"
        return context

class FlightCreate(LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = Flight
    form_class = FlightForm
    # aircraft_form = AircraftForm
    # tailnumber_form = TailNumberForm
    template_name = 'flights/flight_create_form.html'
    success_url = '/logbook/'

    def get_context_data(self, **kwargs):
        context = super(FlightCreate, self).get_context_data(**kwargs)

        if FlightForm not in context:
            context['flight_form'] = self.form_class()
        # if AircraftForm not in context:
        #     context['aircraft_form'] = self.aircraft_form()
        # if TailNumberForm not in context:
        #     context['tailnumber_form'] = self.tailnumber_form()

        context['title'] = "D-> | New Flight"
        context['page_title'] = "New Flight"
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context

class FlightUpdate(LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = Flight
    form_class = FlightForm

    template_name = 'flights/flight_update_form.html'
    success_url = '/logbook/'

    def get_context_data(self, **kwargs):
        context = super(FlightUpdate, self).get_context_data(**kwargs)
        context['title'] = "D-> | Update Flight"
        context['page_title'] = "Update Flight"
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context

class FlightDetail(LoginRequiredMixin, UserObjectsMixin, DetailView):
    model = Flight
    template_name = 'flights/flight_detail.html'

    def get_context_data(self, **kwargs):
        context = super(FlightDetail, self).get_context_data(**kwargs)
        queryset = Flight.objects.filter(pk=self.object.pk)
        get_map_data(queryset)
        context['title'] = "D-> | Flight Detail"
        context['page_title'] = "Detail"
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context

class FlightDelete(LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = Flight
    template_name = 'flights/flight_delete.html'
    success_url = '/logbook/'

    def get_context_data(self, **kwargs):
        context = super(FlightDelete, self).get_context_data(**kwargs)
        context['title'] = "D-> | Delete Flight"
        context['page_title'] = "Delete"
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context

#-------------------Aircraft CRUD-----------------------

class AircraftList(LoginRequiredMixin, UserObjectsMixin, ListView):
    model = Aircraft
    template_name = "aircraft/aircraft_list.html"
    aircraft_form = AircraftForm

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super(AircraftList, self).get_context_data(**kwargs)

        if AircraftForm not in context:
            context['aircraft_form'] = self.aircraft_form()

        context['title'] = "D-> | Aircraft"
        context['page_title'] = "Aircraft"
        return context

class AircraftCreate(LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = Aircraft
    form_class = AircraftForm
    template_name = "aircraft/aircraft_create_form.html"
    success_url = "/aircraft/"

    def get_context_data(self, **kwargs):
        context = super(AircraftCreate, self).get_context_data(**kwargs)
        context['title'] = "D-> | New Aircraft"
        context['page_title'] = "New Aircraft"
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

# class AircraftCreateModal(LoginRequiredMixin, CreateView):
#     model = Aircraft
#     form_class = AircraftForm
#     template_name = "aircraft/aircraft_create_form_modal.html"
#     success_url = ""

class AircraftUpdate(LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = Aircraft
    form_class = AircraftForm
    template_name = 'aircraft/aircraft_update_form.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super(AircraftUpdate, self).get_context_data(**kwargs)
        context['title'] = "D-> | Update " + str(self.object)
        context['page_title'] = "Update " + str(self.object)
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

class AircraftDetail(LoginRequiredMixin, UserObjectsMixin, DetailView):
    model = Aircraft
    form = TailNumberForm
    template_name = 'aircraft/aircraft_detail.html'

    def get_context_data(self, **kwargs):
        context = super(AircraftDetail, self).get_context_data(**kwargs)
        context['tailnumbers'] = TailNumber.objects.all().filter(aircraft = self.object )

        if TailNumberForm not in context:
            context['form'] = self.form()

        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = str(self.object)
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

class AircraftDelete(LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = Aircraft
    template_name = 'aircraft/aircraft_delete.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super(AircraftDelete, self).get_context_data(**kwargs)
        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = "Delete " + str(self.object)
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

#-------------------Approach CRUD-----------------------

class ApproachList(LoginRequiredMixin, ListView):
    model = Approach
    template_name = "approaches/approach_list.html"

    def get_context_data(self, **kwargs):
        context = super(ApproachList, self).get_context_data(**kwargs)
        context['title'] = "D-> | Approach Types"
        return context

class ApproachCreate(LoginRequiredMixin, CreateView):
    model = Approach
    form_class = ApproachForm
    template_name = "approaches/approach_create_form.html"

    def get_context_data(self, **kwargs):
        context = super(ApproachCreate, self).get_context_data(**kwargs)
        context['title'] = "D-> | New Approach Type"
        return context

class ApproachUpdate(LoginRequiredMixin, UpdateView):
    model = Approach
    form_class = ApproachForm
    template_name = 'approaches/approach_update_form.html'
    success_url = '/approaches'

    def get_context_data(self, **kwargs):
        context = super(ApproachUpdate, self).get_context_data(**kwargs)
        context['title'] = "D-> | Rename Approach"
        return context

class ApproachDetail(LoginRequiredMixin, DetailView):
    model = Approach
    template_name = 'approaches/approach_detail.html'

    def get_context_data(self, **kwargs):
        context = super(ApproachDetail, self).get_context_data(**kwargs)

        context['title'] = "D-> | Approach Detail"
        return context

class ApproachDelete(LoginRequiredMixin, DeleteView):
    model = Approach
    template_name = 'approaches/approach_delete.html'
    success_url = '/approaches'

    def get_context_data(self, **kwargs):
        context = super(ApproachDelete, self).get_context_data(**kwargs)
        context['title'] = "D-> | Delete Approach Type"
        return context

#------------------TailNumber CRUD----------------------

class TailNumberList(LoginRequiredMixin, UserObjectsMixin, ListView):
    model = TailNumber
    template_name = "tailnumbers/tailnumber_list.html"
    paginate_by = 120
    context_object_name = 'Tail Numbers'

    def get_context_data(self, **kwargs):
        context = super(TailNumberList, self).get_context_data(**kwargs)
        context['title'] = "D-> | Tailnumbers"
        context['page_title'] = "Tailnumbers"
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

class TailNumberCreate(LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = TailNumber
    form_class = TailNumberForm
    template_name = "tailnumbers/tailnumber_create_form.html"
    success_url = "/aircraft/"

    def get_context_data(self, **kwargs):
        context = super(TailNumberCreate, self).get_context_data(**kwargs)
        context['title'] = "D-> | New TailNumber"
        context['page_title'] = "New Tailnumber"
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

class TailNumberUpdate(LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = TailNumber
    form_class = TailNumberForm
    template_name = 'tailnumbers/tailnumber_update_form.html'
    success_url = '/home/'

    def get_context_data(self, **kwargs):
        context = super(TailNumberUpdate, self).get_context_data(**kwargs)
        context['title'] = "D-> | Update " + str(self.object)
        context['page_title'] = "Update " + str(self.object)
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

class TailNumberDetail(LoginRequiredMixin, UserObjectsMixin, DetailView):
    model = TailNumber
    template_name = 'tailnumbers/tailnumber_detail.html'

    def get_context_data(self, **kwargs):
        tailnumber = self.object
        flights = Flight.objects.all().filter(registration = self.object)
        get_map_data(flights)
        context = super(TailNumberDetail, self).get_context_data(**kwargs)
        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = str(self.object)
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        context['child_name'] = tailnumber.aircraft
        context['child_link'] = reverse('aircraft_detail', args = [self.object.aircraft.pk])
        context['flights'] = flights
        return context

class TailNumberDelete(LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = TailNumber
    template_name = 'tailnumbers/tailnumber_delete.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super(TailNumberDelete, self).get_context_data(**kwargs)
        context['title'] = "D-> | Delete " + str(self.object)
        context['page_title'] = "Delete " + str(self.object)
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context
