import warnings
from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from api.serializers import FlightSerializer


class FlightDurationValidationTests(SimpleTestCase):
    def test_serializer_fields_construct_without_numeric_bound_warnings(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "error",
                message=r"(?:min|max)_value should be an integer or Decimal instance\.",
                category=UserWarning,
            )
            fields = FlightSerializer().fields

        self.assertIn("duration", fields)

    def test_duration_accepts_zero_and_positive_values_but_rejects_negative(self):
        field = FlightSerializer().fields["duration"]

        self.assertEqual(field.run_validation("0.0"), Decimal("0.0"))
        self.assertEqual(field.run_validation("0.1"), Decimal("0.1"))
        with self.assertRaises(ValidationError) as error:
            field.run_validation("-0.1")
        self.assertEqual(error.exception.detail[0].code, "min_value")
