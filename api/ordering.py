from django.db.models import BigIntegerField, F, Func, Value
from django.db.models.functions import Cast, Lower, NullIf, Replace


def natural_registration_order(queryset):
    """Sort registrations by prefix, numeric portion, then suffix (N2 < N10)."""
    def regex_replace(expression, pattern, replacement):
        return Func(expression, Value(pattern), Value(replacement), function='REGEXP_REPLACE')

    registration = Lower(Replace(F('registration'), Value('-'), Value('')))
    # PostgreSQL substring returns NULL when no numeric group matches, avoiding
    # casts of alphabetic international registrations. Registrations are <=10 chars.
    number = Func(registration, Value('[0-9]+'), function='SUBSTRING')
    return queryset.alias(
        registration_prefix=regex_replace(registration, '[0-9].*$', ''),
        registration_number=Cast(NullIf(number, Value('')), BigIntegerField()),
        registration_suffix=regex_replace(registration, '^[^0-9]*[0-9]+', ''),
    ).order_by(
        'registration_prefix', F('registration_number').asc(nulls_last=True),
        'registration_suffix', Lower('registration'), 'pk',
    )
