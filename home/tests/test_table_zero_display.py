from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase

from flights.templatetags.flights_filters import zero_dash


class TableZeroDisplayTests(SimpleTestCase):
    def test_zero_formats_become_dashes_without_altering_other_values(self):
        for value in (0, 0.0, Decimal("0.0"), "0", "0.0", "-0.00"):
            with self.subTest(value=value):
                self.assertEqual(zero_dash(value), "-")
        for value in (None, False, True, Decimal("0.1"), "12.0", "N0123", "Nov 30, 2026", "—"):
            with self.subTest(value=value):
                self.assertEqual(zero_dash(value), value)

    def test_formatted_hours_and_counts_keep_nonzero_precision(self):
        template = Template('{% load flights_filters %}<td>{{ hours|floatformat:1|zero_dash }}</td><td>{{ count|zero_dash }}</td>')
        self.assertEqual(template.render(Context({"hours": Decimal("0.0"), "count": 0})), "<td>-</td><td>-</td>")
        self.assertEqual(template.render(Context({"hours": Decimal("1.2"), "count": 3})), "<td>1.2</td><td>3</td>")
