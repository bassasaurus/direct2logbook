from django import forms
from .models import Signature


class SignatureForm(forms.ModelForm):
    class Meta:
        model = Signature
        fields = ['signature', 'user']  # Include other fields as needed
