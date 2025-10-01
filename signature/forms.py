from django import forms
from .models import Signature


class SignatureForm(forms.ModelForm):
    class Meta:
        model = Signature
        exclude = ['user']
        fields = ['signature']  # Include other fields as needed
