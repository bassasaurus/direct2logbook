from django.db.models import F


def aircraft_tail_integrity_issues(app_registry, using):
    flight = app_registry.get_model('flights', 'Flight')
    rows = flight.objects.using(using).filter(registration__isnull=False).exclude(aircraft_type_id=F('registration__aircraft_id')).order_by('pk')
    if not rows.exists():
        return []
    return [f'Flight aircraft/tailnumber: {rows.count()} mismatch(es); sample IDs {list(rows.values_list("pk", flat=True)[:10])}']
