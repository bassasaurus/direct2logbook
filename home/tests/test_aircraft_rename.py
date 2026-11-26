from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from flights.models import Aircraft, Flight, Stat, TailNumber
from profile.models import Reminder


@override_settings(SECURE_SSL_REDIRECT=False)
class AircraftRenameReminderTests(TestCase):
    def test_aircraft_update_preserves_milestones_and_refreshes_web_and_mobile_labels(self):
        user = get_user_model().objects.create_user('rename-pilot')
        user.profile.active = True
        user.profile.save(update_fields=['active'])
        aircraft = Aircraft.objects.create(user=user, aircraft_type='737',
            aircraft_category='A', aircraft_class='MEL', turbine=True, large=True)
        tail = TailNumber.objects.create(user=user, aircraft=aircraft,
            registration='N737', is_121=True)
        flight = Flight.objects.create(user=user, date=date.today(), aircraft_type=aircraft,
            registration=tail, route='SEA-ORD', duration=Decimal('2.0'), second_in_command=True)
        reminders = [Reminder.objects.create(user=user, kind=kind, aircraft=aircraft,
            title='Original 737 title', target_hours=Decimal('5.0'), crew_position=role)
            for kind, role in [('time_in_type', ''), ('crew_in_type', 'second_in_command')]]
        self.client.force_login(user)

        response = self.client.post(reverse('aircraft_update', args=[aircraft.pk]), {
            'aircraft_type': 'B737', 'aircraft_category': 'A', 'aircraft_class': 'MEL',
            'engine': 'turbine', 'weight_category': 'large',
        })
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        aircraft.refresh_from_db()
        self.assertEqual(aircraft.aircraft_type, 'B737')
        self.assertFalse(Stat.objects.filter(user=user, aircraft_type='737').exists())
        summary = Stat.objects.get(user=user, aircraft_type='B737')
        self.assertEqual(summary.total_time, Decimal('2.0'))
        self.assertEqual(summary.second_in_command, Decimal('2.0'))
        flight.refresh_from_db()
        self.assertEqual(flight.aircraft_type_id, aircraft.pk)
        for reminder in reminders:
            reminder.refresh_from_db()
            self.assertEqual(reminder.aircraft_id, aircraft.pk)

        for url in [reverse('home'), reverse('manage_reminders') + '?group=milestones']:
            page = self.client.get(url)
            self.assertContains(page, 'B737')
            self.assertNotContains(page, 'Original 737 title')

        mobile = APIClient()
        mobile.force_authenticate(user)
        response = mobile.get(reverse('mobile_manage_reminders'))
        self.assertEqual(response.status_code, 200)
        rows = response.json()['reminders']
        self.assertEqual({row['id'] for row in rows}, {r.pk for r in reminders})
        for row in rows:
            self.assertEqual(row['aircraft'], aircraft.pk)
            prefix = 'B737 SIC' if row['kind'] == 'crew_in_type' else 'B737'
            self.assertEqual(row['progress_label'], f'{prefix} 2.0/5 | -3')
            self.assertIn('B737', row['goal_label'])
