"""Evaluate the same reminders for the dashboard and the mobile API."""
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from flights.models import Total
from profile.models import Reminder


def total_hours(user):
    return Total.objects.filter(user=user, total='All').values_list('total_time', flat=True).first() or Decimal('0')


def reminder_notice(reminder, today, hours):
    if reminder.kind == Reminder.Kind.FLIGHT_TIME:
        if reminder.target_hours is None or hours < reminder.target_hours:
            return None
        key = f'hours:{reminder.target_hours:.1f}'
        message = f'You reached {reminder.target_hours:.1f} total flight hours.'
        severity = 'success'
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
    return {'id': reminder.pk, 'key': key, 'title': reminder.title,
            'message': message, 'severity': severity}


def active_reminders(user):
    reminders = sorted(
        Reminder.objects.filter(user=user).order_by('pk'),
        key=lambda reminder: reminder.kind != Reminder.Kind.FLIGHT_TIME,
    )
    today = timezone.localdate()
    hours = total_hours(user) if any(r.kind == Reminder.Kind.FLIGHT_TIME for r in reminders) else Decimal('0')
    return [notice for reminder in reminders if (notice := reminder_notice(reminder, today, hours))]


@transaction.atomic
def dismiss_reminder(user, pk, key):
    reminder = get_object_or_404(Reminder.objects.select_for_update(), user=user, pk=pk)
    hours = total_hours(user) if reminder.kind == Reminder.Kind.FLIGHT_TIME else Decimal('0')
    notice = reminder_notice(reminder, timezone.localdate(), hours)
    if notice and notice['key'] == key:
        reminder.dismissed_key = key
        reminder.save(update_fields=['dismissed_key'])
