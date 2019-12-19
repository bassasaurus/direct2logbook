from flights.models import *
from accounts.models import Profile


from flights.forms import *
from django.db.models import Sum, Q, F
from django.db.models.functions import Length
from django.db.models import CharField

from django.db import transaction
from django.contrib.admin.utils import NestedObjects
from django.utils.text import capfirst

from django.forms import inlineformset_factory

from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.dates import YearArchiveView, MonthArchiveView, ArchiveIndexView
from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin

from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

from dal import autocomplete
import datetime

from flights.get_map_data import get_map_data
import flights.currency as currency

from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils.encoding import force_text

CharField.register_lookup(Length, 'length')


def get_deleted_objects(objs):
    collector = NestedObjects(using='default')
    collector.collect(objs)

    def format_callback(obj):
        opts = obj._meta
        no_edit_link = '%s: %s' % (
            capfirst(opts.verbose_name), force_text(obj))
        return no_edit_link

    to_delete = collector.nested(format_callback)[1:]
    protected = [format_callback(obj) for obj in collector.protected]
    model_count = {model._meta.verbose_name_plural: len(
        objs) for model, objs in collector.model_objs.items()}

    return to_delete, model_count, protected


def error_400(request, exception):
    context = {
        'title': '400',
        'home_link': reverse('home')
    }
    return render(request, '400.html', context)


def error_404(request, exception):
    context = {
        'title': '404',
        'home_link': reverse('home')
    }
    return render(request, '404.html', context)


def error_500(request):
    context = {
        'title': '500',
        'home_link': reverse('home')
    }
    return render(request, '500.html', context)


def error_403(request, exception):
    context = {
        'title': '403',
        'home_link': reverse('home'),
        'exception': exception
    }
    return render(request, '403.html', context)


class ProfileNotActiveMixin(UserPassesTestMixin):

    def test_func(self):
        today = datetime.datetime.now()
        profile = Profile.objects.get(user=self.request.user)

        if profile.end_date > today.date():
            expired = False
        else:
            expired = True

        if profile.active or profile.trial or profile.free_access:
            return True
        elif profile.canceled and expired is False:
            return True
        else:
            return False

    def handle_no_permission(self):
        return redirect('profile')


class LoginRequiredMixin(LoginRequiredMixin):
    login_url = '/accounts/login'
    # redirect_field_name = None


class OwnObjectMixin(UserPassesTestMixin):

    def test_func(self):
        object = self.get_object()
        if self.request.user.pk == object.user.pk:
            return True
        else:
            return False

    def handle_no_permission(self):

        return redirect(reverse('home'))


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


