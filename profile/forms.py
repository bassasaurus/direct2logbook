from django import forms
from accounts.models import Profile


class ProfileForm(forms.ModelForm):

    class Meta:
        model = Profile
        fields = ('company', 'medical_issue_date', 'first_class',
                  'second_class', 'third_class', 'over_40')
