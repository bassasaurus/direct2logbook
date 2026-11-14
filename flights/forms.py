from django import forms
from django.forms import inlineformset_factory
from flights.models import Flight, Aircraft, TailNumber, Imported, Holding, Approach
from django.contrib.auth.models import User
from dal import autocomplete
from flights.record_validation import (
    AIRCRAFT_SELECTIONS, OPERATING_RULES, validate_aircraft, validate_flight, validate_tailnumber,
)


def initialize_radio_groups(form, groups):
    form.legacy_radio_groups = set()
    if form.is_bound:
        form.data = form.data.copy()
    for group, fields in groups.items():
        if not form.is_bound:
            selected = [name for name in fields if form.initial.get(name)]
            form.initial.setdefault(group, selected[0] if len(selected) == 1 else '')
            continue
        key = form.add_prefix(group)
        if key not in form.data and any(form.add_prefix(name) in form.data for name in fields):
            form.legacy_radio_groups.add(group)
            selected = [name for name in fields if form.fields[name].widget.value_from_datadict(
                form.data, form.files, form.add_prefix(name))]
            form.data[key] = selected[0] if len(selected) == 1 else ''


def clean_radio_group(form, cleaned, group, fields):
    if group in form.legacy_radio_groups:
        return  # Validate the submitted boolean fields directly.
    selected = cleaned.get(group)
    previous = [name for name in fields if getattr(form.instance, name)]
    if not form.instance._state.adding and not selected and len(previous) != 1:
        # Empty radios represent an untouched legacy group with no single selection.
        cleaned.update({name: getattr(form.instance, name) for name in fields})
    else:
        cleaned.update({name: selected == name for name in fields})


class UserForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('first_name', 'last_name')


class UserOwnedRelationsFormMixin:
    owned_relation_fields = ()

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.owned_relation_fields:
            field = self.fields[name]
            if user is not None and user.is_authenticated:
                field.queryset = field.queryset.filter(user=user)
            else:
                # Missing caller context must never expose every user's records.
                field.queryset = field.queryset.none()


class FlightForm(UserOwnedRelationsFormMixin, forms.ModelForm):
    owned_relation_fields = ('aircraft_type', 'registration')

    airport_choices = forms.JSONField(required=False, max_length=5000, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['airport_choices'] = self.instance.route_airport_choices or {}

    def clean(self):
        cleaned = super().clean()
        for field, message in validate_flight(cleaned, self.instance).items():
            if field not in self.errors:
                self.add_error(field, message)
        return cleaned

    def clean_route(self):
        from flights.airport_resolution import resolve_route
        route = self.cleaned_data['route']
        unknown = list(dict.fromkeys(item['code'] for item in resolve_route(route) if item['unknown']))
        if unknown:
            raise forms.ValidationError('Unknown airport codes: ' + ', '.join(unknown) + '. Correct the route before saving.')
        return route

    def clean_airport_choices(self):
        from flights.airport_resolution import resolve_route
        value = (self.cleaned_data.get('airport_choices') or {}
                 if 'airport_choices' in self.data else self.initial.get('airport_choices', {}))
        route = self.cleaned_data.get('route', '')
        if not isinstance(value, dict):
            raise forms.ValidationError('Invalid airport selection.')
        if not value or value.get('route') != route:
            return {}
        selections = value.get('airports', {})
        if not isinstance(selections, dict):
            raise forms.ValidationError('Invalid airport selection.')
        resolution = resolve_route(route)
        valid = {str(item['position']): {airport.pk for airport in item['candidates']} for item in resolution}
        for position, airport_id in selections.items():
            if type(airport_id) is not int or airport_id not in valid.get(position, set()):
                raise forms.ValidationError('An airport selection is no longer valid. Check your route again.')
        return {'route': route, 'airports': selections}

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.route_airport_choices = self.cleaned_data.get('airport_choices') or {}
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    class Meta:
        model = Flight
        exclude = ['user']
        fields = '__all__'
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 3, 'maxlength': 500}),
            'date': forms.DateInput(
                format="%m/%d/%Y"
            ),
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
    engine = forms.ChoiceField(required=False, widget=forms.RadioSelect,
        choices=[('turbine', 'Turbine'), ('piston', 'Piston')])
    weight_category = forms.ChoiceField(required=False, widget=forms.RadioSelect,
        choices=[('superr', 'Super'), ('heavy', 'Heavy'),
                 ('large', 'Large'), ('medium', 'Medium'), ('small', 'Small'), ('light_sport', 'LSA')])
    selection_groups = AIRCRAFT_SELECTIONS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance._state.adding:
            for name in ('aircraft_category', 'aircraft_class'):
                if not getattr(self.instance, name):
                    self.fields[name].required = False
        initialize_radio_groups(self, self.selection_groups)

    def clean(self):
        cleaned = super().clean()
        for group, fields in self.selection_groups.items():
            clean_radio_group(self, cleaned, group, fields)
        for field, message in validate_aircraft(cleaned, self.instance).items():
            if field not in self.errors:
                self.add_error(field, message)
        return cleaned

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


class TailNumberForm(UserOwnedRelationsFormMixin, forms.ModelForm):
    operating_rules = forms.ChoiceField(required=False, widget=forms.RadioSelect,
        choices=[('is_91', 'Part 91'), ('is_135', 'Part 135'), ('is_121', 'Part 121')])
    rule_fields = OPERATING_RULES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initialize_radio_groups(self, {'operating_rules': self.rule_fields})

    def clean(self):
        cleaned = super().clean()
        clean_radio_group(self, cleaned, 'operating_rules', self.rule_fields)
        for field, message in validate_tailnumber(cleaned, self.instance).items():
            if field not in self.errors:
                self.add_error(field, message)
        return cleaned

    owned_relation_fields = ('aircraft',)

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


class ImportedForm(UserOwnedRelationsFormMixin, forms.ModelForm):
    owned_relation_fields = ('aircraft_type',)

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


class AirportConfirmationForm(forms.Form):
    route = forms.CharField(widget=forms.HiddenInput, max_length=50, strip=False)
    review = forms.BooleanField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, flight, review=False, **kwargs):
        from flights.airport_resolution import flight_resolution, airport_choice_label
        super().__init__(*args, **kwargs)
        self.flight = flight
        self.resolution = flight_resolution(flight)
        self.initial['route'] = flight.route
        self.initial['review'] = review
        self.has_unresolved = any(item['needs_confirmation'] for item in self.resolution)
        self.has_confirmed = any(item['confirmed'] for item in self.resolution)
        self.pending = [item for item in self.resolution
                        if item['needs_confirmation'] or (review and item['requires_choice'])]
        for item in self.pending:
            choices = []
            for airport in item['candidates']:
                choices.append((str(airport.pk), airport_choice_label(airport)))
            self.fields[f'airport_{item["position"]}'] = forms.ChoiceField(
                label=f'Which airport did you mean for {item["code"]} (route position {item["position"] + 1})?',
                choices=choices, widget=forms.RadioSelect,
                initial=str(item['airport'].pk) if item['confirmed'] else None,
            )

    def clean_route(self):
        route = self.cleaned_data['route']
        if route != self.flight.route:
            raise forms.ValidationError('The route changed. Refresh the flight and confirm its current airports.')
        return route

    def selections(self):
        airports = {str(item['position']): item['airport'].pk for item in self.resolution if item['confirmed']}
        airports.update({name.removeprefix('airport_'): int(value)
                         for name, value in self.cleaned_data.items() if name.startswith('airport_')})
        return {'route': self.flight.route, 'airports': airports}
