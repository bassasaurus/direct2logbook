from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from flights.models import Aircraft, Flight, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class IACRANightHoursTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('iacra-night-owner')
        self.other = get_user_model().objects.create_user('iacra-night-other')
        self.user.profile.trial = True
        self.user.profile.save()
        self.client.force_login(self.user)
        self.aircraft = {}
        self.tails = {}
        for owner in (self.user, self.other):
            for category, code, aircraft_class in [('A', 'C172', 'SEL'), ('R', 'R44', 'HELO')]:
                aircraft = Aircraft.objects.create(user=owner, aircraft_type=code,
                    aircraft_category=category, aircraft_class=aircraft_class)
                self.aircraft[owner.pk, category] = aircraft
                self.tails[owner.pk, category] = TailNumber.objects.create(user=owner,
                    aircraft=aircraft, registration='N' + code)

    def flight(self, category, duration, night, *, pic=False, sic=False, dual=False, owner=None):
        owner = owner or self.user
        # Isolate IACRA aggregation from map and cached-summary signal work.
        return Flight.objects.bulk_create([Flight(user=owner,
            aircraft_type=self.aircraft[owner.pk, category],
            registration=self.tails[owner.pk, category], date=date(2026, 11, 1),
            route='KAAA-KBBB', duration=Decimal(duration),
            night=Decimal(night) if night is not None else None,
            pilot_in_command=pic, second_in_command=sic, dual=dual)])[0]

    def context(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        return response.context

    def test_partial_night_hours_are_summed_instead_of_entire_duration(self):
        for category in ('A', 'R'):
            self.flight(category, '3.0', '0.7', dual=True)
            self.flight(category, '2.5', '0.4', pic=True)
            self.flight(category, '1.8', '1.3', sic=True)
            self.flight(category, '4.0', '1.0', pic=True)
            self.flight(category, '0.5', '0.2', pic=True, sic=True)
            self.flight(category, '2.0', '2.0')  # No applicable crew role.
        context = self.context()
        for prefix in ('airplane', 'rotorcraft'):
            self.assertEqual(context[prefix + '_night_dual'], Decimal('0.7'))
            # A flight marked PIC and SIC contributes once to the combined total.
            self.assertEqual(context[prefix + '_night_pic_sic'], Decimal('2.9'))
            self.assertEqual(context[prefix + '_night_pic'], Decimal('1.6'))
            self.assertEqual(context[prefix + '_night_sic'], Decimal('1.5'))

    def test_daytime_and_blank_night_sic_flights_do_not_inflate_night_totals(self):
        for category in ('A', 'R'):
            self.flight(category, '5.0', '0.0', sic=True)
            self.flight(category, '4.0', None, sic=True)
            self.flight(category, '3.0', '0.0', dual=True)
        context = self.context()
        for prefix in ('airplane', 'rotorcraft'):
            self.assertEqual(context[prefix + '_night_dual'], Decimal('0.0'))
            self.assertEqual(context[prefix + '_night_pic_sic'], Decimal('0.0'))

    def test_categories_and_accounts_remain_separate_without_changing_records(self):
        self.flight('A', '3.0', '1.7', pic=True)
        self.flight('R', '2.0', '0.8', sic=True)
        self.flight('A', '3.0', '0.6', dual=True)
        self.flight('R', '2.0', '0.2', dual=True)
        self.flight('A', '9.0', '8.0', pic=True, dual=True, owner=self.other)
        before = list(Flight.objects.order_by('pk').values())
        context = self.context()
        self.assertEqual(context['airplane_night_pic_sic'], Decimal('1.7'))
        self.assertEqual(context['rotorcraft_night_pic_sic'], Decimal('0.8'))
        self.assertEqual(context['airplane_night_dual'], Decimal('0.6'))
        self.assertEqual(context['rotorcraft_night_dual'], Decimal('0.2'))
        self.assertEqual(list(Flight.objects.order_by('pk').values()), before)

    def test_empty_logbook_returns_zero_hours(self):
        context = self.context()
        for prefix in ('airplane', 'rotorcraft'):
            self.assertEqual(context[prefix + '_night_dual'], Decimal('0.0'))
            self.assertEqual(context[prefix + '_night_pic_sic'], Decimal('0.0'))
