"""Account-owned removal shared by web and mobile."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from profile.models import Profile, Reminder


@transaction.atomic
def remove_saved_reminder(user, pk):
    profile = Profile.objects.select_for_update().get(user=user)
    reminder = get_object_or_404(Reminder.objects.select_for_update(), user=user, pk=pk)
    milestone = reminder.kind not in ('expiration', 'flight_review', 'instructor_renewal', 'ipc')
    if not milestone:
        from home.regulatory_preferences import clear_for_edit
        clear_for_edit(reminder)
        profile.refresh_from_db()
    reminder.delete()
    preferences = dict(profile.web_reminder_preferences)
    if str(pk) in preferences:
        preferences.pop(str(pk))
        profile.web_reminder_preferences = preferences
        profile.save(update_fields=['web_reminder_preferences'])
    return 'milestones' if milestone else 'regulatory'
