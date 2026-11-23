from django import forms
from .models import Signature
from .strokes import validate_strokes
from signature_pad import SignaturePadWidget


class StrokeSignatureWidget(SignaturePadWidget):
    class Media:
        extend = False
        js = ('js/signature_strokes.js',)
        css = {'all': ('signature_pad/css/signature_pad_widget.css',)}


class SignatureForm(forms.ModelForm):
    signature = forms.CharField(required=False, widget=StrokeSignatureWidget(
        dotSize=2.5, minWidth=1.0, maxWidth=4.0,
        backgroundColor='rgb(255, 255, 255)', penColor='rgb(0, 0, 0)'))
    strokes = forms.JSONField(required=False, widget=forms.HiddenInput, validators=[validate_strokes])
    stroke_aspect_ratio = forms.FloatField(required=False, min_value=.5, max_value=10, widget=forms.HiddenInput)

    class Meta:
        model = Signature
        fields = ['signature']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The saved signature is shown separately; the capture pad starts empty.
        if not self.is_bound:
            self.initial.update(signature='', strokes=None, stroke_aspect_ratio=3)

    def clean(self):
        data = super().clean()
        if data.get('strokes'):
            data['signature'] = None
        elif data.get('signature'):
            data['strokes'] = None
        elif not self.errors:
            self.add_error('signature', 'Draw your signature before saving.')
        data['stroke_aspect_ratio'] = data.get('stroke_aspect_ratio') or 3
        return data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('strokes'):
            instance._pending_strokes = (self.cleaned_data['strokes'], self.cleaned_data['stroke_aspect_ratio'])
        if commit:
            instance.save()
        return instance
