from flights.models import *
from accounts.models import Profile
from django.contrib.auth.models import User, Group

from flights.forms import *
from django.db.models import Sum, Q, F
from django.db.models.functions import Length
from django.db.models import CharField

from django.db import transaction
from django.contrib.admin.utils import NestedObjects
from django.utils.text import capfirst

from django.forms import inlineformset_factory

from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView
from django.views.generic.dates import YearArchiveView, MonthArchiveView, ArchiveIndexView, DayArchiveView, DayMixin
from django.contrib.auth.mixins import LoginRequiredMixin

from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
import json
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from dal import autocomplete
import datetime
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from flights.get_map_data import get_map_data
import flights.currency as currency

from django.contrib.auth.mixins import UserPassesTestMixin

CharField.register_lookup(Length, 'length')

zulu_time = datetime.datetime.now().strftime('%Y %b %d %H:%M') + " UTC"


def get_deleted_objects(objs):
    collector = NestedObjects(using='default')
    collector.collect(objs)

    def format_callback(obj):
        opts = obj._meta
        no_edit_link = '%s: %s' % (capfirst(opts.verbose_name),
                                   force_text(obj))
        return no_edit_link

    to_delete = collector.nested(format_callback)[1:]
    protected = [format_callback(obj) for obj in collector.protected]
    model_count = {model._meta.verbose_name_plural: len(
        objs) for model, objs in collector.model_objs.items()}

    return to_delete, model_count, protected


def error_404(request, exception):
    context = {
        'title': '404',
        'home_link': reverse('home')
    }
    return render(request, 'error_404.html', context)


def error_500(request):
    context = {
        'title': '500',
        'home_link': reverse('home')
    }
    return render(request, 'error_500.html', context)


def error_403(request, exception):
    context = {
        'title': '403',
        'home_link': reverse('home')
    }
    return render(request, 'error_403.html', context)


class ProfileNotActiveMixin(UserPassesTestMixin):

    def test_func(self):
        today = datetime.datetime.now()
        profile = Profile.objects.get(user=self.request.user)

        if profile.end_date > today.date():
            expired=False
        else:
            expired=True

        if profile.active or profile.trial:
            return True
        elif profile.canceled and expired==False:
            return True
        else:
            return False

    def handle_no_permission(self):
        return redirect('profile')

class UserObjectsMixin():

    def get_queryset(self):
        user = self.request.user
        return super(UserObjectsMixin, self).get_queryset().filter(user=user)

class LoginRequiredMixin(LoginRequiredMixin):
    login_url = '/accounts/login'
    # redirect_field_name = None


def geoJSON_airports_view(request, user_id):
    if request.method == 'GET':
        user = request.user

        user_cache = 'airports_{}'.format(user.id)
        data = cache.get(user_cache)
        return JsonResponse(data, content_type='application/json', safe=False)


def geoJSON_routes_view(request, user_id):
    if request.method == 'GET':
        user = request.user

        user_cache = 'routes_{}'.format(user.id)
        data = cache.get(user_cache)
        return HttpResponse(data, content_type='text/html')


class AircraftAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):

    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Aircraft.objects.none()

        user = self.request.user
        qs = Aircraft.objects.filter(user=user)

        if self.q:
            qs = qs.filter(aircraft_type__istartswith=self.q)
        return qs


class TailNumberAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):

    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return TailNumber.objects.none()

        user = self.request.user
        qs = TailNumber.objects.filter(user=user)

        aircraft_type = self.forwarded.get('aircraft_type', None)

        if aircraft_type:
            qs = qs.filter(aircraft=aircraft_type)

        if self.q:
            qs = qs.filter(registration__istartswith=self.q)

        return qs


def index_view(request):
    context = {
        'title': 'D-> | Direct2Logbook'
    }
    if request.user.is_authenticated:
        return redirect('home')
    else:
        return render(request, 'index.html', context)


