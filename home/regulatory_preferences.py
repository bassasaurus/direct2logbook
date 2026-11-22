"""Account-backed regulatory alert actions, with UTC calendar-day expiry."""
from datetime import timedelta, timezone as utc_timezone
from django.db import transaction
from django.utils import timezone
from profile.models import Profile, Reminder

KINDS = ('expiration', 'flight_review', 'instructor_renewal', 'ipc')


def key_for(row):
    return 'ifr:' + (row.get('category') or row.get('ipc_category') or '') if row.get('kind') == 'ipc' else 'regulatory:' + str(row['id'])


def generation(profile, key):
    return profile.web_reminder_preferences.get('_regulatory_generations', {}).get(key, 0)


def snapshot(profile):
    return {'preferences': {key: value for key, value in profile.web_reminder_preferences.items()
                            if key.startswith(('regulatory:', 'ifr:'))},
            'generations': profile.web_reminder_preferences.get('_regulatory_generations', {})}


def hidden(preference, row, today=None):
    today = today or timezone.localdate(timezone=utc_timezone.utc)
    if not preference or preference.get('due') != (str(row['due_date']) if row.get('due_date') else None):
        return False
    if preference.get('severity') == 'warning' and row.get('severity') == 'danger':
        return False
    if preference.get('mode') == 'until_red':
        return row.get('severity') == 'warning'
    return preference.get('until', '') > today.isoformat()


def annotate(profile, row):
    if row.get('medical') or row.get('kind') not in KINDS:
        return row
    key = key_for(row)
    return {**row, 'preference_key': key, 'preference_generation': generation(profile, key)}


def notices(user):
    from home.reminders import reminder_rows
    from home.currency import instrument_recency_categories, instrument_currency_notice
    rows = [row for row in reminder_rows(user, respect_dismissal=False) if row.get('kind') in KINDS]
    rows += [notice for item in instrument_recency_categories(user)
             if (notice := instrument_currency_notice(user, item))]
    return rows


@transaction.atomic
def apply_action(user, key, action, expected_generation, due=None, severity=None, until=None):
    profile = Profile.objects.select_for_update().get(user=user)
    values = dict(profile.web_reminder_preferences)
    if expected_generation != generation(profile, key):
        return snapshot(profile)
    row = next((row for row in notices(user) if key_for(row) == key), None)
    if row is None:
        # A removed record cannot be resurrected by an offline action.
        return snapshot(profile)
    if action == 'restore':
        values.pop(key, None)
    else:
        if due != (str(row['due_date']) if row.get('due_date') else None) or severity != row['severity']:
            return snapshot(profile)
        if severity not in ('warning', 'danger'):
            raise ValueError('This reminder does not need an alert action.')
        today = timezone.localdate(timezone=utc_timezone.utc)
        preference = {'title': row['title'], 'due': due, 'severity': severity}
        if action == 'dismiss' and severity == 'warning':
            preference['mode'] = 'until_red'
        elif action in ('snooze', 'dismiss'):
            if not until or until > today + timedelta(days=30 if action == 'dismiss' else 14):
                raise ValueError('Choose a valid reminder return date.')
            if until <= today:
                values.pop(key, None)
                profile.web_reminder_preferences = values
                profile.save(update_fields=['web_reminder_preferences'])
                return snapshot(profile)
            preference.update(mode='until', until=until.isoformat())
        else:
            raise ValueError('Choose Snooze, Dismiss, or Restore.')
        values[key] = preference
    profile.web_reminder_preferences = values
    profile.save(update_fields=['web_reminder_preferences'])
    return snapshot(profile)


@transaction.atomic
def clear_for_edit(reminder, previous_key=None):
    profile = Profile.objects.select_for_update().get(user_id=reminder.user_id)
    row = {'id': reminder.pk, 'kind': reminder.kind, 'ipc_category': reminder.ipc_category}
    key = key_for(row)
    values = dict(profile.web_reminder_preferences)
    versions = dict(values.get('_regulatory_generations', {}))
    for resource in {key, previous_key} - {None}:
        values.pop(resource, None)
        versions[resource] = versions.get(resource, 0) + 1
    values['_regulatory_generations'] = versions
    profile.web_reminder_preferences = values
    profile.save(update_fields=['web_reminder_preferences'])
