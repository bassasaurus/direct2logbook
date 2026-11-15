from django.db.models import F

OWNED_RELATIONS = (
    ('flights', 'TailNumber', 'aircraft'),
    ('flights', 'Flight', 'aircraft_type'),
    ('flights', 'Flight', 'registration'),
    ('flights', 'Imported', 'aircraft_type'),
    ('profile', 'Reminder', 'aircraft'),
)


def ownership_integrity_issues(app_registry, using):
    """Read-only audit: never reassign another pilot's records automatically."""
    issues = []
    for app, name, field in OWNED_RELATIONS:
        model = app_registry.get_model(app, name)
        rows = model.objects.using(using).filter(**{field + '__isnull': False}).exclude(
            user_id=F(field + '__user_id')).order_by('pk')
        if rows.exists():
            sample = list(rows.values_list('pk', flat=True)[:10])
            issues.append(f'{name}.{field}: {rows.count()} ownership mismatch(es); sample IDs {sample}')
    return issues
