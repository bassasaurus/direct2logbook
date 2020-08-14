from flights.models import (
    Flight, TailNumber, Aircraft, Total, Imported, Stat,
    Regs, Weight, Endorsement, Power)
from flights.views import LoginRequiredMixin
from common.views import ProfileNotActiveMixin
from django.views.generic import TemplateView
import datetime
from .currency import (
    amel_vfr_day, amel_vfr_night, asel_vfr_day, asel_vfr_night,
    ases_vfr_day, ases_vfr_night, ames_vfr_day, ames_vfr_night,
    helo_vfr_day, helo_vfr_night, gyro_vfr_day, gyro_vfr_night,
    medical_duration, type_currency)
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Sum, F
from django.shortcuts import render, redirect


def index_view(request):
    context = {
        'title': 'D-> | Direct2Logbook'
    }
    if request.user.is_authenticated:
        return redirect('home')
    else:
        return render(request, 'home/index.html', context)


class HomeView(LoginRequiredMixin, ProfileNotActiveMixin, TemplateView):  # ProfileNotActiveMixin
    template_name = 'home/home.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super(HomeView, self).get_context_data(**kwargs)

        context['recent'] = Flight.objects.filter(
            user=user).order_by('-date')[:5]

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
            context['hold_current_date'] = hold_date_qs.date

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
            gyro_pic = gyro.pilot_in_command
            gyro_sic = gyro.second_in_command
        else:
            gyro_total = 0
            gyro_dual = 0
            gyro_solo = 0
            gyro_ifr = 0
            gyro_ldg_night = 0
            gyro_pic = 0
            gyro_sic = 0

        context['airplane_total'] = asel_total + amel_total + ases_total + ames_total
        context['airplane_dual'] = asel_dual + amel_dual + ases_dual + ames_dual
        context['airplane_solo'] = asel_solo + amel_solo + ases_solo + ames_solo
        context['airplane_ifr'] = asel_ifr + amel_ifr + ases_ifr + ames_ifr
        context['airplane_ldg_night'] = asel_ldg_night + amel_ldg_night + ases_ldg_night + ames_ldg_night
        context['airplane_pic'] = asel_pic + amel_pic + ases_pic + ames_pic
        context['airplane_sic'] = asel_sic + amel_sic + ases_sic + ames_sic

        context['rotor_total'] = helo_total + gyro_total
        context['rotor_dual'] = helo_dual + gyro_dual
        context['rotor_solo'] = helo_solo + gyro_solo
        context['rotor_ifr'] = helo_ifr + gyro_ifr
        context['rotor_ldg_night'] = helo_ldg_night + gyro_ldg_night
        context['rotor_pic'] = helo_pic + gyro_pic
        context['rotor_sic'] = helo_sic + gyro_sic

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

        context['aircraft_type_rating'] = Aircraft.objects.filter(user=user).filter(requires_type=True)
        context['type_currency'] = type_currency(user)

        context['amel_vfr_day'] = amel_vfr_day(user)[0]
        context['amel_vfr_day_current'] = amel_vfr_day(user)[1]
        context['amel_vfr_night'] = amel_vfr_night(user)[0]
        context['amel_vfr_night_current'] = amel_vfr_night(user)[1]

        context['asel_vfr_day'] = asel_vfr_day(user)[0]
        context['asel_vfr_day_current'] = asel_vfr_day(user)[1]
        context['asel_vfr_night'] = asel_vfr_night(user)[0]
        context['asel_vfr_night_current'] = asel_vfr_night(user)[1]

        context['ases_vfr_day'] = ases_vfr_day(user)[0]
        context['ases_vfr_day_current'] = ases_vfr_day(user)[1]
        context['ases_vfr_night'] = ases_vfr_night(user)[0]
        context['ases_vfr_night_current'] = ases_vfr_night(user)[1]

        context['ames_vfr_day'] = ames_vfr_day(user)[0]
        context['ames_vfr_day_current'] = ames_vfr_day(user)[1]
        context['ames_vfr_night'] = ames_vfr_night(user)[0]
        context['ames_vfr_night_current'] = ames_vfr_night(user)[1]

        context['helo_vfr_day'] = helo_vfr_day(user)[0]
        context['helo_vfr_day_current'] = helo_vfr_day(user)[1]
        context['helo_vfr_night'] = helo_vfr_night(user)[0]
        context['helo_vfr_night_current'] = helo_vfr_night(user)[1]

        context['gyro_vfr_day'] = gyro_vfr_day(user)[0]
        context['gyro_vfr_day_current'] = gyro_vfr_day(user)[1]
        context['gyro_vfr_night'] = gyro_vfr_night(user)[0]
        context['gyro_vfr_night_current'] = gyro_vfr_night(user)[1]

        context['expiry_date'] = medical_duration(user)[0]
        context['this_month'] = medical_duration(user)[1]
        context['expiring'] = medical_duration(user)[2]
        context['expired'] = medical_duration(user)[3]
        context['current'] = medical_duration(user)[4]

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
