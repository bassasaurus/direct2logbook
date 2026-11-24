from pdf_output.models import PDFRequest
from flights.models import (
    Flight, TailNumber, Aircraft, Total, Imported, Stat,
    Regs, Weight, Endorsement, Power)
from flights.views import LoginRequiredMixin
from profile.views import ProfileNotActiveMixin
from django.views.generic import TemplateView
import datetime
from decimal import Decimal
from .reminders import medical_expiration_alert, ordered_reminders, reminder_rows, reminder_groups
from .currency import instrument_recency, instrument_recency_categories, instrument_currency_notice
from .flight_reviews import flight_review_currency
from .currency import (
    amel_vfr_day, amel_vfr_night, asel_vfr_day, asel_vfr_night,
    ases_vfr_day, ases_vfr_night, ames_vfr_day, ames_vfr_night,
    helo_vfr_day, helo_vfr_night, gyro_vfr_day, gyro_vfr_night,
    medical_expiry_date, type_currency)
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Sum, F, Exists, OuterRef
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

        context['reminders'] = reminder_rows(user, include_saved=True, respect_dismissal=True)

        context['flight_review_currency'] = flight_review_currency(user)

        context['pdf_request'] = PDFRequest.objects.filter(user=user).first()

        context['recent'] = Flight.objects.filter(
            user=user).order_by('-date', '-pk')[:8]

        # Check all aircraft in one query instead of two lookups per aircraft.
        aircraft_list = list(Aircraft.objects.filter(user=user).annotate(
            has_tailnumber=Exists(TailNumber.objects.filter(user=user, aircraft_id=OuterRef('pk'))),
            has_imported=Exists(Imported.objects.filter(user=user, aircraft_type_id=OuterRef('pk'))),
        ).filter(has_tailnumber=False, has_imported=False))
        if aircraft_list:
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

        # Share the same instrument counts with the mobile API.
        context.update(instrument_recency(user))
        context['instrument_categories'] = instrument_recency_categories(user)

        from .pilot_time import pilot_time_report, report_context
        pilot_time = pilot_time_report(user)
        context.update(report_context(pilot_time))
        from .instrument_credit import instrument_airplane_device_credit
        context['instrument_device_credit'] = instrument_airplane_device_credit(user)


        context['aircraft_type_rating'] = Aircraft.objects.filter(user=user).filter(requires_type=True)
        context['type_currency'] = type_currency(user)

        context['amel_vfr_day'], context['amel_vfr_day_current'] = amel_vfr_day(user)
        context['amel_vfr_night'], context['amel_vfr_night_current'] = amel_vfr_night(user)

        context['asel_vfr_day'], context['asel_vfr_day_current'] = asel_vfr_day(user)
        context['asel_vfr_night'], context['asel_vfr_night_current'] = asel_vfr_night(user)

        context['ases_vfr_day'], context['ases_vfr_day_current'] = ases_vfr_day(user)
        context['ases_vfr_night'], context['ases_vfr_night_current'] = ases_vfr_night(user)

        context['ames_vfr_day'], context['ames_vfr_day_current'] = ames_vfr_day(user)
        context['ames_vfr_night'], context['ames_vfr_night_current'] = ames_vfr_night(user)

        context['helo_vfr_day'], context['helo_vfr_day_current'] = helo_vfr_day(user)
        context['helo_vfr_night'], context['helo_vfr_night_current'] = helo_vfr_night(user)

        context['gyro_vfr_day'], context['gyro_vfr_day_current'] = gyro_vfr_day(user)
        context['gyro_vfr_night'], context['gyro_vfr_night_current'] = gyro_vfr_night(user)

        context['expiry_date'] = medical_expiry_date(user.profile)
        context['medical_alert'] = medical_expiration_alert(
            context['expiry_date'],
        )

        medical = dict(context['medical_alert'], medical=True) if context['medical_alert'] else None
        instrument_notices = [notice for snapshot in context['instrument_categories']
                              if (notice := instrument_currency_notice(user, snapshot))]
        context['dashboard_reminders'] = ordered_reminders(
            ([medical] if medical else []) + context['reminders'] + instrument_notices)

        from .reminders import web_reminder_token, web_reminder_hidden
        from django.utils import timezone
        visible_reminders = []
        from home.regulatory_preferences import annotate
        for notice in context['dashboard_reminders']:
            notice = annotate(user.profile, notice)
            if web_reminder_hidden(user.profile.web_reminder_preferences, notice, timezone.localdate()):
                continue
            if notice['severity'] in ('danger', 'warning'):
                notice['web_action_token'] = web_reminder_token(user, notice)
            visible_reminders.append(notice)
        from home.medical_reminders import medical_hidden
        context['medical_card_notice'] = {**context['medical_alert'], 'medical': True,
                                          'web_action_token': web_reminder_token(user, {**context['medical_alert'], 'medical': True})}
        context['medical_card_visible'] = context['medical_alert']['severity'] != 'success' and not medical_hidden(user.profile, context['medical_alert'])
        visible_reminders = [row for row in visible_reminders if not row.get('medical')]
        context['dashboard_reminders'] = visible_reminders
        context['reminder_groups'] = reminder_groups(context['dashboard_reminders'])
        for group in context['reminder_groups']:
            group['medical_rows'] = [row for row in group['rows'] if row.get('medical')]
            available = [row for row in group['rows'] if not row.get('medical')]
            group['preview_rows'] = available[:3]
            preview_ids = {id(row) for row in group['preview_rows']}
            group['extra_rows'] = [row for row in available if id(row) not in preview_ids]


        context['new_user_aircraft'] = not Aircraft.objects.filter(user=user).exists()
        context['new_user_tailnumber'] = not TailNumber.objects.filter(user=user).exists()
        context['new_user_flight'] = not Flight.objects.filter(user=user).exists()

        context['flights'] = Flight.objects.filter(user=user)
        from .pilot_time import SUMMARY_LABELS
        context['totals'] = list(Total.objects.filter(user=user).filter(Q(total_time__gt=0) | Q(simulator__gt=0)))
        for total in context['totals']:
            total.display_name = SUMMARY_LABELS.get(total.total, total.total)
            total.launch_counts = next((row for row in pilot_time['launches'] if row['code'] == total.total == 'GL'), None)
        context['stats'] = Stat.objects.filter(user=user)
        context['regs'] = Regs.objects.filter(user=user)
        context['weights'] = Weight.objects.filter(
            user=user).exclude(total__lte=.1)
        context['powers'] = Power.objects.filter(user=user)
        context['endorsements'] = Endorsement.objects.filter(
            user=user).exclude(endorsement='Simple').exclude(total__lte=.1)
        context['title'] = 'D-> | Home'
        context['page_title'] = "Home"
        return context
