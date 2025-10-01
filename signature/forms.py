from django import forms
from .models import Signature
from signature_pad import SignaturePadWidget


class SignatureForm(forms.ModelForm):

    signature = forms.CharField(
        widget=SignaturePadWidget(
            dotSize=2.5,
            minWidth=1.0,
            maxWidth=4.0,
            backgroundColor="rgb(240, 240, 240)",
            penColor="rgb(0, 0, 0)"
        )
    )

    class Meta:
        model = Signature
        exclude = ['user']
        fields = ['signature']  # Include other fields as needed
