from django import forms
from functools import partial
from flights.models import *
from flights.fields import *
from dal import autocomplete
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, Div, Field, HTML
from crispy_forms.bootstrap import PrependedText, InlineCheckboxes, AppendedText


DateInput = partial(forms.DateInput, {'class': 'datepicker'})


class FlightForm(forms.ModelForm):
    #crispy_forms-----
    def __init__(self, *args, **kwargs):
        super(FlightForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-flightform'
        self.helper.form_class = 'blueForms'
        self.helper.field_class = 'input-group'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Submit'))
        self.helper.form_style='inline'
        self.helper.form_show_labels = True
        self.fields['date'].label = False
        self.fields['aircraft_type'].label = False
        self.fields['registration'].label = False
        self.fields['route'].label = False
        self.fields['duration'].label = False
        self.fields['legs'].label = False
        self.fields['landings_day'].label = False
        self.fields['landings_night'].label = False
        self.fields['night'].label = False
        self.fields['instrument'].label = False
        self.fields['simulated_instrument'].label = False
        self.fields['remarks'].label = False
        self.fields['pilot_in_command'].label = 'PIC'
        self.fields['second_in_command'].label = 'SIC'
        self.fields['cross_country'].label = 'XC'
        self.fields['instructor'].label = 'CFI'
        self.fields['simulator'].label = 'SIM'

        self.helper.layout = Layout(
             Fieldset(
                Field(), #required for autocomplete fields to render
                AppendedText('date', '<i class="material-icons">date_range</i>', placeholder="Date*", autocomplete='off'),
                Div(HTML('<a href data-toggle="modal" data-target="#new_aircraft_modal"> New Aircraft</a>'), 'aircraft_type'),
                # Div(HTML('<a target="new" href="{% url "aircraft_create" %}">New Aircraft</a>'), 'aircraft_type'),
                Div(HTML('<a target="new" href="{% url "tailnumber_create" %}">New Tailnumber</a>'), 'registration'),
                AppendedText('route', '<i class="material-icons">timeline</i>', onkeydown="upperCase(this)", placeholder="xxx-xxxx*", autocomplete='off'),
                AppendedText('legs', '', placeholder="Legs*"),
                AppendedText('duration', '<i class="material-icons">watch_later</i>', placeholder="Duration*"),
                HTML('<hr>'),
                Div('pilot_in_command',css_class='form-check form-check-inline',),
                Div('second_in_command',css_class='form-check form-check-inline',),
                Div('cross_country',css_class='form-check form-check-inline',),
                Div('instructor',css_class='form-check form-check-inline',),
                Div('dual',css_class='form-check form-check-inline',),
                Div('solo',css_class='form-check form-check-inline',),
                Div('simulator',css_class='form-check form-check-inline',),
                HTML('<hr>'),
                AppendedText('landings_day', '<i class="material-icons">flight_land</i>', placeholder="Day Landings"),
                AppendedText('landings_night', '<i class="material-icons">flight_land</i>', placeholder="Night Landings"),
                AppendedText('night', '', placeholder="Night"),
                Div('approaches', css_class=''),
                AppendedText('instrument', '<i class="material-icons">cloud</i>', placeholder="Actual Instrument"),
                PrependedText('simulated_instrument', '', placeholder="Simulated Instrument"),
                PrependedText('remarks', '', placeholder="Remarks"),
                ),
            )
        self.helper.form_tag = False
    #django class-----
    class Meta:
        model = Flight
        fields = flight_fields()
        widgets = {
            'date': forms.SelectDateWidget(),
            'aircraft_type': autocomplete.ModelSelect2(url='aircraft-autocomplete', attrs={'data-placeholder': 'Aircraft*'}),
            'registration': autocomplete.ModelSelect2(url='tailnumber-autocomplete', attrs={'data-placeholder': 'Tailnumber*'}),
            'cross_country': forms.CheckboxInput(),
            'second_in_command': forms.CheckboxInput(),
            'pilot_in_command': forms.CheckboxInput(),
            'instructor': forms.CheckboxInput(),
            'dual': forms.CheckboxInput(),
            'simulator': forms.CheckboxInput(),
            'solo': forms.CheckboxInput(),
        }

    date = forms.DateField(widget=DateInput())

class UserCreateForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password']

class AircraftForm(forms.ModelForm):

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
            AppendedText('aircraft_type', '<i class="material-icons">airplanemode_active</i>', placeholder="Aircraft Type*"),
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

class ApproachForm(forms.ModelForm):

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

    class Meta:
        model = Approach
        fields = approach_fields()


class TailNumberForm(forms.ModelForm):

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
            AppendedText('registration', '', placeholder = "Registration*"),
        )

    class Meta:
        model = TailNumber
        fields = tailnumber_fields()
        widgets = {
            'aircraft': autocomplete.ModelSelect2(url='aircraft-autocomplete',attrs={'data-placeholder': 'Aircraft*'}),
            'is_121': forms.CheckboxInput(),
            'is_135': forms.CheckboxInput(),
            'is_91': forms.CheckboxInput(),
        }
        labels = {
            'is_121': '121',
            'is_135': '135',
            'is_91': '91',
        }
