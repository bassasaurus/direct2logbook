from decimal import Decimal

from django import forms

from profile.models import Reminder


class ReminderForm(forms.ModelForm):
    due_date = forms.DateField(
        required=False, input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = Reminder
        fields = ('title', 'kind', 'due_date', 'target_hours')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'BFR, IPC, etc.'}),
            'kind': forms.Select(attrs={'class': 'form-control'}),
            'target_hours': forms.NumberInput(attrs={'min': '0.1', 'step': '0.1', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('kind') == Reminder.Kind.EXPIRATION:
            if not cleaned.get('due_date') and 'due_date' not in self.errors:
                self.add_error('due_date', 'Enter an expiration date.')
            cleaned['target_hours'] = None
        elif cleaned.get('kind') == Reminder.Kind.FLIGHT_TIME:
            if (cleaned.get('target_hours') or Decimal('0')) <= 0 and 'target_hours' not in self.errors:
                self.add_error('target_hours', 'Enter a target greater than zero.')
            cleaned['due_date'] = None
        return cleaned

    def save_for_user(self, user):
        reminder = self.save(commit=False)
        reminder.user = user
        if {'kind', 'due_date', 'target_hours'}.intersection(self.changed_data):
            reminder.dismissed_key = ''
        reminder.save()
        return reminder
