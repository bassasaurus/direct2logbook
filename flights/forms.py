from django import forms
from flights.models import *
from flights.fields import *
from dal import autocomplete

class FlightForm(forms.ModelForm):

    #django class-----
    class Meta:
        model = Flight
        fields = flight_fields()
        widgets = {
            'aircraft_type': autocomplete.ModelSelect2(url='aircraft-autocomplete', attrs={'data-placeholder': 'Aircraft *'}),
            'registration': autocomplete.ModelSelect2(url='tailnumber-autocomplete', attrs={'data-placeholder': 'Tailnumber *'}),
            'cross_country': forms.CheckboxInput(),
            'second_in_command': forms.CheckboxInput(),
            'pilot_in_command': forms.CheckboxInput(),
            'instructor': forms.CheckboxInput(),
            'dual': forms.CheckboxInput(),
            'simulator': forms.CheckboxInput(),
            'solo': forms.CheckboxInput(),
        }

class AircraftForm(forms.ModelForm):

    class Meta:
        model = Aircraft
        fields = aircraft_fields()
        widgets = {
            'turbine': forms.CheckboxInput(),
            'piston': forms.CheckboxInput(),
            'requires_type': forms.CheckboxInput(),
            'superr': forms.CheckboxInput(),
            'heavy': forms.CheckboxInput(),
            'large': forms.CheckboxInput(),
            'medium': forms.CheckboxInput(),
            'small': forms.CheckboxInput(),
            'light_sport':forms.CheckboxInput(),
            'tailwheel': forms.CheckboxInput(),
            'simple': forms.CheckboxInput(),
            'compleks': forms.CheckboxInput(),
            'high_performance': forms.CheckboxInput(),
            }

        labels = {
            'aircraft_category': 'Category*',
            'aircraft_class': 'Class*',
            }



class ApproachForm(forms.ModelForm):

    class Meta:
        model = Approach
        fields = approach_fields()

class TailNumberForm(forms.ModelForm):

    class Meta:
        model = TailNumber
        fields = tailnumber_fields()
        widgets = {
            'aircraft_type': autocomplete.ModelSelect2(url='aircraft-autocomplete', attrs={'data-placeholder': 'Aircraft*'}),
            'is_121': forms.CheckboxInput(),
            'is_135': forms.CheckboxInput(),
            'is_91': forms.CheckboxInput(),
        }
        labels = {
            'is_121': '121',
            'is_135': '135',
            'is_91': '91',
        }
