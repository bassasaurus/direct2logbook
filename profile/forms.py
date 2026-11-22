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
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={'placeholder': 'dd/mm/yyyy'}),
    )
    class Meta:
        model = Profile
        fields = ('medical_issue_date', 'first_class', 'second_class', 'third_class', 'over_40')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medical_issue_date'].required = True
