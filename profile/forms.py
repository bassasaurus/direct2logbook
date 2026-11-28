from logbook.date_fields import NamedDateInput
from django import forms
from .models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('company',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['company'].required = True


class MedicalForm(forms.ModelForm):
    medical_issue_date = forms.DateField(
        input_formats=['%b %d, %Y', '%B %d, %Y', '%d/%m/%Y', '%Y-%m-%d'],
        widget=NamedDateInput(format='%b %d, %Y', attrs={'placeholder': 'Select date'}),
    )
    class Meta:
        model = Profile
        fields = ('medical_issue_date', 'first_class', 'second_class', 'third_class', 'over_40')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medical_issue_date'].required = True


class CertificatesForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = (
            'student_pilot_certificate', 'sport_pilot_certificate', 'recreational_pilot_certificate',
            'private_pilot_certificate', 'commercial_pilot_certificate', 'atp_certificate',
            'flight_instructor_certificate', 'instrument_instructor', 'multi_engine_instructor',
        )
        labels = {
            'student_pilot_certificate': 'Student Pilot',
            'sport_pilot_certificate': 'Sport Pilot',
            'recreational_pilot_certificate': 'Recreational Pilot',
            'private_pilot_certificate': 'Private Pilot',
            'commercial_pilot_certificate': 'Commercial Pilot',
            'atp_certificate': 'Airline Transport Pilot (ATP)',
            'flight_instructor_certificate': 'Flight Instructor',
            'instrument_instructor': 'Instrument Instructor',
            'multi_engine_instructor': 'Multi-Engine Instructor',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-check-input'

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('instrument_instructor') or cleaned.get('multi_engine_instructor'):
            cleaned['flight_instructor_certificate'] = True
        return cleaned
