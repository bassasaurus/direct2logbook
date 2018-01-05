from django import forms
from flights.models import *
from flights.fields import *
from dal import autocomplete
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, Div, Field, HTML
from crispy_forms.bootstrap import PrependedText, InlineCheckboxes, AppendedText
# from django.contrib.admin.widgets import AdminDateWidget

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
            'tailwheel': forms.CheckboxInput(),
            'simple': forms.CheckboxInput(),
            'compleks': forms.CheckboxInput(),
            'high_performance': forms.CheckboxInput(),
            }

        labels = {
            'aircraft_category': 'Category*',
            'aircraft_class': 'Class*',
            }

    def __init__(self, *args, **kwargs):
        super(AircraftForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-aircraftform'
        self.helper.form_class = 'blueForms'
        self.helper.field_class = 'input-group'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Submit'))
        self.helper.form_style='inline'
        self.helper.form_show_labels = True
        self.fields['aircraft_type'].label = False
        self.helper.layout = Layout(
            Fieldset(
            Field(), #required for autocomplete fields to render
            AppendedText('aircraft_type', '<i class="material-icons">airplanemode_active</i>', placeholder="Aircraft Type *"),
            HTML('<hr>'),
            Div('turbine', css_class='form-check form-check-inline'),
            Div('piston', css_class='form-check form-check-inline'),
            HTML('<hr>'),
            Div('superr', css_class='form-check form-check-inline'),
            Div('heavy', css_class='form-check form-check-inline'),
            Div('large', css_class='form-check form-check-inline'),
            Div('medium', css_class='form-check form-check-inline'),
            Div('small', css_class='form-check form-check-inline'),
            HTML('<hr>'),
            Div('simple',css_class='form-check form-check-inline'),
            Div('compleks',css_class='form-check form-check-inline'),
            Div('high_performance',css_class='form-check form-check-inline'),
            Div('requires_type',css_class='form-check form-check-inline'),
            HTML('<hr>'),
            Div('tailwheel',css_class='form-check form-check-inline'),
            HTML('<hr>'),
            Div('aircraft_category'),
            Div('aircraft_class'),
            HTML('<hr>'),
            Div('image')
            ),
            )
        self.helper.form_tag = False




class ApproachForm(forms.ModelForm):

    class Meta:
        model = Approach
        fields = approach_fields()

    def __init__(self, *args, **kwargs):
        super(ApproachForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-approachform'
        self.helper.form_class = 'blueForms'
        self.helper.field_class = 'input-group'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Submit'))
        self.helper.form_style='inline'
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            AppendedText('approach_type', '', placeholder = "Approach type*"),
        )




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


    def __init__(self, *args, **kwargs):
        super(TailNumberForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-tailnumberform'
        self.helper.form_class = 'blueForms'
        self.helper.field_class = 'input-group'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Submit'))
        self.helper.form_style='inline'
        self.helper.form_show_labels = True
        self.fields['registration'].label = False
        self.fields['aircraft'].label = False

        self.helper.layout = Layout(
             Fieldset(
                Field(), #required for autocomplete fields to render
                AppendedText('registration', '', placeholder = "Registration*",  autocomplete='off'),
                AppendedText('aircraft', '', placeholder = "Aircraft*"),
                ('is_121'),
                ('is_135'),
                ('is_91'),
                )
            )