class HomeView(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super(HomeView, self).get_context_data(**kwargs)

        context['recent'] = Flight.objects.filter(
            user=user).order_by('-id')[:8]

        flight_error_query = Q(map_error__length__gt=0) | Q(duplicate_error__length__gt=0) | Q(
            aircraft_type_error__length__gt=0) | Q(registration_error__length__gt=0) | Q(crew_error__length__gt=0)
        context['flight_errors'] = Flight.objects.filter(
            user=user).filter(flight_error_query)

        aircraft_error_query = Q(config_error__length__gt=0) | Q(power_error__length__gt=0) | Q(
            weight_error__length__gt=0) | Q(category_error__length__gt=0) | Q(class_error__length__gt=0)
        context['aircraft_errors'] = Aircraft.objects.filter(
            user=user).filter(aircraft_error_query)

        tailnumber_error_query = Q(reg_error__length__gt=0)
        context['tailnumber_errors'] = TailNumber.objects.filter(
            user=user).filter(tailnumber_error_query)
        for tail in TailNumber.objects.filter(user=user).filter(tailnumber_error_query):
            print(tail, len(tail.reg_error))

        aircraft_list = []
        for aircraft in Aircraft.objects.filter(user=user).all():
            if TailNumber.objects.filter(user=user).filter(aircraft__aircraft_type=aircraft).exists():
                pass
            else:
                aircraft_list.append(aircraft)
                context['aircraft_needs_tailnumber'] = aircraft_list

        # cat/class vfr day, night currency
        if not Total.objects.filter(user=user):
            context['asel_total'] = 0
        else:
            context['asel_total'] = Total.objects.filter(
                user=user).get(total="ASEL")
            asel_total = Total.objects.filter(user=user).get(total="ASEL")

        if not Total.objects.filter(user=user):
            context['amel_total'] = 0
        else:
            context['amel_total'] = Total.objects.filter(
                user=user).get(total="AMEL")

        if not Total.objects.filter(user=user):
            context['ases_total'] = 0
        else:
            context['ases_total'] = Total.objects.filter(
                user=user).get(total="ASES")

        if not Total.objects.filter(user=user):
            context['ames_total'] = 0
        else:
            context['ames_total'] = Total.objects.filter(
                user=user).get(total="AMES")

        if not Total.objects.filter(user=user):
            context['helo_total'] = 0
        else:
            context['helo_total'] = Total.objects.filter(
                user=user).get(total="HELO")

        if not Total.objects.filter(user=user):
            context['gyro_total'] = 0
        else:
            context['gyro_total'] = Total.objects.filter(
                user=user).get(total="GYRO")

        # IFR currency
        today = datetime.date.today()
        last_180 = today - datetime.timedelta(days=180)

        appr_qs = Flight.objects.filter(user=user).filter(date__lte=today, date__gte=last_180).filter(
            approach__number__gte=0).aggregate(Sum(F('approach__number')))
        if not appr_qs:
            context['appr_quantity'] = 0
        else:
            context['appr_quantity'] = appr_qs.get(
                'approach__number__sum')  # Model__field__SumFunctionValue
            # context['still_needed'] = 6 - int(appr_qs.get('approach__number__sum'))

        oldest_approach_date = Flight.objects.filter(user=user).filter(
            date__lte=today, date__gte=last_180).filter(approach__number__gte=0).first()
        if not oldest_approach_date:
            context['appr_current_date'] = None
        else:
            context['appr_current_date'] = oldest_approach_date.date + \
                datetime.timedelta(180)

        hold_qs = Flight.objects.filter(user=user).filter(
            date__lte=today, date__gte=last_180).filter(holding__hold=True)
        if not hold_qs:
            context['hold_quantity'] = 0
        else:
            context['hold_quantity'] = 1

        hold_date_qs = Flight.objects.filter(user=user).filter(
            date__lte=today, date__gte=last_180).filter(holding__hold=True).last()
        if not hold_date_qs:
            context['hold_current_date'] = None
        else:
            context['hold_current_date'] = hold_date_qs.date + \
                datetime.timedelta(180)

        context['amel_vfr_day'] = currency.amel_vfr_day(user)[0]
        context['amel_vfr_day_current'] = currency.amel_vfr_day(user)[1]
        context['amel_vfr_night'] = currency.amel_vfr_night(user)[0]
        context['amel_vfr_night_current'] = currency.amel_vfr_night(user)[1]

        context['asel_vfr_day'] = currency.asel_vfr_day(user)[0]
        context['asel_vfr_day_current'] = currency.asel_vfr_day(user)[1]
        context['asel_vfr_night'] = currency.asel_vfr_night(user)[0]
        context['asel_vfr_night_current'] = currency.asel_vfr_night(user)[1]

        context['ases_vfr_day'] = currency.ases_vfr_day(user)[0]
        context['ases_vfr_day_current'] = currency.ases_vfr_day(user)[1]
        context['ases_vfr_night'] = currency.ases_vfr_night(user)[0]
        context['ases_vfr_night_current'] = currency.ases_vfr_night(user)[1]

        context['ames_vfr_day'] = currency.ames_vfr_day(user)[0]
        context['ames_vfr_day_current'] = currency.ames_vfr_day(user)[1]
        context['ames_vfr_night'] = currency.ames_vfr_night(user)[0]
        context['ames_vfr_night_current'] = currency.ames_vfr_night(user)[1]

        context['helo_vfr_day'] = currency.helo_vfr_day(user)[0]
        context['helo_vfr_day_current'] = currency.helo_vfr_day(user)[1]
        context['helo_vfr_night'] = currency.helo_vfr_night(user)[0]
        context['helo_vfr_night_current'] = currency.helo_vfr_night(user)[1]

        context['gyro_vfr_day'] = currency.gyro_vfr_day(user)[0]
        context['gyro_vfr_day_current'] = currency.gyro_vfr_day(user)[1]
        context['gyro_vfr_night'] = currency.gyro_vfr_night(user)[0]
        context['gyro_vfr_night_current'] = currency.gyro_vfr_night(user)[1]

        context['expiry_date'] = currency.medical_duration(user)[0]
        context['this_month'] = currency.medical_duration(user)[1]

        if len(Aircraft.objects.filter(user=user).all()) == 0:
            context['new_user_aircraft'] = True
        else:
            context['new_user_aircraft'] = False

        if len(TailNumber.objects.filter(user=user).all()) == 0:
            context['new_user_tailnumber'] = True
        else:
            context['new_user_tailnumber'] = False

        if len(Flight.objects.filter(user=user).all()) == 0:
            context['new_user_flight'] = True
        else:
            context['new_user_flight'] = False

        context['totals'] = Total.objects.filter(
            user=user).exclude(total_time__lte=.1)
        context['stats'] = Stat.objects.filter(user=user)
        context['regs'] = Regs.objects.filter(user=user).all()
        context['weights'] = Weight.objects.filter(
            user=user).exclude(total__lte=.1)
        context['powers'] = Power.objects.filter(user=user).all()
        context['endorsements'] = Endorsement.objects.filter(
            user=user).exclude(total__lte=.1)
        context['title'] = 'D-> | Home'
        context['page_title'] = "Home"
        return context


class FlightArchive(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, ArchiveIndexView):
    model = Flight
    date_field = 'date'
    make_object_list = True
    allow_empty = True
    allow_future = False

    def get_context_data(self, **kwargs):
        context = super(FlightArchive, self).get_context_data(**kwargs)
        user = self.request.user
        get_map_data(self.object_list, user)

        context['title'] = "D-> | Map"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = 'Map'
        context['years'] = Flight.objects.filter(
            user=user).dates('date', 'year')
        context['months'] = Flight.objects.filter(
            user=user).dates('date', 'month')
        return context


class FlightArchiveYear(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, YearArchiveView):
    model = Flight
    date_field = 'date'
    make_object_list = True
    allow_empty = False  # ok since url can't be used until ArchiveIndexView is populated
    allow_future = False

    def get_context_data(self, **kwargs):
        context = super(FlightArchiveYear, self).get_context_data(**kwargs)
        user = self.request.user
        get_map_data(self.object_list, user)

        context['title'] = "D-> | Flights by Year"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Map'
        context['parent_link'] = reverse('flight_by_date')
        context['page_title'] = "Flights by Year"
        context['years'] = Flight.objects.filter(
            user=user).dates('date', 'year')
        return context


class FlightArchiveMonth(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, MonthArchiveView):
    model = Flight
    date_field = 'date'
    make_object_list = True
    allow_empty = False  # ok since url can't be used until ArchiveIndexView is populated
    allow_future = False

    def get_context_data(self, **kwargs):
        context = super(FlightArchiveMonth, self).get_context_data(**kwargs)
        user = self.request.user
        get_map_data(self.object_list, user)

        context['title'] = "D-> | Flights by Month"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Map'
        context['parent_link'] = reverse('flight_by_date')
        context['page_title'] = "Flights by Month"
        context['years'] = Flight.objects.filter(
            user=user).dates('date', 'year')
        context['months'] = Flight.objects.filter(
            user=user).dates('date', 'month')
        return context

# class FlightArchiveDay(LoginRequiredMixin, UserObjectsMixin, DayArchiveView):
# 	queryset = Flight.objects.all()
# 	date_field = 'date'
# 	allow_future = False

# -------------------Flight CRUD-------------------------


class RemarksList(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, ListView):
    model = Flight
    template_name = "flights/remarks.html"
    pagninate_by = 30

    def get_context_data(self, **kwargs):
        context = super(RemarksList, self).get_context_data(**kwargs)

        context['title'] = "D-> | Remarks"
        context['page_title'] = "Remarks"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context


class FlightList(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, ListView):
    model = Flight
    template_name = "flight_list.html"
    paginate_by = 40

    def get_queryset(self):
        return Flight.objects.filter(user=self.request.user).order_by('-date')

    def get_context_data(self, **kwargs):
        context = super(FlightList, self).get_context_data(**kwargs)

        context['title'] = "D-> | Logbook"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = "Logbook"
        return context


class FlightCreate(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = Flight
    form_class = FlightForm
    template_name = 'flights/flight_create_form.html'

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests and instantiates blank versions of the form
        and its inline formsets.
        """
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        approach_form = ApproachFormSet()
        holding_form = HoldingFormSet()
        return self.render_to_response(
            self.get_context_data(form=form,
                                  approaches=approach_form,
                                  holding=holding_form))

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a form instance and its inline
        formsets with the passed POST variables and then checking them for
        validity.
        """
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        approach_form = ApproachFormSet(self.request.POST)
        holding_form = HoldingFormSet(self.request.POST)
        if (form.is_valid() and approach_form.is_valid() and
                holding_form.is_valid()):
            return self.form_valid(form, approach_form, holding_form)
        else:
            return self.form_invalid(form, approach_form, holding_form)

    def form_valid(self, form, approach_form, holding_form):
        """
        Called if all forms are valid. Creates a Recipe instance along with
        associated Ingredients and Instructions and then redirects to a
        success page.
        """
        form.instance.user = self.request.user
        self.object = form.save()
        approach_form.instance = self.object
        approach_form.save()
        holding_form.instance = self.object
        holding_form.save()
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, approach_form, holding_form):
        """
        Called if a form is invalid. Re-renders the context data with the
        data-filled forms and errors.
        """
        return self.render_to_response(
            self.get_context_data(form=form,
                                  approaches=approach_form,
                                  holding=holding_form))

    def get_context_data(self, **kwargs):
        context = super(FlightCreate, self).get_context_data(**kwargs)

        context['title'] = "D-> | New Flight"
        context['parent_name'] = 'Logbook'
        context['parent_link'] = reverse('flight_list')
        context['home_link'] = reverse('home')
        context['page_title'] = "New Flight"
        return context


class FlightUpdate(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = Flight
    form_class = FlightForm
    template_name = 'flights/flight_update_form.html'

    def get_context_data(self, **kwargs):
        context = super(FlightUpdate, self).get_context_data(**kwargs)
        ApproachFormSet = inlineformset_factory(Flight, Approach, fields=(
            'approach_type', 'number'), max_num=4, extra=1)
        HoldingFormSet = inlineformset_factory(
            Flight, Holding, fields=('hold',), max_num=1, extra=1)

        if self.request.POST:
            # Create a formset instance to edit an existing model object,
            # but use POST data to populate the formset.
            context['approaches'] = ApproachFormSet(
                self.request.POST, instance=self.get_object())
            context['holding'] = HoldingFormSet(
                self.request.POST, instance=self.get_object())

        else:
            # Create a formset with the data from model object and add it to context
            context['approaches'] = ApproachFormSet(instance=self.get_object())
            context['holding'] = HoldingFormSet(instance=self.get_object())

        context['title'] = "D-> | Update Flight"
        context['parent_name'] = 'Logbook'
        context['parent_link'] = reverse('flight_list')
        context['page_title'] = "Update Flight"
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        approaches = context['approaches']
        holding = context['holding']
        with transaction.atomic():
            self.object = form.save()

            if approaches.is_valid():
                approaches.instance = self.object
                approaches.save()
            if holding.is_valid():
                holding.instance = self.object
                holding.save()
            else:
                context.update({'approaches': approaches},
                               {'holding': holding})
                return self.render_to_response(context)

        return super(FlightUpdate, self).form_valid(form)


class FlightDetail(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, DetailView):
    model = Flight
    template_name = 'flights/flight_detail.html'

    def get_context_data(self, **kwargs):
        context = super(FlightDetail, self).get_context_data(**kwargs)
        user = self.request.user
        queryset = Flight.objects.filter(user=user).filter(pk=self.object.pk)

        get_map_data(queryset, user)

        flight = Flight.objects.filter(user=user).get(pk=self.object.pk)
        earliest = Flight.objects.filter(user=user).earliest('date')
        try:
            next_flight = flight.get_next_by_date(user=user)
        except ObjectDoesNotExist:
            next_flight = flight
        try:
            previous_flight = flight.get_previous_by_date(user=user)
        except ObjectDoesNotExist:
            previous_flight = earliest

        context['next_flight'] = next_flight
        context['previous_flight'] = previous_flight

        context['title'] = "D-> | Flight Detail"
        context['page_title'] = "Detail"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'

        return context


class FlightDelete(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = Flight
    template_name = 'flights/flight_delete.html'
    success_url = '/logbook/'

    def get_context_data(self, **kwargs):
        context = super(FlightDelete, self).get_context_data(**kwargs)

        context['title'] = "D-> | Delete Flight"
        context['page_title'] = "Delete"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context

# -------------------Aircraft CRUD-----------------------

# class AircraftList(LoginRequiredMixin, UserObjectsMixin, ListView):
#     model = Aircraft
#     template_name = "aircraft/aircraft_list.html"
#     aircraft_form = AircraftForm
#
#     def get_context_data(self, **kwargs):
#         user = self.request.user
#         context = super(AircraftList, self).get_context_data(**kwargs)
#
#         context['title'] = "D-> | Aircraft"
#         context['parent_name'] = 'Home'
#         context['parent_link'] = reverse('home')
#         context['page_title'] = "Aircraft"
#         return context


class AircraftCreate(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = Aircraft
    form_class = AircraftForm
    template_name = "aircraft/aircraft_create_form.html"
    success_url = "/aircraft/"

    def form_valid(self, form):
        object = form.save(commit=False)
        object.user = self.request.user
        object.save()
        return super(AircraftCreate, self).form_valid(form)

    def get_context_data(self, **kwargs):
        user = self.request.user

        context = super(AircraftCreate, self).get_context_data(**kwargs)
        context['title'] = "D-> | New Aircraft"

        context['home_link'] = reverse('home')
        context['page_title'] = "New Aircraft"
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class AircraftUpdate(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = Aircraft
    form_class = AircraftForm
    template_name = 'aircraft/aircraft_update_form.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super(AircraftUpdate, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update " + str(self.object)
        context['page_title'] = "Update " + str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class AircraftDetail(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, DetailView):
    model = Aircraft
    form = TailNumberForm
    template_name = 'aircraft/aircraft_detail.html'

    def get_context_data(self, **kwargs):
        context = super(AircraftDetail, self).get_context_data(**kwargs)
        context['tailnumbers'] = TailNumber.objects.all().filter(
            aircraft=self.object)

        flights = Flight.objects.all().filter(aircraft_type=self.object)
        user = self.request.user
        get_map_data(flights, user)
        context['flights'] = flights

        if TailNumber.objects.filter(aircraft__aircraft_type=self.object).exists():
            pass
        else:
            context['aircraft_needs_tailnumber'] = "Please select a tailnumber for {}".format(
                self.object.aircraft_type)

        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class AircraftDelete(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = Aircraft
    template_name = 'aircraft/aircraft_delete.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super(AircraftDelete, self).get_context_data(**kwargs)

        deletable_objects, model_count, protected = get_deleted_objects([
                                                                        self.object])

        context['deletable_objects'] = deletable_objects
        context['model_count'] = dict(model_count).items()
        context['protected'] = protected

        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = "Delete " + str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


# ------------------TailNumber CRUD----------------------

class TailNumberList(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, ListView):
    model = TailNumber
    template_name = "tailnumbers/tailnumber_list.html"
    context_object_name = 'tailnumbers'

    def get_context_data(self, **kwargs):
        context = super(TailNumberList, self).get_context_data(**kwargs)

        user = self.request.user

        aircraft_list = []
        for aircraft in Aircraft.objects.filter(user=user).all():
            if TailNumber.objects.filter(user=user).filter(aircraft__aircraft_type=aircraft).exists():
                pass
            else:
                aircraft_list.append(aircraft)
                context['aircraft_needs_tailnumber'] = aircraft_list

        if len(Aircraft.objects.filter(user=user).all()) == 0:
            context['new_user_aircraft'] = True
        else:
            context['new_user_aircraft'] = False

        if len(TailNumber.objects.filter(user=user).all()) == 0:
            context['new_user_tailnumber'] = True
        else:
            context['new_user_tailnumber'] = False

        if len(Flight.objects.filter(user=user).all()) == 0:
            context['new_user_flight'] = True
        else:
            context['new_user_flight'] = False

        context['title'] = "D-> | Aircraft"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = "Aircraft"
        return context


class TailNumberCreate(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = TailNumber
    form_class = TailNumberForm
    template_name = "tailnumbers/tailnumber_create_form.html"

    def form_valid(self, form):
        object = form.save(commit=False)
        object.user = self.request.user
        object.save()
        return super(TailNumberCreate, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(TailNumberCreate, self).get_context_data(**kwargs)

        context['title'] = "D-> | New TailNumber"
        context['page_title'] = "New Tailnumber"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class TailNumberUpdate(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = TailNumber
    form_class = TailNumberForm
    template_name = 'tailnumbers/tailnumber_update_form.html'

    def get_context_data(self, **kwargs):
        context = super(TailNumberUpdate, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update " + str(self.object)
        context['page_title'] = "Update " + str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class TailNumberDetail(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, DetailView):
    model = TailNumber
    template_name = 'tailnumbers/tailnumber_detail.html'

    def get_context_data(self, **kwargs):
        tailnumber = self.object
        user = self.request.user
        flights = Flight.objects.filter(
            user=user).filter(registration=self.object)
        get_map_data(flights, user)

        context = super(TailNumberDetail, self).get_context_data(**kwargs)

        if len(Aircraft.objects.filter(user=user).all()) == 0:
            context['new_user_aircraft'] = True
        else:
            context['new_user_aircraft'] = False

        if len(TailNumber.objects.filter(user=user).all()) == 0:
            context['new_user_tailnumber'] = True
        else:
            context['new_user_tailnumber'] = False

        if len(Flight.objects.filter(user=user).all()) == 0:
            context['new_user_flight'] = True
        else:
            context['new_user_flight'] = False

        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        context['child_name'] = tailnumber.aircraft
        context['child_link'] = reverse('aircraft_detail', args=[
                                        self.object.aircraft.pk])
        context['flights'] = flights
        return context


class TailNumberDelete(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = TailNumber
    template_name = 'tailnumbers/tailnumber_delete.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super(TailNumberDelete, self).get_context_data(**kwargs)

        context['title'] = "D-> | Delete " + str(self.object)
        context['page_title'] = "Delete " + str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class IacraView(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, TemplateView):
    template_name = "flights/iacra.html"

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super(IacraView, self).get_context_data(**kwargs)

        context['total'] = Total.objects.filter(user=user).get(total='All')
        context['ASEL'] = Total.objects.filter(user=user).get(total='ASEL')
        context['AMEL'] = Total.objects.filter(user=user).get(total='AMEL')
        context['ASES'] = Total.objects.filter(user=user).get(total='ASES')
        context['AMES'] = Total.objects.filter(user=user).get(total='AMES')
        context['HELO'] = Total.objects.filter(user=user).get(total='HELO')
        context['GYRO'] = Total.objects.filter(user=user).get(total='GYRO')

        airplane_query = Q(
            aircraft_type__aircraft_category__aircraft_category__icontains='airplane')
        airplane_xc_dual = Flight.objects.filter(user=user).filter(
            airplane_query, cross_country=True, dual=True).aggregate(Sum('duration'))
        if not airplane_xc_dual.get('duration__sum'):
            context['airplane_xc_dual'] = 0.0
        else:
            context['airplane_xc_dual'] = round(
                airplane_xc_dual.get('duration__sum'), 1)

        airplane_xc_solo = Flight.objects.filter(user=user).filter(
            airplane_query, cross_country=True, solo=True).aggregate(Sum('duration'))
        if not airplane_xc_solo.get('duration__sum'):
            context['airplane_xc_solo'] = 0.0
        else:
            context['airplane_xc_solo'] = round(
                airplane_xc_solo.get('duration__sum'), 1)

        airplane_xc_pic_sic_query = Q(cross_country=True) & Q(
            pilot_in_command=True) | Q(second_in_command=True)
        airplane_xc_pic_sic = Flight.objects.filter(user=user).filter(
            airplane_query, airplane_xc_pic_sic_query).aggregate(Sum('duration'))
        if not airplane_xc_pic_sic.get('duration__sum'):
            context['airplane_xc_pic_sic'] = 0.0
        else:
            context['airplane_xc_pic_sic'] = round(
                airplane_xc_pic_sic.get('duration__sum'), 1)

        airplane_night_dual = Flight.objects.filter(user=user).filter(
            airplane_query, night=True, dual=True).aggregate(Sum('duration'))
        if not airplane_night_dual.get('duration__sum'):
            context['airplane_night_dual'] = 0.0
        else:
            context['airplane_night_dual'] = round(
                airplane_night_dual.get('duration__sum'), 1)

        airplane_night_pic_sic_query = Q(night=True) & Q(
            pilot_in_command=True) | Q(second_in_command=True)
        airplane_night_pic_sic = Flight.objects.filter(user=user).filter(
            airplane_query, airplane_night_pic_sic_query).aggregate(Sum('duration'))
        if not airplane_night_pic_sic.get('duration__sum'):
            context['airplane_night_pic_sic'] = 0.0
        else:
            context['airplane_night_pic_sic'] = round(
                airplane_night_pic_sic.get('duration__sum'), 1)

        night_ldg_pic = Flight.objects.filter(user=user).filter(
            airplane_query, pilot_in_command=True).aggregate(Sum('landings_night'))
        if not night_ldg_pic.get('landings_night__sum'):
            context['airplane_night_ldg_pic'] = 0
        else:
            context['airplane_night_ldg_pic'] = night_ldg_pic.get(
                'landings_night__sum')

        night_ldg_sic = Flight.objects.filter(user=user).filter(
            airplane_query, second_in_command=True).aggregate(Sum('landings_night'))
        if not night_ldg_sic.get('landings_night__sum'):
            context['airplane_night_ldg_sic'] = 0
        else:
            context['airplane_night_ldg_sic'] = night_ldg_sic.get(
                'landings_night__sum')

# ---------------rotorcraft---------------
        rotorcraft_query = Q(
            aircraft_type__aircraft_category__aircraft_category__icontains='rotorcraft')
        rotorcraft_xc_dual = Flight.objects.filter(user=user).filter(
            rotorcraft_query, cross_country=True, dual=True).aggregate(Sum('duration'))
        if not rotorcraft_xc_dual.get('duration__sum'):
            context['rotorcraft_xc_dual'] = 0.0
        else:
            context['rotorcraft_xc_dual'] = round(
                rotorcraft_xc_dual.get('duration__sum'), 1)

        rotorcraft_xc_solo = Flight.objects.filter(user=user).filter(
            rotorcraft_query, cross_country=True, solo=True).aggregate(Sum('duration'))
        if not rotorcraft_xc_solo.get('duration__sum'):
            context['rotorcraft_xc_solo'] = 0.0
        else:
            context['rotorcraft_xc_solo'] = round(
                rotorcraft_xc_solo.get('duration__sum'), 1)

        rotorcraft_xc_pic_sic_query = Q(cross_country=True) & Q(
            pilot_in_command=True) | Q(second_in_command=True)
        rotorcraft_xc_pic_sic = Flight.objects.filter(user=user).filter(
            rotorcraft_query, rotorcraft_xc_pic_sic_query).aggregate(Sum('duration'))
        if not rotorcraft_xc_pic_sic.get('duration__sum'):
            context['rotorcraft_xc_pic_sic'] = 0.0
        else:
            context['rotorcraft_xc_pic_sic'] = round(
                rotorcraft_xc_pic_sic.get('duration__sum'), 1)

        rotorcraft_night_dual = Flight.objects.filter(user=user).filter(
            rotorcraft_query, night=True, dual=True).aggregate(Sum('duration'))
        if not rotorcraft_night_dual.get('duration__sum'):
            context['rotorcraft_night_dual'] = 0.0
        else:
            context['rotorcraft_night_dual'] = round(
                rotorcraft_night_dual.get('duration__sum'), 1)

        rotorcraft_night_pic_sic_query = Q(night=True) & Q(
            pilot_in_command=True) | Q(second_in_command=True)
        rotorcraft_night_pic_sic = Flight.objects.filter(user=user).filter(
            rotorcraft_query, rotorcraft_night_pic_sic_query).aggregate(Sum('duration'))
        if not rotorcraft_night_pic_sic.get('duration__sum'):
            context['rotorcraft_night_pic_sic'] = 0.0
        else:
            context['rotorcraft_night_pic_sic'] = round(
                rotorcraft_night_pic_sic.get('duration__sum'), 1)

        night_ldg_pic = Flight.objects.filter(user=user).filter(
            rotorcraft_query, pilot_in_command=True).aggregate(Sum('landings_night'))
        if not night_ldg_pic.get('landings_night__sum'):
            context['rotorcraft_night_ldg_pic'] = 0.0
        else:
            context['rotorcraft_night_ldg_pic'] = round(
                night_ldg_pic.get('landings_night__sum'), 1)

        night_ldg_sic = Flight.objects.filter(user=user).filter(
            rotorcraft_query, second_in_command=True).aggregate(Sum('landings_night'))
        if not night_ldg_sic.get('landings_night__sum'):
            context['rotorcraft_night_ldg_sic'] = 0.0
        else:
            context['rotorcraft_night_ldg_sic'] = round(
                night_ldg_sic.get('landings_night__sum'), 1)

        context['title'] = "D-> | IACRA - 8710"
        context['page_title'] = "IACRA - 8710"
        context['parent_link'] = reverse('home')
        context['parent_name'] = 'Home'

        return context

class ImportAircraftListView(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, ListView):
    model = ImportAircraft
    template_name = 'import_aircraft/import_aircraft_list.html'

    def get_queryset(self, **kwargs):
        queryset = super().get_queryset(**kwargs)
        queryset = ImportAircraft.objects.filter(user=self.request.user)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "D-> | Import Aircraft"
        context['page_title'] = "Import Aircraft"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class ImportAircraftCreateView(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, CreateView):
    model = ImportAircraft
    form_class = ImportAircraftForm
    template_name = 'import_aircraft/import_aircraft_create.html'
    success_url = '/import/aircraft/'

    def form_valid(self, form):
        object = form.save(commit=False)
        object.user = self.request.user
        object.save()
        return super(ImportAircraftCreateView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(ImportAircraftCreateView,
                        self).get_context_data(**kwargs)

        context['title'] = "D-> | Import Aircraft Create"
        context['page_title'] = "Import Aircraft Create"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('import_aircraft_list')
        context['parent_name'] = 'Import Aircraft'
        return context


class ImportAircraftUpdateView(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, UpdateView):
    model = ImportAircraft
    form_class = ImportAircraftForm
    template_name = 'import_aircraft/import_aircraft_update.html'
    success_url = '/import/aircraft/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['title'] = "D-> | Import Aircraft Update"
        context['page_title'] = "Import Aircraft Update"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('import_aircraft_list')
        context['parent_name'] = 'Import Aircraft'
        return context


class ImportAircraftDetailView(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, DetailView):
    model = ImportAircraft
    template_name = 'import_aircraft/import_aircraft_detail.html'

class ImportAircraftDeleteView(ProfileNotActiveMixin, LoginRequiredMixin, UserObjectsMixin, DeleteView):
    model = ImportAircraft
    template_name = 'import_aircraft/import_aircraft_delete.html'
