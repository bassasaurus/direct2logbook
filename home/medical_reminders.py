"""Shared medical alert visibility and account preferences."""
from datetime import timezone as utc_timezone
from django.utils import timezone
from home.currency import medical_expiry_date
from home.reminders import medical_expiration_alert, web_reminder_hidden


def medical_card(profile):
    due = medical_expiry_date(profile)
    alert = medical_expiration_alert(due)
    medical = {key: getattr(profile, key) for key in ('first_class', 'second_class', 'third_class', 'over_40')}
    medical['medical_issue_date'] = profile.medical_issue_date.isoformat() if profile.medical_issue_date else None
    return {**alert, 'medical': medical, 'medical_due_date': due.isoformat() if due else None,
            'medical_severity': alert['severity'], 'medical_banner': alert['banner'],
            'medical_missing': bool(alert.get('missing'))}


def medical_hidden(profile, alert):
    today = timezone.localdate(timezone=utc_timezone.utc)
    row = {**alert, 'medical': True}
    return web_reminder_hidden(profile.web_reminder_preferences, row, today) or (
        alert['severity'] == 'warning' and profile.medical_warning_dismissed_for == medical_expiry_date(profile))


def medical_generation(profile):
    return profile.web_reminder_preferences.get('_medical_generation', {}).get('value', 0)


def medical_preference(profile):
    preference = profile.web_reminder_preferences.get('medical', {})
    if not preference and profile.medical_warning_dismissed_for:
        return {'caution_due': profile.medical_warning_dismissed_for.isoformat()}
    return preference


def clear_medical_preferences(profile, invalidate=True):
    profile.web_reminder_preferences = {key: value for key, value in profile.web_reminder_preferences.items() if key != 'medical'}
    if invalidate:
        profile.web_reminder_preferences['_medical_generation'] = {'value': medical_generation(profile) + 1}
    profile.medical_warning_dismissed_for = None
    profile.save(update_fields=['web_reminder_preferences', 'medical_warning_dismissed_for'])
