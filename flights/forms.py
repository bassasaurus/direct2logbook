from logbook.date_fields import NamedDateInput
from django import forms
from logbook.date_formats import DATE_INPUT_FORMATS
from django.forms import inlineformset_factory
from flights.models import Flight, Aircraft, TailNumber, Imported, Holding, Approach
from django.contrib.auth.models import User
from dal import autocomplete
from flights.aircraft_classification import CLASS_CHOICES, CLASSES_BY_CATEGORY, class_required
from flights.aircraft_characteristics import ENGINE_CHOICES, WAKE_CHOICES, engine_required, normalize_characteristics
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

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs['class'] = (widget.attrs.get('class', '') + ' is-invalid').strip()
                widget.attrs['aria-invalid'] = 'true'

    def _update_errors(self, errors):
        from logbook.db_errors import MESSAGES
        from django.core.exceptions import ValidationError
        if hasattr(errors, 'error_dict'):
            safe = {}
            for field, values in errors.error_dict.items():
                for error in values:
                    constraint = (error.params or {}).get('name')
                    if not constraint:
                        constraint = next((item.name for item in self.instance._meta.constraints
                                           if str(error.message) == str(item.get_violation_error_message())), None)
                    if constraint in MESSAGES:
                        target, message = MESSAGES[constraint]
                        safe.setdefault(target or '__all__', []).append(message)
                    elif error.code == 'violation_of_constraint':
                        safe.setdefault('__all__', []).append('Couldn’t save this record. Please check your entries.')
                    else:
                        safe.setdefault(field, []).append(error)
            errors = ValidationError(safe)
        return super()._update_errors(errors)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        for name, field in self.fields.items():
            field.error_messages['required'] = 'Required'
            if name in self.owned_relation_fields:
                label = 'tailnumber' if name == 'registration' else 'aircraft'
                field.error_messages['invalid_choice'] = f'This {label} is no longer available. Choose one from your list.'
            if isinstance(field, (forms.DecimalField, forms.FloatField)):
                from django.core.validators import MinValueValidator
                for validator in field.validators:
                    if isinstance(validator, MinValueValidator) and validator.limit_value == 0:
                        validator.message = 'Hours cannot be negative.'
                field.validators.insert(0, MinValueValidator(0, 'Hours cannot be negative.'))
        if user is not None and user.is_authenticated and self.instance._state.adding:
            self.instance.user = user
        for name in self.owned_relation_fields:
            field = self.fields[name]
            if user is not None and user.is_authenticated:
                field.queryset = field.queryset.filter(user=user)
            else:
                # Missing caller context must never expose every user's records.
                field.queryset = field.queryset.none()


