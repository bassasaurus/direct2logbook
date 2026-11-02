from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from flights.models import Aircraft, Flight, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class CrossCountryCrewTotalsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='xc_owner')
        self.other = get_user_model().objects.create_user(username='xc_other')
        self.user.profile.trial = True
        self.user.profile.save()
        self.client.force_login(self.user)
        self.aircraft = {}
        self.tails = {}
        for category, code, aircraft_class in [('A', 'C172', 'SEL'), ('R', 'R44', 'HELO')]:
            aircraft = Aircraft.objects.create(user=self.user, aircraft_type=code,
                                               aircraft_category=category, aircraft_class=aircraft_class)
            self.aircraft[category] = aircraft
            self.tails[category] = TailNumber.objects.create(user=self.user, aircraft=aircraft,
                                                            registration='N' + code)

    def flight(self, category, duration, cross_country=False, pic=False, sic=False, user=None):
        # Bulk insert skips totals/map signals: this test isolates the dashboard's
        # direct Flight aggregation, without unrelated cached-statistics updates.
        return Flight.objects.bulk_create([Flight(
            user=user or self.user, aircraft_type=self.aircraft[category],
            registration=self.tails[category], date=date(2025, 1, 1), route='KAAA-KBBB',
            duration=Decimal(duration), cross_country=cross_country,
            pilot_in_command=pic, second_in_command=sic,
        )])[0]

    def test_pic_and_sic_both_require_cross_country_for_each_category(self):
        for category in ('A', 'R'):
            self.flight(category, '1.2', cross_country=True, pic=True)
            self.flight(category, '2.3', cross_country=True, sic=True)
            self.flight(category, '0.5', cross_country=True, pic=True, sic=True)
            self.flight(category, '4.0', pic=True)
            self.flight(category, '5.0', sic=True)
            self.flight(category, '6.0', cross_country=True)
            self.flight(category, '7.0', cross_country=True, sic=True, user=self.other)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        for key in ('airplane_xc_pic_sic', 'rotorcraft_xc_pic_sic'):
            # A flight with both crew flags contributes its duration only once.
            self.assertEqual(response.context[key], Decimal('4.0'))

    def test_non_cross_country_sic_only_returns_zero_without_changing_flights(self):
        flights = [self.flight(category, '2.5', sic=True) for category in ('A', 'R')]
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        for key in ('airplane_xc_pic_sic', 'rotorcraft_xc_pic_sic'):
            self.assertEqual(response.context[key], 0)
        for flight in flights:
            flight.refresh_from_db()
            self.assertEqual(flight.duration, Decimal('2.5'))
            self.assertTrue(flight.second_in_command)
            self.assertFalse(flight.cross_country)

    def test_airplane_and_rotorcraft_totals_stay_separate(self):
        self.flight('A', '1.1', cross_country=True, sic=True)
        self.flight('R', '2.2', cross_country=True, sic=True)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['airplane_xc_pic_sic'], Decimal('1.1'))
        self.assertEqual(response.context['rotorcraft_xc_pic_sic'], Decimal('2.2'))
