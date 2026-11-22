from decimal import Decimal

from django import forms
from django.db.models.functions import Lower

from flights.models import Aircraft
from profile.models import Reminder
from django.utils import timezone
from home.flight_reviews import flight_review_due_date, calendar_month_due_date


class ReminderForm(forms.ModelForm):
    due_date = forms.DateField(
        required=False, input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
    )

    last_qualifying_date = forms.DateField(
        required=False, input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
    )

    instructor_period_start = forms.DateField(required=False, input_formats=['%Y-%m-%d'],
        label='Recent Experience Period Start Date',
        help_text='Use the start month on your recent-experience record, including the retained month after early renewal. Review scheduled at month-end, 24 months later.',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}))
    ipc_completed_date = forms.DateField(required=False, input_formats=['%Y-%m-%d'], label='IPC Completion Date',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}))

    class Meta:
        model = Reminder
        fields = ('title', 'kind', 'due_date', 'aircraft', 'crew_position', 'company',
                  'company_start_date', 'company_end_date', 'target_hours', 'last_qualifying_date', 'completion_type', 'condition', 'instructor_period_start', 'ipc_completed_date', 'ipc_category')
        labels = {'kind': 'Reminder Type', 'aircraft': 'Aircraft Type', 'crew_position': 'Crew Position',
                  'last_qualifying_date': 'Last Qualifying Date', 'completion_type': 'Completion Type', 'condition': 'Flight Condition', 'ipc_completed_date': 'IPC Completion Date', 'instructor_period_start': 'Recent Experience Period Start Date',
                  'company_start_date': 'Start date', 'company_end_date': 'End date (optional)'}
        help_texts = {'instructor_period_start': 'Use the start month on your recent-experience record. This may be the retained prior due month after early renewal. Due at month-end, 24 months later; this is a recent-experience deadline, not certificate expiration.','completion_type': 'Select only a qualifying event under 14 CFR 61.56. WINGS requires a completed phase, not individual credits.',
                      'company_end_date': 'All flights in this date range count. Leave blank for an ongoing job.'}
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'BFR, IPC, etc.'}),
            'completion_type': forms.Select(attrs={'class': 'form-control'}),
            'instructor_period_start': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'ipc_completed_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'kind': forms.Select(attrs={'class': 'form-control'}),
            'aircraft': forms.Select(attrs={'class': 'form-control'}),
            'crew_position': forms.Select(attrs={'class': 'form-control'}),
            'company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter company name'}),
            'company_start_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'company_end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'target_hours': forms.NumberInput(attrs={'min': '0.1', 'step': '0.1', 'class': 'form-control'}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['title'].required = False
        self.fields['aircraft'].queryset = Aircraft.objects.filter(user=user).order_by(Lower('aircraft_type'), 'pk')
        if self.instance._state.adding and not self.is_bound:
            profile = getattr(user, 'profile', None)
            company = profile.company.strip() if profile else ''
            if company:
                self.initial.setdefault('company', company)
            else:
                self.fields['company'].help_text = 'Add a company in your profile to prefill future milestones.'

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get('kind')
        if kind == Reminder.Kind.EXPIRATION:
            if not cleaned.get('title') and 'title' not in self.errors:
                self.add_error('title', 'Enter a title.')
        elif kind:
            cleaned['title'] = dict(RegulatoryReminderForm.type_choices).get(kind, Reminder.Kind(kind).label)
        if kind == Reminder.Kind.IPC:
            if not cleaned.get('ipc_category'):
                self.add_error('ipc_category', 'Choose the IPC aircraft category.')
            completed = cleaned.get('ipc_completed_date')
            if not completed and 'ipc_completed_date' not in self.errors:
                self.add_error('ipc_completed_date', 'Enter the IPC completion date.')
            elif completed:
                if completed > timezone.localdate():
                    self.add_error('ipc_completed_date', 'The completion date cannot be in the future.')
                else:
                    cleaned['due_date'] = calendar_month_due_date(completed, 6)
            cleaned['target_hours'] = None
        elif kind == Reminder.Kind.INSTRUCTOR_RENEWAL:
            start = cleaned.get('instructor_period_start')
            if not start and 'instructor_period_start' not in self.errors:
                self.add_error('instructor_period_start', 'Enter the recent-experience period start date.')
            elif start:
                try:
                    cleaned['due_date'] = flight_review_due_date(start)
                except ValueError:
                    self.add_error('instructor_period_start', 'Enter a valid period start date.')
            cleaned['target_hours'] = None
        elif kind == Reminder.Kind.FLIGHT_REVIEW:
            completed = cleaned.get('last_qualifying_date')
            if not completed and 'last_qualifying_date' not in self.errors:
                self.add_error('last_qualifying_date', 'Enter the last qualifying completion date.')
            elif completed:
                if completed > timezone.localdate():
                    self.add_error('last_qualifying_date', 'The completion date cannot be in the future.')
                else:
                    cleaned['due_date'] = flight_review_due_date(completed)
            if not cleaned.get('completion_type') and 'completion_type' not in self.errors:
                self.add_error('completion_type', 'Choose the qualifying completion type.')
            if Reminder.objects.filter(user=self.user, kind=kind).exclude(pk=self.instance.pk).exists():
                self.add_error('kind', 'A Flight Review reminder already exists. Edit it to record your latest qualifying event.')
            cleaned['target_hours'] = None
        elif kind == Reminder.Kind.EXPIRATION:
            if not cleaned.get('due_date') and 'due_date' not in self.errors:
                self.add_error('due_date', 'Enter an expiration date.')
            cleaned['target_hours'] = None
        elif kind:
            if (cleaned.get('target_hours') or Decimal('0')) <= 0 and 'target_hours' not in self.errors:
                self.add_error('target_hours', 'Target hours must be greater than 0.')
            cleaned['due_date'] = None
        if kind != Reminder.Kind.IPC:
            cleaned['ipc_category'] = ''
            cleaned['ipc_completed_date'] = None
        if kind != Reminder.Kind.INSTRUCTOR_RENEWAL:
            cleaned['instructor_period_start'] = None
        if kind != Reminder.Kind.FLIGHT_REVIEW:
            cleaned['last_qualifying_date'] = None
            cleaned['completion_type'] = ''
        if kind == Reminder.Kind.FLIGHT_CONDITION:
            if not cleaned.get('condition') and 'condition' not in self.errors:
                self.add_error('condition', 'Choose a flight condition.')
        else:
            cleaned['condition'] = ''
        if kind in (Reminder.Kind.TIME_IN_TYPE, Reminder.Kind.CREW_IN_TYPE):
            if not cleaned.get('aircraft') and 'aircraft' not in self.errors:
                self.add_error('aircraft', 'Choose an aircraft type.')
        else:
            cleaned['aircraft'] = None
        if kind == Reminder.Kind.CREW_IN_TYPE:
            if not cleaned.get('crew_position') and 'crew_position' not in self.errors:
                self.add_error('crew_position', 'Choose a crew position.')
        else:
            cleaned['crew_position'] = ''
        if kind == Reminder.Kind.COMPANY_TIME:
            if not cleaned.get('company') and 'company' not in self.errors:
                self.add_error('company', 'Enter a company name.')
            start = cleaned.get('company_start_date')
            end = cleaned.get('company_end_date')
            if not start and 'company_start_date' not in self.errors:
                self.add_error('company_start_date', 'Enter a start date.')
            if start and end and end < start:
                self.add_error('company_end_date', 'End date must be on or after the start date.')
        else:
            cleaned['company'] = ''
            cleaned['company_start_date'] = None
            cleaned['company_end_date'] = None
        return cleaned

    def save_for_user(self, user):
        reminder = self.save(commit=False)
        reminder.user = user
        reminder.dismissed_key = ''
        reminder.save()
        return reminder


class RegulatoryReminderForm(ReminderForm):
    type_choices = (
        (Reminder.Kind.EXPIRATION, 'Custom'),
        (Reminder.Kind.FLIGHT_REVIEW, 'BFR'),
        (Reminder.Kind.IPC, 'IPC'),
        (Reminder.Kind.INSTRUCTOR_RENEWAL, 'FIRC'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kind'].choices = self.type_choices
        self.order_fields(['kind', 'title'])
        self.fields['kind'].label = 'Reminder Type'
        self.fields['title'].widget.attrs['placeholder'] = 'Reminder title'
        self.fields['instructor_period_start'].help_text = ''
        self.initial.setdefault('kind', Reminder.Kind.EXPIRATION)


class MilestoneForm(ReminderForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kind'].choices = [choice for choice in Reminder.Kind.choices
                                       if choice[0] not in (Reminder.Kind.EXPIRATION, Reminder.Kind.FLIGHT_REVIEW, Reminder.Kind.INSTRUCTOR_RENEWAL, Reminder.Kind.IPC)]
        self.order_fields(['kind', 'title'])
        self.fields['kind'].label = 'Milestone Type'
        self.initial.setdefault('kind', Reminder.Kind.FLIGHT_TIME)
