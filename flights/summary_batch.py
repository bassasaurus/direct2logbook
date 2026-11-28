"""Defer import summaries without disconnecting signals in other requests."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import SimpleNamespace

from django.db import connection


@dataclass
class SummaryBatch:
    user_id: int
    aircraft_ids: set = field(default_factory=set)


_current_batch = ContextVar('flight_summary_batch', default=None)


def defer_flight_summary(instance):
    from flights.models import Flight
    batch = _current_batch.get()
    if batch is None or not isinstance(instance, Flight) or instance.user_id != batch.user_id:
        return False
    batch.aircraft_ids.add(instance.aircraft_type_id)
    previous = getattr(instance, '_previous_summary_aircraft_id', None)
    if previous:
        batch.aircraft_ids.add(previous)
    return True


@contextmanager
def batch_flight_summaries(user):
    """Finish summaries before the caller's transaction commits; failures roll back."""
    if not connection.in_atomic_block:
        raise RuntimeError('Summary batching requires an atomic transaction.')
    parent = _current_batch.get()
    if parent is not None:
        if parent.user_id != user.pk:
            raise RuntimeError('A summary batch must belong to one account.')
        yield
        return
    batch = SummaryBatch(user.pk)
    token = _current_batch.set(batch)
    try:
        yield
    finally:
        # Exceptions skip the rebuild, but always restore ordinary signal behavior.
        _current_batch.reset(token)
    if batch.aircraft_ids:
        rebuild_flight_summaries(user, batch.aircraft_ids)


def rebuild_flight_summaries(user, aircraft_ids):
    from flights.aircraft_classification import summary_key
    from flights.models import Aircraft, Total
    from flights.signal_stat import stat_update
    from flights.signal_total import total_all_update
    from flights.signal_extra import weight_update, regs_update, power_update, endorsement_update

    aircraft = list(Aircraft.objects.filter(user=user, pk__in=aircraft_ids).order_by('pk'))
    if not aircraft:
        return
    # total_all_update computes all existing category rows in one pass. Ensure
    # every newly imported category exists before that single pass starts.
    keys = {'All'} | {summary_key(item.aircraft_category, item.aircraft_class) for item in aircraft}
    for key in sorted(keys - {None, ''}):
        Total.objects.get_or_create(user=user, total=key)
    instance = SimpleNamespace(user=user, user_id=user.pk, aircraft_type=aircraft[0])
    total_all_update(None, instance)
    for item in aircraft:
        stat_update(None, SimpleNamespace(user=user, user_id=user.pk, aircraft_type=item))
    weight_update(None, instance)
    regs_update(None, instance, using=connection.alias)
    power_update(None, instance)
    endorsement_update(None, instance)
