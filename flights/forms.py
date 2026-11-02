from django import forms
from django.forms import inlineformset_factory
from flights.models import Flight, Aircraft, TailNumber, Imported, Holding, Approach
from django.contrib.auth.models import User
from dal import autocomplete


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

    class Meta:
        model = Flight
        exclude = ['user']
        fields = '__all__'
        widgets = {
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
        from flights.airport_resolution import flight_resolution
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
                location = ', '.join(value for value in (airport.city, airport.state, airport.country) if value)
                label = f'{airport.name} — {location}'
                if airport.icao:
                    label += f' ({airport.icao})'
                choices.append((str(airport.pk), label))
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
