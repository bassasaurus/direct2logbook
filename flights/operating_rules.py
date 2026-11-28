"""Operating-rule labels shared by forms, APIs, imports and summaries."""
OPERATING_RULE_CHOICES = (
    ('is_91', 'Part 91'),
    ('is_121', 'Part 121'),
    ('is_125', 'Part 125'),
    ('is_135', 'Part 135'),
    ('is_137', 'Part 137'),
)
OPERATING_RULE_FIELDS = tuple(field for field, label in OPERATING_RULE_CHOICES)
OPERATING_RULE_CODES = tuple(field.removeprefix('is_') for field in OPERATING_RULE_FIELDS)
