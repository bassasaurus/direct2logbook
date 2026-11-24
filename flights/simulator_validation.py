"""Validate simulator details in selection order, without cascading prompts."""


def validate_simulator_entry(values, *, require_device=True, aircraft_category=None):
    if not values.get('simulator'):
        return {}
    credit = values.get('instrument_credit_eligible', False)
    if not require_device and not credit:
        return {}  # Preserve old-client writes which omit the new device fields.
    kind = values.get('device_type')
    if kind not in ('FFS', 'FTD', 'ATD'):
        return {'device_type': 'Select device type.'}
    if kind == 'ATD' and values.get('atd_type') not in ('BATD', 'AATD'):
        return {'atd_type': 'Select BATD or AATD.'}
    if not (values.get('device_id') or '').strip():
        return {'device_id': 'Device ID required.'}
    if credit and aircraft_category != 'A':
        return {'instrument_credit_eligible': 'Airplane device required.'}
    if credit and not values.get('dual'):
        return {'dual': 'Dual required.'}
    duration = values.get('duration') or 0
    instrument = values.get('simulated_instrument') or 0
    if duration <= 0:
        return {'duration': 'Duration required.'} if credit else {}
    if instrument > duration:
        return {'simulated_instrument': 'Cannot exceed duration.'}
    if credit and instrument <= 0:
        return {'simulated_instrument': 'Instrument time required.'}
    return {}