class HomeView(LoginRequiredMixin, TemplateView):  # ProfileNotActiveMixin
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super(HomeView, self).get_context_data(**kwargs)

        context['recent'] = Flight.objects.filter(
            user=user).order_by('-date')[:8]

        aircraft_list = []
        for aircraft in Aircraft.objects.filter(user=user).all():
            if TailNumber.objects.filter(user=user).filter(aircraft__aircraft_type=aircraft).exists() or Imported.objects.filter(user=user).filter(aircraft_type=aircraft).exists():
                pass
            else:
                aircraft_list.append(aircraft)
                context['aircraft_needs_tailnumber'] = aircraft_list

        # cat/class vfr day, night currency
        try:
            Total.objects.filter(user=user).get(total="ASEL")
            context['asel_total'] = Total.objects.filter(
                user=user).get(total="ASEL")
        except ObjectDoesNotExist:
            context['asel_total'] = 0

        try:
            Total.objects.filter(user=user).get(total="AMEL")
            context['amel_total'] = Total.objects.filter(
                user=user).get(total="AMEL")
        except ObjectDoesNotExist:
            context['amel_total'] = 0

        try:
            Total.objects.filter(user=user).get(total="ASES")
            context['ases_total'] = Total.objects.filter(
                user=user).get(total="ASES")
        except ObjectDoesNotExist:
            context['ases_total'] = 0

        try:
            Total.objects.filter(user=user).get(total="AMES")
            context['ames_total'] = Total.objects.filter(
                user=user).get(total="AMES")
        except ObjectDoesNotExist:
            context['ames_total'] = 0

        try:
            Total.objects.filter(user=user).get(total="HELO")
            context['helo_total'] = Total.objects.filter(
                user=user).get(total="HELO")
        except ObjectDoesNotExist:
            context['helo_total'] = 0

        try:
            Total.objects.filter(user=user).get(total="GYRO")
            context['gyro_total'] = Total.objects.filter(
                user=user).get(total="GYRO")
        except ObjectDoesNotExist:
            context['gyro_total'] = 0

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

        # iacra
        # use .exists() then assign value when queryset is None and build more specific contexts
        context['total'] = Total.objects.filter(user=user).get(total='All')

        if Total.objects.filter(user=user, total='ASEL').exists():
            asel = Total.objects.filter(user=user).get(total='ASEL')
            asel_total = asel.total_time
            asel_dual = asel.dual
            asel_solo = asel.solo
            asel_ifr = asel.instrument
            asel_ldg_night = asel.landings_night
            asel_pic = asel.pilot_in_command
            asel_sic = asel.second_in_command
        else:
            asel_total = 0
            asel_dual = 0
            asel_solo = 0
            asel_ifr = 0
            asel_ldg_night = 0
            asel_pic = 0
            asel_sic = 0

        if Total.objects.filter(user=user, total='AMEL').exists():
            amel = Total.objects.filter(user=user).get(total='AMEL')
            amel_total = amel.total_time
            amel_dual = amel.dual
            amel_solo = amel.solo
            amel_ifr = amel.instrument
            amel_ldg_night = amel.landings_night
            amel_pic = amel.pilot_in_command
            amel_sic = amel.second_in_command
        else:
            amel_total = 0
            amel_dual = 0
            amel_solo = 0
            amel_ifr = 0
            amel_ldg_night = 0
            amel_pic = 0
            amel_sic = 0

        if Total.objects.filter(user=user, total='ASES').exists():
            ases = Total.objects.filter(user=user).get(total='ASES')
            ases_total = ases.total_time
            ases_dual = ases.dual
            ases_solo = ases.solo
            ases_ifr = ases.instrument
            ases_ldg_night = ases.landings_night
            ases_pic = ases.pilot_in_command
            ases_sic = ases.second_in_command
        else:
            ases_total = 0
            ases_dual = 0
            ases_solo = 0
            ases_ifr = 0
            ases_ldg_night = 0
            ases_pic = 0
            ases_sic = 0

        if Total.objects.filter(user=user, total='AMES').exists():
            ames = Total.objects.filter(user=user).get(total='AMES')
            ames_total = ames.total_time
            ames_dual = ames.dual
            ames_solo = ames.solo
            ames_ifr = ames.instrument
            ames_ldg_night = ames.landings_night
            ames_pic = ames.pilot_in_command
            ames_sic = ames.second_in_command
        else:
            ames_total = 0
            ames_dual = 0
            ames_solo = 0
            ames_ifr = 0
            ames_ldg_night = 0
            ames_pic = 0
            ames_sic = 0

        if Total.objects.filter(user=user, total='HELO').exists():
            helo = Total.objects.filter(user=user).get(total='HELO')
            helo_total = helo.total_time
            helo_dual = helo.dual
            helo_solo = helo.solo
            helo_ifr = helo.instrument
            helo_ldg_night = helo.landings_night
            helo_pic = helo.pilot_in_command
            helo_sic = helo.second_in_command
        else:
            helo_total = 0
            helo_dual = 0
            helo_solo = 0
            helo_ifr = 0
            helo_ldg_night = 0
            helo_pic = 0
            helo_sic = 0

        if Total.objects.filter(user=user, total='GYRO').exists():
            gyro = Total.objects.filter(user=user).get(total='GYRO')
            gyro_total = gyro.total_time
            gyro_dual = gyro.dual
            gyro_solo = gyro.solo
            gyro_ifr = gyro.instrument
            gyro_ldg_night = gyro.landings_night
            gyro_pic = helo.pilot_in_command
            gyro_sic = gyro.second_in_command
        else:
            gyro_total = 0
            gyro_dual = 0
            gyro_solo = 0
            gyro_ifr = 0
            gyro_ldg_night = 0
            gyro_pic = 0
            gyro_sic = 0

        context['airplane_total'] = asel_total + \
            amel_total + ases_total + ames_total
        context['airplane_dual'] = asel_dual + \
            amel_dual + ases_dual + ames_dual
        context['airplane_solo'] = asel_solo + \
            amel_solo + ases_solo + ames_solo
        context['airplane_ifr'] = asel_ifr + amel_ifr + ases_ifr + ames_ifr
        context['airplane_ldg_night'] = asel_ldg_night + \
            amel_ldg_night + ases_ldg_night + ames_ldg_night
        context['airplane_pic'] = asel_pic + amel_pic + ases_pic + ames_pic
        context['airplane_sic'] = asel_sic + amel_sic + ases_sic + ames_sic

        context['rotor_total'] = helo_total + gyro_total
        context['rotor_dual'] = helo_dual + gyro_dual
        context['rotor_solo'] = helo_solo + gyro_solo
        context['rotor_ifr'] = helo_ifr + gyro_ifr
        context['rotor_ldg_night'] = helo_ldg_night + gyro_ldg_night
        context['rotor_pic'] = helo_pic + gyro_pic
        context['rotor_sic'] = helo_pic + gyro_sic

        context['asel_pic'] = asel_pic
        context['asel_sic'] = asel_sic
        context['amel_pic'] = amel_pic
        context['amel_sic'] = amel_sic
        context['ases_pic'] = ases_pic
        context['ases_sic'] = ases_sic
        context['ames_pic'] = ames_pic
        context['ames_sic'] = ames_sic
        context['helo_total'] = helo_total
        context['gyro_total'] = gyro_total

        airplane_query = Q(aircraft_type__aircraft_category='A')
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
        rotorcraft_query = Q(aircraft_type__aircraft_category='R')
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

