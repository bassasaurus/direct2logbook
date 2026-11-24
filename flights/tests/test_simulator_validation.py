from decimal import Decimal
from django.test import SimpleTestCase
from flights.simulator_validation import validate_simulator_entry


class StagedSimulatorValidationTests(SimpleTestCase):
    def test_requirements_progress_in_order(self):
        values = {'simulator': True, 'instrument_credit_eligible': True}
        steps = (
            ('device_type', {'device_type': 'ATD'}),
            ('atd_type', {'atd_type': 'BATD'}),
            ('device_id', {'device_id': 'B42'}),
            ('dual', {'dual': True}),
            ('duration', {'duration': Decimal('2.0')}),
            ('simulated_instrument', {'simulated_instrument': Decimal('1.0')}),
        )
        for field, change in steps:
            with self.subTest(stage=field):
                errors = validate_simulator_entry(values, aircraft_category='A')
                self.assertEqual(list(errors), [field])
                values.update(change)
        self.assertEqual(validate_simulator_entry(values, aircraft_category='A'), {})

    def test_practice_without_rating_credit_does_not_require_dual(self):
        self.assertEqual(validate_simulator_entry({'simulator': True, 'device_type': 'FFS',
            'device_id': 'F42', 'duration': Decimal('2.0')}), {})

    def test_legacy_omitted_details_remain_compatible(self):
        self.assertEqual(validate_simulator_entry({'simulator': True}, require_device=False), {})
        self.assertIn('device_type', validate_simulator_entry({'simulator': True,
            'instrument_credit_eligible': True}, require_device=False))

    def test_instrument_time_cannot_exceed_session_even_without_credit_claim(self):
        self.assertIn('simulated_instrument', validate_simulator_entry({'simulator': True,
            'device_type': 'FTD', 'device_id': 'F42', 'duration': Decimal('2.0'),
            'simulated_instrument': Decimal('2.1')}))

    def test_rating_credit_rejects_nonairplane_device_and_never_invents_dual(self):
        values = {'simulator': True, 'device_type': 'FFS', 'device_id': 'R42',
                  'instrument_credit_eligible': True, 'duration': Decimal('2.0')}
        self.assertIn('instrument_credit_eligible', validate_simulator_entry(values, aircraft_category='R'))
        self.assertNotIn('dual', values)
