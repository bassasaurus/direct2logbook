from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from profile.models import Reminder
from home.currency import medical_expiry_date
from .reminder_forms import RegulatoryReminderForm, MilestoneForm
from .reminders import dismiss_medical_warning, dismiss_reminder, medical_expiration_alert, ordered_reminders, reminder_presentation, reminder_groups


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def manage_reminders(request, pk=None, reminder_kind=None):
    reminders = Reminder.objects.filter(user=request.user)
    editable = reminders.select_for_update() if request.method == 'POST' else reminders
    reminder = get_object_or_404(editable, pk=pk) if pk is not None else None
    if reminder_kind in (Reminder.Kind.INSTRUCTOR_RENEWAL, Reminder.Kind.FLIGHT_REVIEW, Reminder.Kind.IPC) and reminder is None:
        reminder = editable.filter(kind=reminder_kind).order_by('-pk').first()
    selected_kind = request.POST.get('kind') or (reminder.kind if reminder else reminder_kind or request.GET.get('kind'))
    inferred_group = 'milestones' if selected_kind in (
        Reminder.Kind.FLIGHT_TIME, Reminder.Kind.TIME_IN_TYPE, Reminder.Kind.CREW_IN_TYPE, Reminder.Kind.COMPANY_TIME, Reminder.Kind.FLIGHT_CONDITION,
    ) else 'regulatory'
    group = inferred_group if reminder else request.POST.get('reminder_group') or request.GET.get('group') or inferred_group
    if group not in ('regulatory', 'milestones'):
        group = inferred_group
    form_class = RegulatoryReminderForm if group == 'regulatory' else MilestoneForm
    form = form_class(request.POST if request.method == 'POST' else None, instance=reminder, user=request.user,
                      initial={'kind': selected_kind} if selected_kind in Reminder.Kind.values else None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                form.save_for_user(request.user)
        except DatabaseError as error:
            from logbook.db_errors import database_feedback, logger
            logger.exception('Database failure saving reminder')
            feedback, _ = database_feedback(error, 'reminder')
            for field, messages in feedback.items():
                for message in messages:
                    form.add_error(field if field in form.fields else None, message)
        else:
            if request.POST.get('reminder_group') or request.GET.get('group'):
                return redirect(reverse('manage_reminders') + '?group=' + group)
            return redirect('manage_reminders')
    saved_reminders = reminders.select_related('aircraft').order_by('pk')
    for saved_reminder in saved_reminders:
        presentation = reminder_presentation(saved_reminder)
        saved_reminder.progress_label = presentation['progress_label']
        saved_reminder.status_message = presentation.get('status_message')
        saved_reminder.holding_warning = presentation.get('holding_warning')
        saved_reminder.severity = presentation['severity']
        saved_reminder.presentation = presentation
    medical_status = medical_expiration_alert(medical_expiry_date(request.user.profile))
    cards = [{'reminder': reminder, **reminder.presentation} for reminder in saved_reminders]
    cards.insert(0, {**(medical_status or {}), 'medical': True, 'severity': medical_status['severity'] if medical_status else 'neutral',
                  'plain': not medical_status or not medical_status['banner']})
    return render(request, 'home/reminders.html', {
        'form_group': group,
        'form_group_title': dict(form.fields['kind'].choices).get(form['kind'].value(), 'Reminder' if group == 'regulatory' else 'Milestone'),
        'form': form, 'reminders': saved_reminders, 'editing': reminder, 'reminder_cards': ordered_reminders(cards),
        'reminder_groups': [section for section in reminder_groups(ordered_reminders([card for card in cards if not card.get('medical')])) if section['key'] == group],
        'web_hidden_reminders': hidden_web_reminders(request.user),
        'medical_status': medical_status,
        'medical_profile': request.user.profile, 'medical_due_date': medical_expiry_date(request.user.profile),
        'title': 'D-> | Reminders',
        'page_title': 'Reminders',
        'parent_link': reverse('home'), 'parent_name': 'Home',
    })


@login_required
@require_POST
def remove_reminder(request, pk):
    get_object_or_404(Reminder, user=request.user, pk=pk).delete()
    return redirect('manage_reminders')


@login_required
@require_POST
def dismiss_dashboard_reminder(request, pk):
    dismiss_reminder(request.user, pk, request.POST.get('key'))
    return redirect('home')


@login_required
@require_POST
def dismiss_dashboard_medical_warning(request):
    dismiss_medical_warning(request.user, request.POST.get('key'))
    return redirect('home')


@login_required
@require_POST
def restore_dashboard_reminder(request, pk):
    reminder = get_object_or_404(Reminder, user=request.user, pk=pk)
    Reminder.objects.filter(user=request.user, pk=reminder.pk).update(dismissed_key='')
    return redirect('manage_reminders')


@login_required
@require_POST
@transaction.atomic
def web_reminder_action(request):
    from datetime import timedelta
    from django.core.signing import BadSignature, Signer
    from django.utils import timezone
    from profile.models import Profile
    try:
        notice = Signer(salt='web-reminder').unsign_object(request.POST.get('key', ''))
    except (BadSignature, ValueError, TypeError):
        return redirect('home')
    if not isinstance(notice, dict) or notice.get('user') != request.user.pk:
        return redirect('home')
    profile = Profile.objects.select_for_update().get(user=request.user)
    preferences = dict(profile.web_reminder_preferences)
    key = notice['id']
    action = request.POST.get('action')
    if action == 'snooze':
        action = request.POST.get('days')
    if action == 'restore':
        preferences.pop(key, None)
    elif action == 'dismiss' and key == 'ifr':
        preferences[key] = {'dismissed': True, 'title': notice['title']}
    elif action in ('1', '3', '7', '14', '30'):
        preferences[key] = {'until': (timezone.localdate() + timedelta(days=int(action))).isoformat(),
                            'title': notice['title']}
    else:
        return redirect('home')
    profile.web_reminder_preferences = preferences
    profile.save(update_fields=['web_reminder_preferences'])
    return redirect('manage_reminders' if action == 'restore' else 'home')


def hidden_web_reminders(user):
    from django.core.signing import Signer
    from django.utils import timezone
    rows = []
    for key, preference in user.profile.web_reminder_preferences.items():
        if preference.get('dismissed') or preference.get('until', '') > timezone.localdate().isoformat():
            rows.append({**preference, 'token': Signer(salt='web-reminder').sign_object({
                'user': user.pk, 'id': key, 'title': preference['title']})})
    return rows
