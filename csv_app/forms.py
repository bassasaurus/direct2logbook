from flights.operating_rules import OPERATING_RULE_CHOICES
from django import forms

from .validation import MAX_BYTES
from .dates import DATE_ORDER_CHOICES
from .mapping import MAPPING_FIELDS, REQUIRED_FIELDS, BASIC_FIELDS, LABELS, HOUR_FIELDS, key
from .records import PAGE_SIZE
from flights.models import Aircraft, TailNumber
from dal import autocomplete, forward


class InspectForm(forms.Form):
    file = forms.FileField(label='CSV file')

    def clean_file(self):
        upload = self.cleaned_data['file']
        if upload.size > MAX_BYTES:
            raise forms.ValidationError(f'The CSV must be no larger than {MAX_BYTES // (1024 * 1024)} MB.')
        return upload


class DateOrderForm(forms.Form):
    date_order = forms.ChoiceField(label='Date format', choices=DATE_ORDER_CHOICES,
                                   widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                                   error_messages={'required': 'Choose a date format.'})


class ColumnMappingForm(forms.Form):
    confirm_short_years = forms.BooleanField(required=False,
        label='Interpret years 00–68 as 2000–2068 and 69–99 as 1969–1999',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    time_units = forms.ChoiceField(label='Plain numeric times are in', required=False,
        choices=[('', 'Choose time units'), ('hours', 'Decimal hours (1.5 = 1 hour 30 minutes)'),
                 ('minutes', 'Minutes (90 = 1 hour 30 minutes)')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        error_messages={'required': 'Choose the units used for numeric times.'})
    confirm_overnight = forms.BooleanField(required=False,
        label='Treat Block In as the next day when its clock time is earlier than Block Out.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    confirm_block_difference = forms.BooleanField(required=False,
        label='Keep the selected Duration values for rows that differ from block times or cannot be compared.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    ignore_unused = forms.BooleanField(required=False, label='Ignore the unselected columns listed above',
                                       widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def __init__(self, *args, table, **kwargs):
        super().__init__(*args, **kwargs)
        self.table = table
        suggestions = table.suggestions()
        columns = [(str(index), f"{name or 'Unnamed'} (column {index + 1}) — {', '.join(table.samples(index)) or 'Blank'}")
                   for index, name in enumerate(table.headers)]
        for index, name in enumerate(MAPPING_FIELDS):
            required = name in REQUIRED_FIELDS
            label = LABELS.get(name, name.title())
            self.fields[f'map_{index}'] = forms.ChoiceField(
                label=label, required=required,
                choices=[('', 'Choose a column' if required else 'Not provided')] + columns
                    + ([('airports', 'Build from Departure and Destination')] if name == 'route' else [])
                    + ([('block_times', 'Calculate from Block Out and Block In')] if name == 'duration' else [])
                    + [('constant', 'Use one value for every row')],
                initial=str(suggestions[name]) if name in suggestions else
                    'airports' if name == 'route' and 'departure' in suggestions and 'destination' in suggestions else
                    'block_times' if name == 'duration' and 'block out' in suggestions and 'block in' in suggestions else '',
                widget=forms.Select(attrs={'class': 'form-select', 'data-column-map': '',
                                           'data-mapping-target': name, 'aria-label': f'Match {label}'}),
                error_messages={'required': f'Choose a column or shared value for {label}.'})
            self.fields[f'value_{index}'] = forms.CharField(required=False, max_length=500, strip=name != 'remarks',
                label=f'{label} for every row', widget=forms.TextInput(attrs={
                    'class': 'form-control', 'placeholder': 'Value for every row', 'aria-label': f'{label} for every row'}))
        for name in ('registration', 'route'):
            self.fields[f'map_{MAPPING_FIELDS.index(name)}'].required = self.has_actual_flights
        self.fields['time_units'].required = self.needs_numeric_units
        self.fields['time_units'].initial = self.time_detection['suggestion']

    @property
    def has_actual_flights(self):
        from .mapping import converted_value
        from .validation import number, CSVValidationError
        for line, record in enumerate(self.table.records, 2):
            if not any(record):
                continue
            try:
                if number(converted_value('simulator', self.mapped_value('simulator', record), line)) <= 0:
                    return True
            except CSVValidationError:
                return True
        return False

    @property
    def time_detection(self):
        import re
        from decimal import Decimal
        fields = HOUR_FIELDS if self.table.role_times else {'duration', 'night', 'instrument', 'simulated instrument'}
        numeric, durations, decimal_notation = [], [], False
        for record in self.table.records:
            if not any(record):
                continue
            for name in fields:
                value = self.mapped_value(name, record).strip()
                if re.fullmatch(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', value) and Decimal(value) > 0:
                    numeric.append(Decimal(value))
                    decimal_notation |= '.' in value
                    if name == 'duration':
                        durations.append(Decimal(value))
        # Fractional hours provide evidence for a column-wide interpretation.
        # Large durations suggest minutes, but never silently convert grouped/device time.
        large = any(value > 30 for value in numeric)
        clear = not numeric or (decimal_notation and not large)
        return {'clear': clear, 'suggestion': 'hours' if clear else
                'minutes' if any(value > 30 for value in durations) else ''}

    @property
    def needs_numeric_units(self):
        return not self.time_detection['clear']

    @property
    def effective_time_units(self):
        return 'hours' if self.time_detection['clear'] else self['time_units'].value() or ''

    def unmatched_reason(self, name):
        candidates = self.table.candidates().get(name, [])
        if len(candidates) > 1 and name not in self.table.suggestions():
            headings = ', '.join(f'{self.table.headers[index]} (column {index + 1})' for index in candidates)
            return f'Multiple possible columns: {headings}. Choose one.'
        if candidates:
            return 'Matching column was unassigned. Choose a column to use it again.'
        available = self.table.suggestions()
        if name == 'duration' and (('block out' in available) != ('block in' in available)):
            return 'Both Block Out and Block In are needed to calculate Duration.'
        if name == 'route' and (('departure' in available) != ('destination' in available)):
            return 'Both Departure and Destination are needed to build Route.'
        if name == 'instrument' and self.table.source_key and any(header.strip().lower() == 'ifr' for header in self.table.headers):
            return 'IFR identifies flight rules, not actual instrument time. Choose an instrument-time column.'
        if name in ('departure', 'destination'):
            from .mapping import key
            heading = 'departure' if name == 'departure' else 'arrival'
            if any(key(header) == heading for header in self.table.headers):
                return 'These values do not clearly identify airports. Choose an airport-code column.'
        return 'No matching column heading found.'

    def rows(self):
        suggestions = self.table.suggestions()
        candidates = self.table.candidates()
        formats = self.table.column_formats
        result = []
        for index, name in enumerate(MAPPING_FIELDS):
            column, constant = self[f'map_{index}'], self[f'value_{index}']
            selected = column.value() or ''
            ambiguous = len(candidates.get(name, [])) > 1 and name not in suggestions and not selected
            required = name in REQUIRED_FIELDS or self.fields[f'map_{index}'].required
            errors = bool(column.errors or constant.errors)
            group = 'required' if required else 'review' if errors or ambiguous else 'matched' if selected else 'optional'
            reason = self.unmatched_reason(name)
            status = ('Choose between columns. ' + reason if ambiguous else
                      'Shared value' if selected == 'constant' else
                      'Calculated from block times' if selected == 'block_times' else
                      'Built from airports' if selected == 'airports' else
                      'Suggested match' if selected and str(suggestions.get(name)) == str(selected) else
                      'Selected' if selected else reason)
            conversion = []
            if str(selected).isdigit() and self.table.source_key == 'foreflight':
                prepared = self.table.headers[int(selected)]
                if prepared in ('Structured Approach Count', 'Structured Approach Types'):
                    conversion.append('Structured approaches → combined types and counts')
                elif prepared == 'Comments and Approach Details':
                    conversion.append('Comments + approach runway, airport and circling details → Remarks')
            if name == 'route':
                if selected == 'airports':
                    conversion.append('Departure + Destination → Route')
                elif str(selected).isdigit() and self.table.derived.get(int(selected)) == 'route':
                    conversion.append('Departure + intermediate stops + Destination → Route')
            elif name == 'duration' and selected == 'block_times':
                conversion.append('Block In − Block Out → decimal hours (nearest tenth)')
            elif name in (HOUR_FIELDS if self.table.role_times else {'duration', 'night', 'instrument', 'simulated instrument'}):
                import re
                format_info = formats.get(str(selected), {})
                if selected == 'constant':
                    value = str(constant.value() or '').strip()
                    format_info = {'hhmm': bool(re.fullmatch(r'\d{1,3}:[0-5]\d', value)),
                                   'numeric': bool(re.fullmatch(r'-?\d+(?:\.\d+)?', value))}
                if format_info.get('hhmm'):
                    conversion.append('HH:MM → decimal hours (nearest tenth)')
                if format_info.get('numeric') and self.effective_time_units == 'minutes':
                    conversion.append('Minutes → decimal hours (nearest tenth)')
                from .block_times import rounded_duration
                samples = [str(constant.value() or '')] if selected == 'constant' else self.table.samples(int(selected)) if str(selected).isdigit() else []
                examples = [f'{value} → {converted} h' for value in samples
                            if (':' in value or self.effective_time_units == 'minutes')
                            and (converted := rounded_duration(value, self.effective_time_units or 'hours')) is not None]
                if examples:
                    conversion.append('; '.join(examples))
            combined_label, combined_preview = '', ''
            if name == 'route' and selected == 'airports':
                selected_inputs = [str(self[f'map_{MAPPING_FIELDS.index(target)}'].value() or '') for target in ('departure', 'destination')]
                if all(selected_inputs):
                    combined_label = 'Combined from ' + ' + '.join(f'column {int(value) + 1}' if value.isdigit() else 'shared value' for value in selected_inputs)
                    examples = list(dict.fromkeys(f"{self.mapped_value('departure', record)}-{self.mapped_value('destination', record)}" for record in self.table.records if any(record)))[:3]
                    combined_preview = ', '.join(examples)
            source_label = f'Column {int(selected) + 1} · {self.table.headers[int(selected)]}' if str(selected).isdigit() and int(selected) < len(self.table.headers) else ''
            result.append({'label': LABELS.get(name, name.title()), 'required': required,
                'column': column, 'constant': constant, 'group': group, 'target': name,
                'ambiguous': ambiguous, 'status': status, 'unmatched_reason': reason, 'conversion': '; '.join(conversion), 'source_label': source_label, 'combined_label': combined_label, 'combined_preview': combined_preview})
        return result

    @property
    def needs_year_confirmation(self):
        import re
        selected = self[f'map_{MAPPING_FIELDS.index("date")}'].value()
        if selected == 'constant':
            values = [self[f'value_{MAPPING_FIELDS.index("date")}'].value() or '']
        elif selected is not None and str(selected).isdigit() and int(selected) < len(self.table.headers):
            values = [row[int(selected)] for row in self.table.records if any(row)]
        else:
            values = []
        return any(re.fullmatch(r'\d{1,2}([/\-])\d{1,2}\1\d{2}', value.strip()) for value in values)

    def mapped_value(self, name, record):
        index = MAPPING_FIELDS.index(name)
        selected = str(self[f'map_{index}'].value() or '')
        if selected == 'constant':
            return str(self[f'value_{index}'].value() or '')
        if selected.isdigit() and int(selected) < len(record):
            return record[int(selected)]
        return ''

    @property
    def uses_block_times(self):
        return any(self[f'map_{MAPPING_FIELDS.index(name)}'].value() for name in ('block out', 'block in')) or self[f'map_{MAPPING_FIELDS.index("duration")}'].value() == 'block_times'

    def block_checks(self):
        from .block_times import elapsed_hours, rounded_duration, OvernightConfirmationRequired
        from .validation import CSVValidationError
        if not self.uses_block_times:
            return []
        calculated = self[f'map_{MAPPING_FIELDS.index("duration")}'].value() == 'block_times'
        checks = []
        for line, record in enumerate(self.table.records, 2):
            if not any(record):
                continue
            out, arrival = self.mapped_value('block out', record), self.mapped_value('block in', record)
            if not out and not arrival and not calculated:
                continue
            duration = rounded_duration(self.mapped_value('duration', record), self.effective_time_units or 'hours')
            error, hours, overnight = '', None, False
            try:
                hours = elapsed_hours(out, arrival, bool(self['confirm_overnight'].value()))
            except OvernightConfirmationRequired as exc:
                overnight = True
                error = str(exc)
            except CSVValidationError as exc:
                error = str(exc)
            checks.append({'line': line, 'out': out, 'arrival': arrival, 'calculated': hours,
                'selected': duration, 'from_blocks': calculated, 'overnight': overnight, 'error': error,
                'difference': not calculated and not overnight and (hours is None or duration != hours)})
        return checks

    @property
    def show_time_units(self):
        return self.needs_numeric_units or bool(self['time_units'].errors)

    def source_usage(self):
        usage, moved = {}, set()
        helper_targets = {'departure', 'destination', 'block out', 'block in'}
        route_active = self[f'map_{MAPPING_FIELDS.index("route")}'].value() == 'airports' and all(
            self[f'map_{MAPPING_FIELDS.index(name)}'].value() for name in ('departure', 'destination'))
        blocks_active = all(self[f'map_{MAPPING_FIELDS.index(name)}'].value() for name in ('block out', 'block in'))
        for row in self.rows():
            selected = str(row['column'].value() or '')
            if not selected.isdigit():
                continue
            target, label = row['target'], row['label']
            if target in ('departure', 'destination'):
                if not route_active:
                    continue
                label = 'Route'
            elif target in ('block out', 'block in'):
                if not blocks_active:
                    continue
                label = 'Duration'
            else:
                moved.add(int(selected))
            for index in self.table.consumed_columns([selected]):
                usage.setdefault(int(index), []).append(label)
        return usage, moved

    def source_columns(self):
        usage, moved = self.source_usage()
        candidates = self.table.candidates()
        result = []
        for index, name in enumerate(self.table.headers):
            samples = self.table.samples(index)
            if not samples:
                continue
            labels = list(dict.fromkeys(usage.get(index, [])))
            possible = [LABELS.get(target, target.title()) for target, indexes in candidates.items() if index in indexes]
            conversion_reason = ''
            if any(index in candidates.get(target, []) for target in ('departure', 'destination')):
                conversion_reason = 'Import-only airport column: combine into Route; not stored separately.'
            elif any(index in candidates.get(target, []) for target in ('block out', 'block in')):
                conversion_reason = 'Import-only block time: calculate Duration; not stored separately.'
            unused_reason = ('Legs is not imported. Each included row creates one logbook entry; leg counts do not split entries.'
                             if key(name) in ('legs', 'leg', 'legcount', 'numberoflegs') else '')
            if self.table.source_key == 'myflightbook':
                if key(name) == 'flightid':
                    unused_reason = 'This source-system flight ID is not a Direct2Logbook record ID and cannot update an existing entry.'
                elif key(name) == 'landings':
                    unused_reason = 'Total landings includes touch-and-go and full-stop landings. It does not identify separate day/night counts; review the matched full-stop columns.'
                elif key(name) == 'flightproperties':
                    unused_reason = 'This display summary is not imported. Map individual supported fields instead.'
            result.append({'index': index, 'number': index + 1, 'name': name or f'Column {index + 1}', 'conversion_reason': conversion_reason, 'unused_reason': unused_reason,
                'samples': samples, 'derived': index in self.table.derived, 'used': bool(labels), 'moved': index in moved,
                'usage': ', '.join(labels), 'possible': ', '.join(possible)})
        return result

    def unused_columns(self):
        usage, _ = self.source_usage()
        used = {str(index) for index in usage}
        return [{'index': index, 'name': name or f'Column {index + 1}', 'samples': self.table.samples(index)}
                for index, name in enumerate(self.table.headers)
                if str(index) not in used and self.table.samples(index)]

    def clean(self):
        cleaned = super().clean()
        if self.time_detection['clear']:
            cleaned['time_units'] = 'hours'
        mapping = {}
        for index, name in enumerate(MAPPING_FIELDS):
            selected = cleaned.get(f'map_{index}')
            if selected == 'constant':
                value = cleaned.get(f'value_{index}', '')
                if not value:
                    self.add_error(f'value_{index}', 'Enter the value to use for every row.')
                else:
                    mapping[name] = {'value': value}
            elif name == 'duration' and selected == 'block_times':
                mapping[name] = {'calculated': 'block_times'}
            elif selected and selected != 'airports':
                mapping[name] = {'column': int(selected)}
        if not any(name in mapping for name in ('pilot in command', 'second in command', 'solo', 'dual')):
            self.add_error(None, 'Choose a column or shared value for PIC, SIC, Solo, or Dual.')
        if self.needs_year_confirmation and not cleaned.get('confirm_short_years'):
            self.add_error('confirm_short_years', 'Confirm the two-digit years or use four-digit years in the file.')
        if self.unused_columns() and not cleaned.get('ignore_unused'):
            self.add_error('ignore_unused', 'Match the remaining columns or confirm that they can be ignored.')
        if 'route' in mapping and ('departure' in mapping or 'destination' in mapping):
            self.add_error(None, 'Choose Route or departure/destination airports, not both.')
        if ('departure' in mapping) != ('destination' in mapping):
            self.add_error(None, 'Match both Departure Airport and Destination Airport.')
        if cleaned.get(f'map_{MAPPING_FIELDS.index("route")}') == 'airports' and not {'departure', 'destination'} <= mapping.keys():
            self.add_error(f'map_{MAPPING_FIELDS.index("route")}', 'Match both Departure Airport and Destination Airport to build Route.')
        if ('block out' in mapping) != ('block in' in mapping):
            self.add_error(None, 'Match both Block Out and Block In, or leave both unselected.')
        if mapping.get('duration', {}).get('calculated') == 'block_times' and not {'block out', 'block in'} <= mapping.keys():
            self.add_error(None, 'Match Block Out and Block In to calculate Duration.')
        if mapping.get('duration', {}).get('calculated') == 'block_times':
            cleaned['confirm_block_difference'] = False
        checks = self.block_checks()
        if any(row['overnight'] for row in checks) and not cleaned.get('confirm_overnight'):
            self.add_error('confirm_overnight', 'Confirm the overnight crossing or use block times that include dates.')
        if any(row['difference'] for row in checks) and not cleaned.get('confirm_block_difference'):
            self.add_error('confirm_block_difference', 'Review the differences. Calculate Duration from block times or confirm keeping the selected Duration values.')
        cleaned['mapping'] = mapping
        return cleaned


class RecordResolutionForm(forms.Form):
    def __init__(self, *args, user, resolution, **kwargs):
        super().__init__(*args, **kwargs)
        self.resolution = resolution
        self.user = user
        self.pending_tail_forms = []
        self.aircraft_stage = bool(resolution.missing_aircraft)
        self.entries = resolution.issues[:PAGE_SIZE]
        for entry in self.entries:
            index = entry['index']
            self.fields[f'aircraft_{index}'] = forms.ModelChoiceField(
                queryset=Aircraft.objects.filter(user=user), label='Aircraft Type',
                initial=getattr(entry.get('aircraft'), 'pk', None),
                widget=autocomplete.ModelSelect2(url='aircraft-autocomplete', attrs={'data-width': '100%', 'data-placeholder': 'Choose an aircraft'}),
                error_messages={'required': 'Choose an aircraft.', 'invalid_choice': 'Choose an aircraft from your account.'})
            if not self.aircraft_stage:
                aircraft_id = self.data.get(f'aircraft_{index}') if self.is_bound else getattr(entry.get('aircraft'), 'pk', None)
                owned_aircraft = Aircraft.objects.filter(user=user, pk=aircraft_id).first() if str(aircraft_id).isdigit() else None
                self.fields[f'tailnumber_{index}'] = forms.ModelChoiceField(
                    queryset=TailNumber.objects.filter(user=user, aircraft=owned_aircraft).select_related('aircraft') if owned_aircraft else TailNumber.objects.none(), label='Tailnumber',
                    initial=getattr(entry.get('tailnumber'), 'pk', None) if entry.get('tailnumber') and entry['tailnumber'].aircraft_id == getattr(owned_aircraft, 'pk', None) else None, required=entry['required'] and entry.get('tailnumber') is not None,
                    widget=autocomplete.ModelSelect2(url='tailnumber-autocomplete', forward=[forward.Field(f'aircraft_{index}', 'aircraft_type'), forward.Const(True, 'require_aircraft')], attrs={'data-width': '100%', 'data-placeholder': 'Choose a tailnumber'}),
                    error_messages={'required': 'Choose a tailnumber.', 'invalid_choice': 'Choose a tailnumber assigned to the selected aircraft.'})

            if not self.aircraft_stage and entry.get('tailnumber') is None:
                if not entry['required']:
                    self.fields[f'skip_tail_{index}'] = forms.BooleanField(required=False, label='Use no tailnumber for these simulator sessions', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
                self.fields[f'operating_rules_{index}'] = forms.ChoiceField(required=False,
                    label='Operating rules', choices=[('', 'Choose operating rules'), *OPERATING_RULE_CHOICES],
                    widget=forms.RadioSelect(attrs={'class': 'form-check-input'}))

    def clean(self):
        cleaned = super().clean()
        choices = json_copy(self.resolution.saved)
        choices.setdefault('aircraft', {})
        choices.setdefault('pairs', {})
        for entry in self.entries:
            index = entry['index']
            aircraft = cleaned.get(f'aircraft_{index}')
            if not aircraft:
                continue
            if self.aircraft_stage:
                choices['aircraft'][entry['key']] = aircraft.pk
            else:
                tail = cleaned.get(f'tailnumber_{index}')
                if not entry.get('tailnumber') and not tail:
                    if not entry['required'] and cleaned.get(f'skip_tail_{index}'):
                        choices['pairs'][entry['key']] = {'aircraft': aircraft.pk, 'tailnumber': None}
                        continue
                    from flights.forms import TailNumberForm
                    rule = cleaned.get(f'operating_rules_{index}')
                    if not rule:
                        self.add_error(f'operating_rules_{index}', 'Choose one operating rule.')
                        continue
                    tail_form = TailNumberForm({'aircraft': aircraft.pk, 'registration': entry['source'],
                                                'operating_rules': rule}, user=self.user)
                    if not tail_form.is_valid():
                        for messages in tail_form.errors.values():
                            for message in messages:
                                self.add_error(None, f"{entry['source']}: {message}")
                    else:
                        self.pending_tail_forms.append((entry, tail_form))
                    continue
                if tail and tail.aircraft_id != aircraft.pk:
                    self.add_error(f'tailnumber_{index}', f'{tail.registration} belongs to {tail.aircraft.aircraft_type}. Choose that aircraft or a tailnumber assigned to {aircraft.aircraft_type}.')
                else:
                    choices['pairs'][entry['key']] = {'aircraft': aircraft.pk, 'tailnumber': tail.pk if tail else None}
        cleaned['resolution'] = choices
        return cleaned

    def rows(self):
        return [{**entry, 'aircraft_field': self[f'aircraft_{entry["index"]}'],
                 'tailnumber_field': None if self.aircraft_stage else self[f'tailnumber_{entry["index"]}'],
                 'new_tail': not self.aircraft_stage and entry.get('tailnumber') is None,
                 'skip_tail_field': self[f'skip_tail_{entry["index"]}'] if not self.aircraft_stage and entry.get('tailnumber') is None and not entry['required'] else None,
                 'operating_rules_field': self[f'operating_rules_{entry["index"]}'] if not self.aircraft_stage and entry.get('tailnumber') is None else None}
                for entry in self.entries]


def json_copy(value):
    import copy
    return copy.deepcopy(value)


class RowCorrectionForm(forms.Form):
    def __init__(self, *args, data_rows, page=1, errors=None, **kwargs):
        from .rows import PAGE_SIZE
        super().__init__(*args, **kwargs)
        self.data_rows = data_rows
        self.page_count = max(1, (len(data_rows['rows']) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page = max(1, min(page, self.page_count))
        self.entries = data_rows['rows'][(self.page - 1) * PAGE_SIZE:self.page * PAGE_SIZE]
        self.row_errors = errors or {}
        original_choices = data_rows.get('record_choices', {})
        aircraft_options = {value.casefold(): value for value in original_choices.get('aircraft', []) if value}
        pairs = {key: {value.casefold(): value for value in values} for key, values in original_choices.get('tailnumbers', {}).items()}
        for entry in data_rows['rows']:
            for values in (entry['original'], entry['values']):
                designator, registration = values[1].strip(), values[2].strip()
                if designator:
                    aircraft_options.setdefault(designator.casefold(), designator)
                    if registration:
                        pairs.setdefault(designator.casefold(), {}).setdefault(registration.casefold(), registration)
        self.aircraft_options = list(aircraft_options.values())
        self.tailnumber_options = {key: list(values.values()) for key, values in pairs.items()}
        for row in self.entries:
            line = row['line']
            self.fields[f'exclude_{line}'] = forms.BooleanField(required=False, initial=row['excluded'],
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
            for index, name in enumerate(data_rows['header']):
                self.fields[f'row_{line}_{index}'] = forms.CharField(required=False, initial=row['values'][index], strip=name != 'remarks',
                    label=LABELS.get(name, name.title()), widget=forms.TextInput(attrs={'class': 'form-control',
                    'aria-label': f'Row {line}: {LABELS.get(name, name.title())}'}))
            if self.aircraft_options:
                self.fields[f'row_{line}_1'] = forms.CharField(required=False, max_length=10, initial=row['values'][1], label='Aircraft Type',
                    widget=forms.Select(choices=[('', 'Choose aircraft from file')] + [(value, value) for value in self.aircraft_options] + [('__custom__', 'Enter another…')], attrs={'class': 'form-select', 'data-row-aircraft': str(line), 'aria-label': f'Row {line}: Aircraft Type'}))
            selected_aircraft = self.data.get(f'row_{line}_1', row['values'][1]) if self.is_bound else row['values'][1]
            registrations = list(self.tailnumber_options.get(str(selected_aircraft).casefold(), []))
            current = row['values'][2].strip()
            if current and current not in registrations:
                registrations.append(current)  # Preserve a conflicting source value for explicit correction.
            if registrations or self.tailnumber_options:
                self.fields[f'row_{line}_2'] = forms.CharField(required=False, max_length=10, initial=current, label='Tailnumber',
                    widget=forms.Select(choices=[('', 'Choose tailnumber from file')] + [(value, value) for value in registrations] + [('__custom__', 'Enter another…')], attrs={'class': 'form-select', 'data-row-tailnumber': str(line), 'aria-label': f'Row {line}: Tailnumber'}))

            for index in (1, 2):
                if isinstance(self.fields[f'row_{line}_{index}'].widget, forms.Select):
                    self.fields[f'custom_row_{line}_{index}'] = forms.CharField(required=False, max_length=10,
                        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter aircraft type' if index == 1 else 'Enter registration',
                            'aria-label': f'Row {line}: Enter aircraft type' if index == 1 else f'Row {line}: Enter registration'}))

    def clean(self):
        cleaned = super().clean()
        for row in self.entries:
            line = row['line']
            for index in (1, 2):
                name = f'row_{line}_{index}'
                if cleaned.get(name) == '__custom__':
                    value = cleaned.get(f'custom_row_{line}_{index}', '').strip()
                    if not value and not cleaned.get(f'exclude_{line}'):
                        self.add_error(f'custom_row_{line}_{index}', 'Enter a value.')
                    cleaned[name] = value
        return cleaned

    def corrected(self):
        data = json_copy(self.data_rows)
        for row in data['rows']:
            if row in self.entries:
                line = row['line']
                row['excluded'] = self.cleaned_data[f'exclude_{line}']
                updated = [self.cleaned_data[f'row_{line}_{i}'] for i in range(len(data['header']))]
                edited = set(row.get('edited_fields', []))
                conversions = dict(row.get('field_conversions', {}))
                for index, name in enumerate(data['header']):
                    if updated[index] != row['values'][index]:
                        import re
                        if name in HOUR_FIELDS and re.fullmatch(r'\d{1,3}:[0-5]\d', updated[index].strip()):
                            conversions[name] = 'HH:MM → decimal hours (nearest tenth)'
                        else:
                            conversions.pop(name, None)
                        if updated[index] == row['original'][index]:
                            edited.discard(name)
                        else:
                            edited.add(name)
                row['edited_fields'] = [name for name in data['header'] if name in edited]
                row['field_conversions'] = conversions
                row['values'] = updated
        return data

    def rows(self):
        result = []
        for row in self.entries:
            fields = []
            errors = self.row_errors.get(row['line'], {}) if not row['excluded'] else {}
            for index, name in enumerate(self.data_rows['header']):
                field = self[f'row_{row["line"]}_{index}']
                if name in errors:
                    field.field.widget.attrs['class'] += ' is-invalid'
                    field.field.widget.attrs['aria-invalid'] = 'true'
                fields.append({'field': field, 'custom_field': self[f'custom_row_{row["line"]}_{index}'] if f'custom_row_{row["line"]}_{index}' in self.fields else None, 'original': row['original'][index],
                               'error': errors.get(name), 'basic': index < 5 or name in errors})
            result.append({**row, 'fields': fields, 'basic_fields': [f for f in fields if f['basic']],
                'extra_fields': [f for f in fields if not f['basic']], 'errors': errors,
                'exclude': self[f'exclude_{row["line"]}']})
        return result


class OverlapReviewForm(forms.Form):
    def __init__(self, *args, issues, **kwargs):
        super().__init__(*args, **kwargs)
        from .overlaps import PAGE_SIZE
        self.issues = issues[:PAGE_SIZE]
        self.stale = False
        for issue in self.issues:
            line = issue['line']
            self.fields[f'decision_{line}'] = forms.ChoiceField(label=f'Row {line}',
                choices=[('exclude', 'Exclude incoming row'), ('include', 'Import anyway')],
                widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                error_messages={'required': 'Choose Exclude incoming row or Import anyway.'})
            self.fields[f'token_{line}'] = forms.CharField(initial=issue['token'], widget=forms.HiddenInput())

    def clean(self):
        cleaned = super().clean()
        for issue in self.issues:
            token = cleaned.get(f'token_{issue["line"]}')
            if token and token != issue['token']:
                self.stale = True
                self.add_error(None, 'Matching entries changed. Review the updated records and choose again.')
        return cleaned

    def rows(self):
        return [dict(issue, decision=self[f'decision_{issue["line"]}'], token_field=self[f'token_{issue["line"]}']) for issue in self.issues]
