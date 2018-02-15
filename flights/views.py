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
import datetime
from django.core.paginator import Paginator

from flights.get_map_data import get_map_data
import flights.currency as currency

zulu_time = datetime.datetime.now().strftime('%Y %b %d %H:%M') + " UTC"

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

class ProfileView(LoginRequiredMixin, UserObjectsMixin, TemplateView):
    model = Profile
    template_name='profile/profile.html'

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Profile"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = 'Profile'
        return context


class ProfileUpdateView(LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = Profile
    fields = ()

    template_name = 'profile/profile_update.html'
    success_url = '/profile/'

    def get_context_data(self, **kwargs):
        context = super(ProfileUpdateView, self).get_context_data(**kwargs)

        profile_form = ProfileForm()
        user_form = UserForm()
        context['zulu_time'] = zulu_time
        context['profile_form'] = profile_form
        context['user_form'] = user_form
        context['title'] = "D-> | Update Profile"
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Profile'
        return context

class HomeView(LoginRequiredMixin, UserObjectsMixin, TemplateView):
    template_name='home.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super(HomeView, self).get_context_data(**kwargs)

        context['last_ten'] = Flight.objects.filter(user=user).order_by('-id')[:5]

        if not Total.objects.filter(user=user):
            context['asel_total'] = 0
        else:
            context['asel_total'] = Total.objects.filter(user=user).get(total="ASEL")

        if not Total.objects.filter(user=user):
            context['amel_total'] = 0
        else:
            context['amel_total'] = Total.objects.filter(user=user).get(total="AMEL")
            amel = Total.objects.filter(user=user).get(total="AMEL")

        if not Total.objects.filter(user=user):
            context['ases_total'] = 0
        else:
            context['ases_total'] = Total.objects.filter(user=user).get(total="ASES")

        if not Total.objects.filter(user=user):
            context['ames_total'] = 0
        else:
            context['ames_total'] = Total.objects.filter(user=user).get(total="AMES")

        if not Total.objects.filter(user=user):
            context['helo_total'] = 0
        else:
            context['helo_total'] = Total.objects.filter(user=user).get(total="HELO")

        if not Total.objects.filter(user=user):
            context['gyro_total'] = 0
        else:
            context['gyro_total'] = Total.objects.filter(user=user).get(total="GYRO")

        context['zulu_time'] = zulu_time

        context['amel_vfr_night'] = currency.amel_vfr_night(user)
        context['amel_vfr_day'] = currency.amel_vfr_day(user)
        context['asel_vfr_night'] = currency.asel_vfr_night(user)
        context['asel_vfr_day'] = currency.asel_vfr_day(user)
        context['ases_vfr_day'] = currency.ases_vfr_day(user)
        context['ases_vfr_night'] = currency.ases_vfr_night(user)
        context['ames_vfr_day'] = currency.ames_vfr_day(user)
        context['ames_vfr_night'] = currency.ames_vfr_night(user)
        context['helo_vfr_day'] = currency.asel_vfr_day(user)
        context['helo_vfr_night'] = currency.helo_vfr_night(user)
        context['gyro_vfr_day'] = currency.gyro_vfr_day(user)
        context['gyro_vfr_night'] = currency.gyro_vfr_night(user)

        context['totals'] = Total.objects.filter(user=user).exclude(total_time__lte=.1)
        context['stats'] = Stat.objects.filter(user=user).exclude(total_time__lte=.1)
        context['regs'] = Regs.objects.filter(user=user).all()
        context['weights'] = Weight.objects.filter(user=user).exclude(total__lte=.1)
        context['powers'] = Power.objects.filter(user=user).all()
        context['endorsements'] = Endorsement.objects.exclude(total__lte=.1)
        context['title'] = 'D-> | Home'
        context['page_title'] = "Home"
        return context

class FlightArchive(LoginRequiredMixin, UserObjectsMixin, ArchiveIndexView):
    model = Flight
    date_field = 'date'
    make_object_list = True
    allow_empty = True
    allow_future = False

    def get_context_data(self, **kwargs):
        context = super(FlightArchive, self).get_context_data(**kwargs)
        get_map_data(self.object_list)
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Map"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Flights by Year"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Map'
        context['parent_link'] = reverse('flight_by_date')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Flights by Month"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Map'
        context['parent_link'] = reverse('flight_by_date')
        context['page_title'] = "Flights by Month"
        return context

# class FlightArchiveDay(LoginRequiredMixin, UserObjectsMixin, DayArchiveView):
# 	queryset = Flight.objects.all()
# 	date_field = 'date'
# 	allow_future = False
#     year = '2017'

#-------------------Flight CRUD-------------------------

class RemarksList(LoginRequiredMixin, UserObjectsMixin, ListView):
    model = Flight
    template_name = "flights/remarks.html"
    paginate_by = 40

    def get_context_data(self, **kwargs):
        context = super(RemarksList, self).get_context_data(**kwargs)
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Remarks"
        context['page_title'] = "Remarks"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context

class FlightList(LoginRequiredMixin, UserObjectsMixin, ListView):
    model = Flight
    template_name = "flight_list.html"
    paginate_by = 40

    def get_context_data(self, **kwargs):
        context = super(FlightList, self).get_context_data(**kwargs)

        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Logbook"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = "Logbook"
        return context

class FlightCreate(LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = Flight
    form_class = FlightForm
    # aircraft_form = AircraftForm
    form = TailNumberForm
    template_name = 'flights/flight_create_form.html'
    success_url = '/logbook/'

    def get_context_data(self, **kwargs):
        context = super(FlightCreate, self).get_context_data(**kwargs)

        context['flight_form'] = self.form_class()

        context['form'] = self.form()

        context['zulu_time'] = zulu_time

        context['title'] = "D-> | New Flight"
        context['page_title'] = "New Flight"
        context['home_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Update Flight"
        context['page_title'] = "Update Flight"
        context['home_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Flight Detail"
        context['page_title'] = "Detail"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context

class FlightDelete(LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = Flight
    template_name = 'flights/flight_delete.html'
    success_url = '/logbook/'

    def get_context_data(self, **kwargs):
        context = super(FlightDelete, self).get_context_data(**kwargs)
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Delete Flight"
        context['page_title'] = "Delete"
        context['home_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Aircraft"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = "Aircraft"
        return context

class AircraftCreate(LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = Aircraft
    form_class = AircraftForm
    template_name = "aircraft/aircraft_create_form.html"
    success_url = "/aircraft/"

    def get_context_data(self, **kwargs):
        context = super(AircraftCreate, self).get_context_data(**kwargs)
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | New Aircraft"

        context['home_link'] = reverse('home')
        context['page_title'] = "New Aircraft"
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

class AircraftUpdate(LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = Aircraft
    form_class = AircraftForm
    template_name = 'aircraft/aircraft_update_form.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super(AircraftUpdate, self).get_context_data(**kwargs)
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Update " + str(self.object)
        context['page_title'] = "Update " + str(self.object)
        context['home_link'] = reverse('home')
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


        context['form'] = self.form()

        context['zulu_time'] = zulu_time
        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context

class AircraftDelete(LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = Aircraft
    template_name = 'aircraft/aircraft_delete.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super(AircraftDelete, self).get_context_data(**kwargs)
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = "Delete " + str(self.object)
        context['home_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Tailnumbers"
        context['page_title'] = "Tailnumbers"
        context['home_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | New TailNumber"
        context['page_title'] = "New Tailnumber"
        context['home_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Update " + str(self.object)
        context['page_title'] = "Update " + str(self.object)
        context['home_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = str(self.object)
        context['home_link'] = reverse('home')
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
        context['zulu_time'] = zulu_time
        context['title'] = "D-> | Delete " + str(self.object)
        context['page_title'] = "Delete " + str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context