class FlightForm(UserOwnedRelationsFormMixin, forms.ModelForm):
    date = forms.DateField(input_formats=DATE_INPUT_FORMATS, widget=NamedDateInput(format='%b %d, %Y'))
    owned_relation_fields = ('aircraft_type', 'registration')

    airport_choices = forms.JSONField(required=False, max_length=5000, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['registration'].required = False
        self.fields['route'].required = False
        self.initial['airport_choices'] = self.instance.route_airport_choices or {}
        if not self.is_bound and self.instance._state.adding and self.user is not None and not self.initial.get('aircraft_type'):
            default = Aircraft.objects.filter(user=self.user, is_default=True).first()
            if default:
                self.initial['aircraft_type'] = default.pk
        if self.is_bound and self.data.get('simulator') and 'registration' not in self.data and self.instance.pk:
            self.data = self.data.copy()
            self.data['registration'] = self.instance.registration_id or ''
        from flights.launch_methods import launch_choices
        available = list(self.fields['aircraft_type'].queryset.only('pk', 'aircraft_category', 'self_launch_capable'))
        self.launch_aircraft_metadata = {str(row.pk): {'category': row.aircraft_category,
            'self_launch_capable': row.self_launch_capable} for row in available}
        selected = (self.data.get(self.add_prefix('aircraft_type')) if self.is_bound
                    else self.initial.get('aircraft_type'))
        aircraft = next((row for row in available if str(row.pk) == str(getattr(selected, 'pk', selected))), None)
        self.launch_method_visible = bool(aircraft and aircraft.aircraft_category == 'GL'
            and not (self.data.get(self.add_prefix('simulator')) if self.is_bound else self.initial.get('simulator')))
        self.fields['launch_method'].choices = [('', 'Choose launch method')] + launch_choices(aircraft)
        self.fields['launch_method'].error_messages['invalid_choice'] = 'Choose an available launch method.'

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('simulator') and (cleaned.get('device_type') or cleaned.get('device_id')):
            cleaned['registration'] = None
        for field, message in validate_flight(cleaned, self.instance).items():
            # Model.clean handles launch validation for forms, admin and imports.
            if field == 'launch_method':
                continue
            if field not in self.errors:
                self.add_error(field, message)
        return cleaned

    def clean_route(self):
        from flights.airport_resolution import resolve_route
        from flights.route_normalization import normalize_route
        route = normalize_route(self.cleaned_data['route'])
        if not route:
            sim = self.fields['simulator'].widget.value_from_datadict(self.data, self.files, 'simulator')
            if not sim:
                raise forms.ValidationError('Enter a route.')
            return route
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
            'date': NamedDateInput(
                format="%b %d, %Y"
            ),
            'aircraft_type': autocomplete.ModelSelect2(
                url='aircraft-autocomplete',
                attrs={'data-placeholder': 'e.g. C172'}
            ),
            'registration': autocomplete.ModelSelect2(
                url='tailnumber-autocomplete',
                forward=['aircraft_type'],
                attrs={'data-placeholder': 'e.g. N12345',
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


class ApproachForm(forms.ModelForm):
    class Meta:
        model = Approach
        fields = ('approach_type', 'number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from flights.approach_choices import APPROACH_CHOICES, LEGACY_APPROACH_CHOICES
        choices = [('', 'Type'), *APPROACH_CHOICES]
        current = self.initial.get('approach_type')
        choices.extend((code, label) for code, label in LEGACY_APPROACH_CHOICES if code == current)
        self.fields['approach_type'].choices = choices


ApproachFormSet = inlineformset_factory(Flight, Approach, form=ApproachForm, fields=(
    'approach_type', 'number'), max_num=4, extra=1)

HoldingFormSet = inlineformset_factory(
    Flight, Holding, fields=('hold',), max_num=1, extra=1)


class AircraftForm(UserOwnedRelationsFormMixin, forms.ModelForm):
    engine = forms.ChoiceField(required=False, widget=forms.RadioSelect,
        choices=ENGINE_CHOICES)
    weight_category = forms.ChoiceField(required=False, widget=forms.RadioSelect,
        choices=WAKE_CHOICES, label='Wake Category')
    selection_groups = AIRCRAFT_SELECTIONS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category = self.data.get(self.add_prefix('aircraft_category'), '') if self.is_bound else self.initial.get('aircraft_category', '')
        self.fields['simple'].disabled = True
        self.fields['simple'].widget = forms.HiddenInput()
        self.class_not_applicable = category in CLASSES_BY_CATEGORY and not class_required(category)
        klass = self.data.get(self.add_prefix('aircraft_class'), '') if self.is_bound else self.initial.get('aircraft_class', '')
        self.engine_not_applicable = not engine_required(category, klass)
        self.fields['aircraft_class'].required = False  # Conditional shared validation below.
        self.fields['aircraft_class'].widget.attrs['data-category-class'] = ''
        self.fields['aircraft_category'].widget.attrs['data-aircraft-category'] = ''
        self.classification_choices = {key: [list(choice) for choice in CLASS_CHOICES if choice[0] in codes]
                                       for key, codes in CLASSES_BY_CATEGORY.items()}
        self.classification_changed_warning = not self.instance._state.adding
        if not self.instance._state.adding:
            for name in ('aircraft_category', 'aircraft_class'):
                if not getattr(self.instance, name):
                    self.fields[name].required = False
        initialize_radio_groups(self, self.selection_groups)

    def clean(self):
        cleaned = super().clean()
        for group, fields in self.selection_groups.items():
            clean_radio_group(self, cleaned, group, fields)
        cleaned = normalize_characteristics(cleaned, self.instance)
        self.cleaned_data = cleaned
        for field, message in validate_aircraft(cleaned, self.instance, user=self.user).items():
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
            'small': forms.CheckboxInput(),
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
        for field, message in validate_tailnumber(cleaned, self.instance, user=self.user).items():
            if field not in self.errors:
                self.add_error(field, message)
        return cleaned

    owned_relation_fields = ('aircraft',)

    class Meta:
        model = TailNumber
        exclude = ['user']
        fields = '__all__'
        widgets = {
            'aircraft': autocomplete.ModelSelect2(url='aircraft-autocomplete', attrs={'data-placeholder': 'e.g. C172'}),
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
    last_flown = forms.DateField(required=False, input_formats=DATE_INPUT_FORMATS, widget=NamedDateInput(format='%b %d, %Y'))
    owned_relation_fields = ('aircraft_type',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field, forms.DecimalField):
                field.widget.attrs['placeholder'] = '##.#'
            elif name in ('landings_day', 'landings_night'):
                field.widget.attrs['placeholder'] = '#'

    class Meta:
        model = Imported
        exclude = ['user']
        fields = '__all__'
        widgets = {
            'aircraft_type': autocomplete.ModelSelect2(url='aircraft-autocomplete', attrs={'data-placeholder': 'e.g. C172'}),
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
