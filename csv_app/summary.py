"""Final review uses the same rounded, typed payload as the import service."""
from decimal import Decimal
from .validation import parse_csv
from .mapping import LABELS


def import_summary(batch):
    rows, _ = parse_csv(batch.content)
    flights = [row for row in rows if not row['simulator']]
    devices = [row for row in rows if row['simulator']]
    staged = batch.row_data.get('rows', [])
    edited = [{'line': row['line'], 'fields': [LABELS.get(name, name.title()) for name in row.get('edited_fields', [])]}
              for row in staged if not row['excluded'] and row.get('edited_fields')]
    excluded = [row['line'] for row in staged if row['excluded']]
    warnings = list(dict.fromkeys(batch.source_metadata.get('conversion_notes', [])))
    for row in staged:
        if not row['excluded']:
            warnings.extend(LABELS.get(name, name.title()) + ': ' + note for name, note in row.get('field_conversions', {}).items())
    warnings.append('Hours are rounded to the nearest tenth.')
    roles = ('pilot_in_command', 'second_in_command', 'cross_country', 'instructor', 'dual', 'solo')
    if any(any(row.get(role) for role in roles) for row in rows):
        warnings.append('Selected roles and Cross-country apply to the full entry duration.')
    if any(row['approaches'] for row in rows):
        warnings.append('Approach types and counts are preserved. Counts without a type are stored as unspecified.')
    if any(row.get('hold') for row in rows):
        warnings.append('Holding is recorded as Yes/No; positive holding counts mean Yes.')
    if batch.column_mapping.get('duration', {}).get('calculated') == 'block_times':
        warnings.append('Duration is calculated from Block In minus Block Out, rounded to the nearest tenth.')
    if batch.source_metadata.get('short_years_confirmed'):
        warnings.append('Two-digit years expanded using the confirmed century rule.')
    if batch.source_metadata.get('block_overnight_confirmed'):
        warnings.append('Clock-only overnight crossings treat Block In as the next day.')
    if batch.source_metadata.get('block_duration_differences_confirmed'):
        warnings.append('You chose the selected Duration values where they differed from block times or could not be compared.')
    return {
        'entry_count': len(rows), 'flight_count': len(flights), 'device_count': len(devices),
        'flight_hours': sum((row['duration'] for row in flights), Decimal('0.0')),
        'device_hours': sum((row['duration'] for row in devices), Decimal('0.0')),
        'date_start': min(row['date'] for row in rows), 'date_end': max(row['date'] for row in rows),
        'edited_count': len(edited), 'excluded_count': len(excluded),
        'edited_rows': edited, 'excluded_rows': excluded,
        'overlap_included_count': sum(not row['excluded'] and batch.overlap_review.get(str(row['line']), {}).get('action') == 'include' for row in staged),
        'warnings': list(dict.fromkeys(warnings)),
    }


def note_route_conversion(batch, before, after):
    import csv
    import io
    routes = lambda content: [record[3] for record in list(csv.reader(io.StringIO(content)))[1:] if any(record)]
    if routes(before) != routes(after):
        notes = batch.source_metadata.setdefault('conversion_notes', [])
        if 'Route airport codes normalized.' not in notes:
            notes.append('Route airport codes normalized.')