# ---------------FTD---------------
# ---------------ATD---------------
# ---------------FFS---------------

        # end iacra

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

        if len(Aircraft.objects.filter(user=user)) == 0:
            context['new_user_aircraft'] = True
        else:
            context['new_user_aircraft'] = False

        if len(TailNumber.objects.filter(user=user)) == 0:
            context['new_user_tailnumber'] = True
        else:
            context['new_user_tailnumber'] = False

        if len(Flight.objects.filter(user=user)) == 0:
            context['new_user_flight'] = True
        else:
            context['new_user_flight'] = False

        context['flights'] = Flight.objects.filter(user=user)
        context['totals'] = Total.objects.filter(
            user=user).exclude(total_time__lte=.1)
        context['stats'] = Stat.objects.filter(user=user)
        context['regs'] = Regs.objects.filter(user=user)
        context['weights'] = Weight.objects.filter(
            user=user).exclude(total__lte=.1)
        context['powers'] = Power.objects.filter(user=user)
        context['endorsements'] = Endorsement.objects.filter(
            user=user).exclude(total__lte=.1)
        context['title'] = 'D-> | Home'
        context['page_title'] = "Home"
        return context


class FlightArchive(LoginRequiredMixin, ProfileNotActiveMixin, ArchiveIndexView):
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


class FlightArchiveYear(LoginRequiredMixin, ProfileNotActiveMixin, YearArchiveView):
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


class FlightArchiveMonth(LoginRequiredMixin, ProfileNotActiveMixin, MonthArchiveView):
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


class RemarksList(LoginRequiredMixin, ProfileNotActiveMixin, ListView):
    model = Flight
    template_name = "flights/remarks.html"
    pagninate_by = 30

    def get_queryset(self):
        return Flight.objects.filter(user=self.request.user).order_by('-date')

    def get_context_data(self, **kwargs):
        context = super(RemarksList, self).get_context_data(**kwargs)

        context['title'] = "D-> | Remarks"
        context['page_title'] = "Remarks"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('flight_list')
        context['parent_name'] = 'Logbook'
        return context


class FlightList(LoginRequiredMixin, ProfileNotActiveMixin, ListView):
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


class FlightCreate(LoginRequiredMixin, ProfileNotActiveMixin, CreateView):
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
        if (form.is_valid() and approach_form.is_valid() and holding_form.is_valid()):
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


class FlightUpdate(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, UpdateView):
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


class FlightDetail(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, DetailView):
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


class FlightDelete(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, DeleteView):
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


class AircraftCreate(LoginRequiredMixin, ProfileNotActiveMixin, CreateView):
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

        context = super(AircraftCreate, self).get_context_data(**kwargs)
        context['title'] = "D-> | New Aircraft"

        context['home_link'] = reverse('home')
        context['page_title'] = "New Aircraft"
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class AircraftUpdate(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, UpdateView):
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


class AircraftDetail(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, DetailView):
    model = Aircraft
    form = TailNumberForm
    template_name = 'aircraft/aircraft_detail.html'

    def get_context_data(self, **kwargs):
        context = super(AircraftDetail, self).get_context_data(**kwargs)
        context['tailnumbers'] = TailNumber.objects.filter(
            user=self.request.user, aircraft=self.object)

        flights = Flight.objects.filter(
            user=self.request.user, aircraft_type=self.object)
        user = self.request.user
        get_map_data(flights, user)
        context['flights'] = flights

        if TailNumber.objects.filter(user=user).filter(aircraft__aircraft_type=self.object).exists() or Imported.objects.filter(user=user).filter(aircraft_type=self.object).exists():
            pass
        else:
            context['aircraft_needs_tailnumber'] = "Please select a tailnumber for {}".format(
                self.object.aircraft_type)

        if Imported.objects.filter(user=user).filter(aircraft_type=self.object).exists():
            context['is_imported'] = True
        else:
            context['is_imported'] = False

        if not self.object.piston and not self.object.turbine:
            context['power_error'] = True
        else:
            context['power_error'] = False

        if not self.object.requires_type and not self.object.tailwheel and not self.object.simple and not self.object.compleks and not self.object.high_performance:
            context['config_error'] = True
        else:
            context['config_error'] = False

        if self.object.aircraft_category == '':
            context['category_error'] = True
        else:
            context['category_error'] = False

        if self.object.aircraft_class == '':
            context['class_error'] = True
        else:
            context['class_error'] = False

        if not self.object.superr and not self.object.heavy and not self.object.large and not self.object.medium and not self.object.small and not self.object.light_sport:
            context['weight_error'] = True
        else:
            context['weight_error'] = False

        context['title'] = "D-> | " + str(self.object)
        context['page_title'] = str(self.object)
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class AircraftDelete(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, DeleteView):
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

