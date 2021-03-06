from django import forms
from django.forms import inlineformset_factory
from flights.models import Flight, Aircraft, TailNumber, Imported, Holding, Approach
from django.contrib.auth.models import User
from dal import autocomplete


class UserForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('first_name', 'last_name')


class FlightForm(forms.ModelForm):

    aircraft = Aircraft.objects.all()
    choices = []
    for obj in aircraft:
        j = 0
        choices.append((j, str(obj)))
        j += 1

    aircraft_type = autocomplete.ModelSelect2(choices=choices)

    class Meta:
        model = Flight
        exclude = ['user']
        fields = '__all__'
        widgets = {
            'aircraft_type': autocomplete.ModelSelect2(
                url='aircraft-autocomplete',
                attrs={'data-placeholder': 'Aircraft *'}
            ),
            'registration': autocomplete.ModelSelect2(
                url='tailnumber-autocomplete',
                forward=['aircraft_type'],
                attrs={'data-placeholder': 'Tailnumber *',
                       },
            ),

            'cross_country': forms.CheckboxInput(),
            'second_in_command': forms.CheckboxInput(),
            'pilot_in_command': forms.CheckboxInput(),
            'instructor': forms.CheckboxInput(),
            'dual': forms.CheckboxInput(),
            'simulator': forms.CheckboxInput(),
            'solo': forms.CheckboxInput(),
        }


ApproachFormSet = inlineformset_factory(Flight, Approach, fields=(
    'approach_type', 'number'), max_num=4, extra=1)

HoldingFormSet = inlineformset_factory(
    Flight, Holding, fields=('hold',), max_num=1, extra=1)


class AircraftForm(forms.ModelForm):

    class Meta:
        model = Aircraft
        exclude = ['user']
        fields = '__all__'
        widgets = {
            'turbine': forms.CheckboxInput(),
            'piston': forms.CheckboxInput(),
            'requires_type': forms.CheckboxInput(),
            'superr': forms.CheckboxInput(),
            'heavy': forms.CheckboxInput(),
            'large': forms.CheckboxInput(),
            'medium': forms.CheckboxInput(),
            'small': forms.CheckboxInput(),
            'light_sport': forms.CheckboxInput(),
            'tailwheel': forms.CheckboxInput(),
            'simple': forms.CheckboxInput(),
            'compleks': forms.CheckboxInput(),
            'high_performance': forms.CheckboxInput(),
        }


class TailNumberForm(forms.ModelForm):

    class Meta:
        model = TailNumber
        exclude = ['user']
        fields = '__all__'
        widgets = {
            'aircraft': autocomplete.ModelSelect2(url='aircraft-autocomplete', attrs={'data-placeholder': 'Aircraft *'}),
            'is_121': forms.CheckboxInput(),
            'is_135': forms.CheckboxInput(),
            'is_91': forms.CheckboxInput(),
        }
        labels = {
            'is_121': '121',
            'is_135': '135',
            'is_91': '91',
        }


class ImportedForm(forms.ModelForm):

    class Meta:
        model = Imported
        exclude = ['user']
        fields = '__all__'
        widgets = {
            'aircraft_type': autocomplete.ModelSelect2(url='aircraft-autocomplete', attrs={'data-placeholder': 'Aircraft *'}),
            'is_121': forms.CheckboxInput(),
            'is_135': forms.CheckboxInput(),
            'is_91': forms.CheckboxInput(),
        }
