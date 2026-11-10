from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from profile.models import Reminder
from .reminder_forms import ReminderForm
from .reminders import dismiss_reminder


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def manage_reminders(request, pk=None):
    reminders = Reminder.objects.filter(user=request.user)
    editable = reminders.select_for_update() if request.method == 'POST' else reminders
    reminder = get_object_or_404(editable, pk=pk) if pk is not None else None
    form = ReminderForm(request.POST if request.method == 'POST' else None, instance=reminder)
    if request.method == 'POST' and form.is_valid():
        form.save_for_user(request.user)
        return redirect('manage_reminders')
    return render(request, 'home/reminders.html', {
        'form': form, 'reminders': reminders.order_by('pk'), 'editing': reminder,
        'title': 'D-> | Reminders', 'page_title': 'Reminders',
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