class TailNumberList(LoginRequiredMixin, ProfileNotActiveMixin, ListView):
    model = TailNumber
    template_name = "tailnumbers/tailnumber_list.html"
    context_object_name = 'tailnumbers'

    def get_queryset(self):
        return TailNumber.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super(TailNumberList, self).get_context_data(**kwargs)

        user = self.request.user

        aircraft_list = []
        for aircraft in Aircraft.objects.filter(user=user).all():
            if TailNumber.objects.filter(user=user).filter(aircraft__aircraft_type=aircraft).exists() or Imported.objects.filter(user=user).filter(aircraft_type=aircraft).exists():
                pass
            else:
                aircraft_list.append(aircraft)
                context['aircraft_needs_tailnumber'] = aircraft_list

        if len(Aircraft.objects.filter(user=user)) == 0:
            context['new_user_aircraft'] = True
        else:
            context['new_user_aircraft'] = False

        if len(TailNumber.objects.filter(user=user)) == 0:
            context['new_user_tailnumber'] = True
        else:
            context['new_user_tailnumber'] = False

        if len(Flight.objects.filter(user=user)) == 0:
            context['new_user_flight'] = True
        else:
            context['new_user_flight'] = False

        context['imported'] = Imported.objects.filter(user=user)

        context['title'] = "D-> | Aircraft"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = "Aircraft"
        return context


class TailNumberCreate(LoginRequiredMixin, ProfileNotActiveMixin, CreateView):
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


class TailNumberUpdate(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, UpdateView):
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


class TailNumberDetail(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, DetailView):
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


class TailNumberDelete(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, DeleteView):
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


class ImportedListView(LoginRequiredMixin, ProfileNotActiveMixin, ListView):
    model = Imported
    template_name = 'imported/imported_list.html'
    context_object_name = 'imported'

    def get_queryset(self):
        return Imported.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "D-> | Imported Aircraft"
        context['page_title'] = "Imported Aircraft"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('aircraft_list')
        context['parent_name'] = 'Aircraft'
        return context


class ImportedCreateView(LoginRequiredMixin, ProfileNotActiveMixin, CreateView):
    model = Imported
    form_class = ImportedForm
    template_name = 'imported/imported_create.html'
    success_url = '/aircraft/'

    def form_valid(self, form):
        object = form.save(commit=False)
        object.user = self.request.user
        object.save()
        return super(ImportedCreateView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(ImportedCreateView,
                        self).get_context_data(**kwargs)

        context['title'] = "D-> | Imported Aircraft Create"
        context['page_title'] = "Imported Aircraft Create"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('imported_list')
        context['parent_name'] = 'Imported Aircraft'
        return context


class ImportedUpdateView(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, UpdateView):
    model = Imported
    form_class = ImportedForm
    template_name = 'imported/imported_update.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['title'] = "D-> | Imported Aircraft Update"
        context['page_title'] = "Imported Aircraft Update"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('imported_list')
        context['parent_name'] = 'Imported Aircraft'
        return context


class ImportedDetailView(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, DetailView):
    model = Imported
    template_name = 'imported/imported_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['title'] = "D-> | Imported Aircraft Update"
        context['page_title'] = "Imported Aircraft Update"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('imported_list')
        context['parent_name'] = 'Imported Aircraft'
        return context


class ImportedDeleteView(LoginRequiredMixin, OwnObjectMixin, ProfileNotActiveMixin, DeleteView):
    model = Imported
    template_name = 'imported/imported_delete.html'
    success_url = '/aircraft/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['title'] = "D-> | Imported Aircraft Delete"
        context['page_title'] = "Imported Aircraft Delete"
        context['home_link'] = reverse('home')
        context['parent_link'] = reverse('imported_list')
        context['parent_name'] = 'Imported Aircraft'
        return context
