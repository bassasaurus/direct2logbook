from django import forms
from .models import Profile


class ProfileForm(forms.ModelForm):

    class Meta:
        model = Profile
        fields = ('company', 'medical_issue_date', 'first_class',
                  'second_class', 'third_class', 'over_40')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medical_issue_date'].required = True
        self.fields['company'].required = True
