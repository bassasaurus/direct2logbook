"""Calendar-month currency for user-recorded qualifying events under 14 CFR 61.56."""
import calendar
from datetime import date
from django.utils import timezone


def flight_review_due_date(completed):
    if completed is None:
        return None
    return calendar_month_due_date(completed, 24)


def flight_review_currency(user):
    from profile.models import Reminder
    reminder = Reminder.objects.filter(user=user, kind=Reminder.Kind.FLIGHT_REVIEW).order_by('-last_qualifying_date', '-pk').first()
    if not reminder or not reminder.last_qualifying_date:
        return None
    due = flight_review_due_date(reminder.last_qualifying_date)
    return {'reminder': reminder, 'last_qualifying_date': reminder.last_qualifying_date,
            'completion_type': reminder.get_completion_type_display(), 'due_date': due,
            'current': timezone.localdate() <= due}


def calendar_month_due_date(completed, months):
    if completed is None:
        return None
    index = completed.year * 12 + completed.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, calendar.monthrange(year, month)[1])
