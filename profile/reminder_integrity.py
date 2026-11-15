from django.db.models import F, Q


def reminder_conditions():
    """Database rules that mirror required fields without inventing default values."""
    kinds = ('expiration', 'flight_time', 'time_in_type', 'crew_in_type', 'company_time')
    roles = ('pilot_in_command', 'second_in_command', 'solo', 'dual')
    return [
        ('reminder_kind_valid', Q(kind__in=kinds)),
        ('reminder_target_positive', Q(target_hours__isnull=True) | Q(target_hours__gt=0)),
        ('reminder_expiration_complete', ~Q(kind='expiration') | (
            Q(due_date__isnull=False) & ~Q(title__regex=r'^\s*$'))),
        ('reminder_milestone_target', Q(kind='expiration') | Q(target_hours__isnull=False)),
        ('reminder_type_aircraft', ~Q(kind__in=('time_in_type', 'crew_in_type')) | Q(aircraft__isnull=False)),
        ('reminder_crew_valid', Q(crew_position__in=('',) + roles)),
        ('reminder_crew_required', ~Q(kind='crew_in_type') | Q(crew_position__in=roles)),
        ('reminder_company_complete', ~Q(kind='company_time') | (
            ~Q(company__regex=r'^\s*$') & Q(company_start_date__isnull=False))),
        ('reminder_company_date_order', Q(company_end_date__isnull=True) | (
            Q(company_start_date__isnull=False) & Q(company_end_date__gte=F('company_start_date')))),
    ]


def reminder_integrity_issues(app_registry, using):
    reminder = app_registry.get_model('profile', 'Reminder')
    issues = []
    for name, condition in reminder_conditions():
        rows = reminder.objects.using(using).filter(~condition).order_by('pk')
        if rows.exists():
            issues.append(f'{name}: {rows.count()} invalid reminder(s); sample IDs {list(rows.values_list("pk", flat=True)[:10])}')
    return issues
