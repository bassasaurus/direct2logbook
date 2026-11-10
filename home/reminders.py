"""Evaluate the same reminders for the dashboard and the mobile API."""
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from flights.models import Flight, Stat, Total
from flights.queryset_helpers import avoid_none
from home.currency import medical_expiry_date
from profile.models import Profile, Reminder


def total_hours(user):
    return Total.objects.filter(user=user, total='All').values_list('total_time', flat=True).first() or Decimal('0')


def medical_expiration_alert(expiry_date, dismissed_for=None):
    if expiry_date is None:
        return None
    days_remaining = (expiry_date - timezone.localdate()).days
    if days_remaining > 60:
        return None
    upcoming = days_remaining > 30
    if upcoming and dismissed_for == expiry_date:
        return None
    status = 'Expired' if days_remaining < 0 else 'Expires'
    alert = {
        'title': 'Medical certificate',
        'message': f'{status} {expiry_date:%b %d, %Y}.',
        'severity': 'warning' if upcoming else 'danger',
    }
    if upcoming:
        alert['key'] = expiry_date.isoformat()
    return alert


@transaction.atomic
def dismiss_medical_warning(user, key):
    profile = Profile.objects.select_for_update().get(user=user)
    expiry_date = medical_expiry_date(profile)
    alert = medical_expiration_alert(expiry_date, profile.medical_warning_dismissed_for)
    if alert and 'key' in alert and alert['key'] == key:
        profile.medical_warning_dismissed_for = expiry_date
        profile.save(update_fields=['medical_warning_dismissed_for'])
        return None
    return alert


def milestone_hours(reminder, today, all_hours=None):
    if reminder.kind == Reminder.Kind.FLIGHT_TIME:
        return total_hours(reminder.user_id) if all_hours is None else all_hours
    if reminder.kind == Reminder.Kind.COMPANY_TIME:
        if not reminder.company_start_date:
            return Decimal('0')
        end = reminder.company_end_date or today
        flights = Flight.objects.filter(user=reminder.user_id, date__range=(reminder.company_start_date, end))
        return avoid_none(flights, 'duration')
    if not reminder.aircraft_id:
        return Decimal('0')
    field = 'total_time'
    if reminder.kind == Reminder.Kind.CREW_IN_TYPE:
        field = reminder.crew_position
        if field not in Reminder.CrewPosition.values:
            return Decimal('0')
    return Stat.objects.filter(
        user=reminder.user_id, aircraft_type=reminder.aircraft.aircraft_type,
    ).values_list(field, flat=True).first() or Decimal('0')


def milestone_progress_label(reminder):
    if reminder.kind == Reminder.Kind.EXPIRATION:
        return None
    return reminder.milestone_label(milestone_hours(reminder, timezone.localdate()))


def reminder_notice(reminder, today, hours):
    if reminder.kind != Reminder.Kind.EXPIRATION:
        if reminder.target_hours is None:
            return None
        key = f'hours:{reminder.target_hours:.1f}'
        remaining = reminder.target_hours - hours
        if remaining <= 0:
            message = f'You reached {reminder.milestone_label()}.'
            severity = 'success'
        elif (remaining <= 10 and reminder.dismissed_key != key
              and (reminder.kind in (Reminder.Kind.FLIGHT_TIME, Reminder.Kind.COMPANY_TIME) or reminder.aircraft_id)):
            key = f'{key}:approaching'
            message = f'{remaining:.1f} hours to go. {reminder.milestone_label(hours)}.'
            severity = 'warning'
        else:
            return None
    else:
        if reminder.due_date is None:
            return None
        days = (reminder.due_date - today).days
        if days > 30:
            return None
        stage = 'expired' if days < 0 else 'urgent' if days <= 7 else 'upcoming'
        key = f'date:{reminder.due_date.isoformat()}:{stage}'
        date_label = reminder.due_date.strftime('%b %d, %Y')
        message = f'Expired {date_label}.' if days < 0 else f'Due {date_label}.'
        severity = 'danger' if stage != 'upcoming' else 'warning'

    if key == reminder.dismissed_key:
        return None
    return {'id': reminder.pk, 'key': key, 'title': reminder.title, 'kind': reminder.kind,
            'message': message, 'severity': severity}


def reminder_rows(user, *, include_saved=False):
    reminders = sorted(
        Reminder.objects.filter(user=user).select_related('aircraft').order_by('pk'),
        key=lambda reminder: reminder.kind == Reminder.Kind.EXPIRATION,
    )
    today = timezone.localdate()
    all_hours = total_hours(user) if any(r.kind == Reminder.Kind.FLIGHT_TIME for r in reminders) else Decimal('0')
    rows = []
    for reminder in reminders:
        hours = milestone_hours(reminder, today, all_hours) if reminder.kind != Reminder.Kind.EXPIRATION else None
        notice = reminder_notice(reminder, today, hours)
        if include_saved:
            row = notice or {'id': reminder.pk, 'title': reminder.title, 'kind': reminder.kind}
            row['progress_label'] = reminder.milestone_label(hours) if hours is not None else None
            row['due_date'] = reminder.due_date
            rows.append(row)
        elif notice:
            rows.append(notice)
    return rows


@transaction.atomic
def dismiss_reminder(user, pk, key):
    reminder = get_object_or_404(Reminder.objects.select_for_update(), user=user, pk=pk)
    today = timezone.localdate()
    hours = milestone_hours(reminder, today) if reminder.kind != Reminder.Kind.EXPIRATION else None
    notice = reminder_notice(reminder, today, hours)
    if notice and notice['key'] == key:
        reminder.dismissed_key = key
        reminder.save(update_fields=['dismissed_key'])
