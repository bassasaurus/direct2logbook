from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from profile.models import Reminder
from .reminder_forms import ReminderForm
from .reminders import dismiss_medical_warning, dismiss_reminder, milestone_progress_label


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def manage_reminders(request, pk=None):
    reminders = Reminder.objects.filter(user=request.user)
    editable = reminders.select_for_update() if request.method == 'POST' else reminders
    reminder = get_object_or_404(editable, pk=pk) if pk is not None else None
    form = ReminderForm(request.POST if request.method == 'POST' else None, instance=reminder, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save_for_user(request.user)
        return redirect('manage_reminders')
    saved_reminders = reminders.select_related('aircraft').order_by('pk')
    for saved_reminder in saved_reminders:
        saved_reminder.progress_label = milestone_progress_label(saved_reminder)
    return render(request, 'home/reminders.html', {
        'form': form, 'reminders': saved_reminders, 'editing': reminder,
        'title': 'D-> | Reminders', 'page_title': 'Reminders',
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
