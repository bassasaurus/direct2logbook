from django.test import SimpleTestCase
from api.serializers import ApproachSerializer, FlightApproachWriteSerializer
from flights.approach_choices import APPROACH_CHOICES, LEGACY_APPROACH_CHOICES
from flights.forms import ApproachForm
from flights.models import Approach


class AIMApproachChoiceTests(SimpleTestCase):
    def test_new_forms_offer_specific_minima_and_keep_ils_categories(self):
        choices = dict(ApproachForm().fields['approach_type'].choices)
        for code in ('ILS', 'CATII', 'CATIII', 'GLS', 'PAR', 'ASR',
                     'LNAV', 'LP', 'LNAV/VNAV', 'LPV', 'RNP AR', 'LDA/GS'):
            self.assertIn(code, choices)
        self.assertEqual(choices['CATII'], 'ILS CAT II')
        self.assertEqual(choices['CATIII'], 'ILS CAT III')
        for code in ('GPS', 'RNAV', 'MLS', 'CAT II', 'CAT III'):
            self.assertNotIn(code, choices)
        codes = [code for code, _ in APPROACH_CHOICES]
        self.assertEqual(len(set(codes)), len(codes))

    def test_both_api_writers_accept_current_and_older_client_values(self):
        for code, _ in (*APPROACH_CHOICES, *LEGACY_APPROACH_CHOICES):
            for serializer_type in (ApproachSerializer, FlightApproachWriteSerializer):
                with self.subTest(code=code, serializer=serializer_type.__name__):
                    serializer = serializer_type(data={'approach_type': code, 'number': 2})
                    self.assertTrue(serializer.is_valid(), serializer.errors)
                    self.assertEqual(serializer.validated_data['approach_type'], code)
        serializer = FlightApproachWriteSerializer(data={'approach_type': 'MADE UP', 'number': 1})
        self.assertFalse(serializer.is_valid())

    def test_editing_a_legacy_approach_preserves_its_original_value(self):
        for code, _ in LEGACY_APPROACH_CHOICES:
            with self.subTest(code=code):
                instance = Approach(approach_type=code, number=1)
                form = ApproachForm({'approach_type': code, 'number': 2}, instance=instance)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.save(commit=False).approach_type, code)
                self.assertEqual(form.instance.number, 2)
