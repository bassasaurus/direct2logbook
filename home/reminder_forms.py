from decimal import Decimal

from django import forms
from django.db.models.functions import Lower

from flights.models import Aircraft
from profile.models import Reminder


class ReminderForm(forms.ModelForm):
    due_date = forms.DateField(
        required=False, input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = Reminder
        fields = ('title', 'kind', 'due_date', 'aircraft', 'crew_position', 'company',
                  'company_start_date', 'company_end_date', 'target_hours')
        labels = {'kind': 'Reminder Type', 'aircraft': 'Aircraft Type', 'crew_position': 'Crew Position',
                  'company_start_date': 'Start date', 'company_end_date': 'End date (optional)'}
        help_texts = {'company_end_date': 'All flights in this date range count. Leave blank for an ongoing job.'}
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'BFR, IPC, etc.'}),
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
        if kind and not cleaned.get('title') and 'title' not in self.errors:
            if kind == Reminder.Kind.EXPIRATION:
                self.add_error('title', 'Enter a title.')
            else:
                existing_title = self.instance.title if self.instance.kind == kind else ''
                cleaned['title'] = existing_title or Reminder.Kind(kind).label
        if kind == Reminder.Kind.EXPIRATION:
            if not cleaned.get('due_date') and 'due_date' not in self.errors:
                self.add_error('due_date', 'Enter an expiration date.')
            cleaned['target_hours'] = None
        elif kind:
            if (cleaned.get('target_hours') or Decimal('0')) <= 0 and 'target_hours' not in self.errors:
                self.add_error('target_hours', 'Enter a target greater than zero.')
            cleaned['due_date'] = None
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
        if set(self.changed_data) - {'title'}:
            reminder.dismissed_key = ''
        reminder.save()
        return reminder
