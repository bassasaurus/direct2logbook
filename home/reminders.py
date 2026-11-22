from logbook.date_formats import display_date
"""Evaluate the same reminders for the dashboard and the mobile API."""
from decimal import Decimal, ROUND_HALF_UP

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
        return {'title': 'Medical Certificate', 'message': 'Medical expiration date not recorded.',
                'severity': 'danger', 'banner': True, 'days_remaining': None, 'missing': True}
    today = timezone.localdate()
    days_remaining = (expiry_date - today).days
    severity = ('danger' if (expiry_date.year, expiry_date.month) <= (today.year, today.month) else
                'warning' if days_remaining <= 45 else 'success')
    upcoming = severity == 'warning'
    if upcoming and dismissed_for == expiry_date:
        return None
    status = 'Was due by' if days_remaining < 0 else 'Due by'
    alert = {
        'title': 'Medical Certificate',
        'message': f'{status} {display_date(expiry_date)}.',
        'severity': severity, 'banner': severity != 'success', 'days_remaining': days_remaining,
        'due_date': expiry_date,
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
    if reminder.kind == Reminder.Kind.FLIGHT_CONDITION:
        if reminder.condition not in Reminder.FlightCondition.values:
            return Decimal('0')
        return Total.objects.filter(user=reminder.user_id, total='All').values_list(
            reminder.condition, flat=True).first() or Decimal('0')
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
    if reminder.is_dated:
        return None
    return reminder.milestone_progress_label(milestone_hours(reminder, timezone.localdate()))


def reminder_notice(reminder, today, hours, *, respect_dismissal=True):
    if reminder.kind == Reminder.Kind.IPC:
        from home.currency import instrument_recency
        instrument = instrument_recency(reminder.user_id, ipc=reminder)
        reminder.due_date = instrument['instrument_review_date']
    if not reminder.is_dated:
        if reminder.target_hours is None:
            return None
        key = f'hours:{reminder.target_hours:.1f}'
        remaining = reminder.target_hours - hours
        if remaining <= 0:
            message = f'You reached {reminder.milestone_label()}.'
            severity = 'success'
        elif (remaining <= 10 and (reminder.kind in (Reminder.Kind.FLIGHT_TIME, Reminder.Kind.COMPANY_TIME, Reminder.Kind.FLIGHT_CONDITION) or reminder.aircraft_id)):
            message = f'{remaining:.1f} hours to go. {reminder.milestone_label(hours)}.'
            severity = 'success'
        else:
            return None
    else:
        if reminder.due_date is None:
            return None
        days = (reminder.due_date - today).days
        if days >= 30 and reminder.kind != Reminder.Kind.IPC:
            return None
        stage = 'expired' if days < 0 else 'urgent' if days <= 14 else 'upcoming'
        key = f'date:{reminder.due_date.isoformat()}:{stage}'
        date_label = display_date(reminder.due_date)
        message = (instrument['instrument_status_message'] if reminder.kind == Reminder.Kind.IPC
                   else f'Review overdue since {date_label}.' if days < 0 else f'Review by {date_label}.')
        severity = 'danger' if stage != 'upcoming' else 'warning'
        if reminder.kind == Reminder.Kind.IPC:
            from home.currency import instrument_alert_details
            details = instrument_alert_details(instrument, today)
            message, severity = details['message'], details['severity']
            key = f"date:{reminder.due_date.isoformat()}:{severity}"

    if respect_dismissal and (bool(reminder.dismissed_key) if not reminder.is_dated else key == reminder.dismissed_key):
        return None
    return {'id': reminder.pk, 'key': key,
            'title': (f"IPC — {instrument['instrument_category_label']}" if reminder.kind == Reminder.Kind.IPC else reminder.title),
            'kind': reminder.kind,
            'category': instrument['instrument_category'] if reminder.kind == Reminder.Kind.IPC else None,
            'milestone_state': ('completed' if remaining <= 0 else 'approaching') if not reminder.is_dated else None,
            'banner': reminder.is_dated or remaining <= 0,
            'message': message, 'severity': severity, 'due_date': reminder.due_date if reminder.is_dated else None,
            'holding_warning': instrument['instrument_holding_warning'] if reminder.kind == Reminder.Kind.IPC else None,
            'progress_label': reminder.milestone_progress_label(hours) if hours is not None else None, **reminder_metrics(reminder, today, hours)}


def reminder_rows(user, *, include_saved=False, respect_dismissal=True):
    reminders = sorted(
        Reminder.objects.filter(user=user).select_related('aircraft').order_by('pk'),
        key=lambda reminder: reminder.is_dated,
    )
    today = timezone.localdate()
    all_hours = total_hours(user) if any(r.kind == Reminder.Kind.FLIGHT_TIME for r in reminders) else Decimal('0')
    rows = []
    for reminder in reminders:
        hours = milestone_hours(reminder, today, all_hours) if not reminder.is_dated else None
        notice = reminder_notice(reminder, today, hours, respect_dismissal=respect_dismissal if not (include_saved and reminder.is_dated) else False)
        if include_saved and (reminder.is_dated or not respect_dismissal):
            row = notice or {'id': reminder.pk, 'title': reminder.title, 'kind': reminder.kind,
                             'severity': 'success' if reminder.is_dated else 'neutral'}
            row['progress_label'] = reminder.milestone_progress_label(hours) if hours is not None else None
            row['due_date'] = reminder.due_date
            row.update(reminder_metrics(reminder, today, hours))
            rows.append(row)
        elif notice:
            rows.append(notice)
    return ordered_reminders(rows)


@transaction.atomic
def dismiss_reminder(user, pk, key):
    reminder = get_object_or_404(Reminder.objects.select_for_update(), user=user, pk=pk)
    today = timezone.localdate()
    hours = milestone_hours(reminder, today) if not reminder.is_dated else None
    notice = reminder_notice(reminder, today, hours)
    if notice and notice['key'] == key:
        reminder.dismissed_key = key
        reminder.save(update_fields=['dismissed_key'])


REMINDER_PRIORITY = {'danger': 0, 'warning': 1, 'success': 2, 'neutral': 3}


def reminder_sort_key(row):
    priority = REMINDER_PRIORITY.get(row.get('severity'), 3)
    if row.get('medical') and row.get('missing'):
        return (priority, -1, 0, Decimal('0'))
    if row.get('days_remaining') is not None:
        return (priority, 0, row['days_remaining'], Decimal('0'))
    if row.get('milestone_state') in ('completed', 'approaching'):
        return (priority, 1, -1 if row['milestone_state'] == 'completed' else 0, Decimal(row.get('hours_remaining') or '0'))
    if row.get('completion_percent') is not None:
        return (priority, 1, -Decimal(row['completion_percent']), Decimal(row.get('hours_remaining') or '0'))
    return (priority, 2, 0, Decimal('0'))


def ordered_reminders(rows):
    return sorted(rows, key=reminder_sort_key)


def reminder_metrics(reminder, today, hours):
    if reminder.is_dated:
        return {'days_remaining': (reminder.due_date - today).days if reminder.due_date else None,
                'completion_percent': None, 'hours_remaining': None}
    if reminder.target_hours is None or reminder.target_hours <= 0 or hours is None:
        return {'days_remaining': None, 'completion_percent': None, 'hours_remaining': None}
    target, current = Decimal(str(reminder.target_hours)), Decimal(str(hours))
    percent = max(Decimal('0'), current / target * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    percent = min(percent, Decimal('100.0') if current >= target else Decimal('99.9'))
    return {'days_remaining': None, 'completion_percent': str(percent),
            'hours_remaining': str(max(Decimal('0'), target - current))}


def reminder_presentation(reminder):
    today = timezone.localdate()
    hours = milestone_hours(reminder, today) if not reminder.is_dated else None
    notice = reminder_notice(reminder, today, hours, respect_dismissal=False)
    return {
        'milestone_state': notice.get('milestone_state') if notice else 'inactive' if not reminder.is_dated else None,
        'banner': notice.get('banner', True) if notice else reminder.is_dated,
        'severity': notice['severity'] if notice else 'success' if hours is None else 'neutral',
        'status_message': notice['message'] if notice and reminder.kind == Reminder.Kind.IPC else None,
        'holding_warning': notice.get('holding_warning') if notice else None,
        'progress_label': reminder.milestone_progress_label(hours) if hours is not None else None,
        **reminder_metrics(reminder, today, hours),
    }


def reminder_groups(rows):
    """Keep date-based regulatory reminders separate from flight-hour goals."""
    groups = [{'key': 'regulatory', 'title': 'Reminders', 'rows': []},
              {'key': 'milestones', 'title': 'Milestones', 'rows': []}]
    for row in rows:
        saved = row.get('reminder')
        kind = saved.kind if saved is not None else row.get('kind')
        regulatory = row.get('medical') or kind in (Reminder.Kind.EXPIRATION, Reminder.Kind.FLIGHT_REVIEW, Reminder.Kind.INSTRUCTOR_RENEWAL, Reminder.Kind.IPC)
        groups[0 if regulatory else 1]['rows'].append(row)
    return groups


def web_reminder_key(notice):
    if not notice.get('medical') and notice.get('kind') in ('expiration', 'flight_review', 'instructor_renewal', 'ipc'):
        from home.regulatory_preferences import key_for
        return key_for(notice)
    return 'ifr' if notice.get('kind') == 'ipc' else 'medical' if notice.get('medical') else str(notice['id'])


def web_reminder_token(user, notice):
    from django.core.signing import Signer
    return Signer(salt='web-reminder').sign_object({
        'user': user.pk, 'id': web_reminder_key(notice), 'title': notice.get('title', 'Medical Certificate'),
        'due': str(notice['due_date']) if notice.get('due_date') else None, 'severity': notice.get('severity'),
        'generation': notice.get('preference_generation', 0),
    })


def web_reminder_hidden(preferences, notice, today):
    if notice.get('milestone_state'):
        return False  # Milestones use account-backed Dismiss, never legacy timed snoozes.
    if not notice.get('medical') and notice.get('kind') in ('expiration', 'flight_review', 'instructor_renewal', 'ipc'):
        from home.regulatory_preferences import hidden, key_for
        return hidden(preferences.get(key_for(notice)), notice, today)
    preference = preferences.get(web_reminder_key(notice), {})
    if (notice.get('medical') and notice['severity'] == 'warning'
            and preference.get('caution_due') == str(notice.get('due_date'))):
        return True
    return preference.get('dismissed', False) or preference.get('until', '') > today.isoformat()
