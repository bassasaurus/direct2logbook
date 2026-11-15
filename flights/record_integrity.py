def record_integrity_issues(app_registry, using):
    """Read-only checks for core constraint candidates; never repair user data."""
    from django.db.models import Count, Q
    from django.db.models.functions import Lower

    issues = []
    for model_name, fields in (
        ('Aircraft', ('aircraft_type',)), ('TailNumber', ('registration',)), ('Flight', ('route',)),
    ):
        model = app_registry.get_model('flights', model_name)
        for field in fields:
            rows = model.objects.using(using).filter(Q(**{field + '__regex': r'^\s*$'}) | Q(**{field + '__isnull': True})).order_by('pk')
            if rows.exists():
                issues.append(f'{model_name}.{field}: {rows.count()} empty value(s); sample IDs {list(rows.values_list("pk", flat=True)[:10])}')
    for model_name, fields in (
        ('Flight', ('duration', 'night', 'instrument', 'simulated_instrument')),
        ('Imported', ('total_time', 'pilot_in_command', 'second_in_command', 'cross_country',
                      'instructor', 'dual', 'solo', 'instrument', 'night', 'simulated_instrument', 'simulator')),
    ):
        model = app_registry.get_model('flights', model_name)
        for field in fields:
            rows = model.objects.using(using).filter(**{field + '__lt': 0}).order_by('pk')
            if rows.exists():
                issues.append(f'{model_name}.{field}: {rows.count()} negative value(s); sample IDs {list(rows.values_list("pk", flat=True)[:10])}')
    for model_name, field in (('Aircraft', 'aircraft_type'), ('TailNumber', 'registration')):
        model = app_registry.get_model('flights', model_name)
        groups = model.objects.using(using).order_by().annotate(folded=Lower(field)).values('user_id', 'folded').annotate(total=Count('pk')).filter(total__gt=1)
        if groups.exists():
            examples = []
            for group in groups.order_by('user_id', 'folded')[:10]:
                ids = model.objects.using(using).annotate(folded=Lower(field)).filter(user_id=group['user_id'], folded=group['folded']).order_by('pk').values_list('pk', flat=True)
                examples.append(list(ids[:10]))
            issues.append(f'{model_name}.{field}: {groups.count()} case-insensitive duplicate group(s); sample record IDs {examples}')
    from profile.reminder_integrity import reminder_integrity_issues
    from operations.status_integrity import status_integrity_issues
    from flights.ownership_integrity import ownership_integrity_issues
    from flights.aircraft_tail_integrity import aircraft_tail_integrity_issues
    return (issues + summary_integrity_issues(app_registry, using)
            + reminder_integrity_issues(app_registry, using) + status_integrity_issues(app_registry, using) + ownership_integrity_issues(app_registry, using) + aircraft_tail_integrity_issues(app_registry, using))


def summary_integrity_issues(app_registry, using):
    """Report duplicate stored summary keys; leave every balance untouched."""
    from django.db.models import Count

    issues = []
    for name, field in (('Stat', 'aircraft_type'), ('Total', 'total'), ('Power', 'role'),
                        ('Regs', 'reg_type'), ('Endorsement', 'endorsement'), ('Weight', 'weight')):
        model = app_registry.get_model('flights', name)
        groups = model.objects.using(using).order_by().values('user_id', field).annotate(total_rows=Count('pk')).filter(total_rows__gt=1)
        if groups.exists():
            examples = []
            for group in groups.order_by('user_id', field)[:10]:
                ids = model.objects.using(using).filter(user_id=group['user_id'], **{field: group[field]}).order_by('pk').values_list('pk', flat=True)
                examples.append(list(ids[:10]))
            issues.append(f'{name}: {groups.count()} duplicate summary group(s); sample record IDs {examples}')
    return issues
