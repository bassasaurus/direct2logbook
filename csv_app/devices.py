"""Classify only explicit training-device descriptions, never aircraft models."""
import re
from .validation import CSVValidationError


def device_classification(kind, level=''):
    key = re.sub(r'[^A-Z0-9]', '', kind.upper())
    kinds = {'FFS':'FFS','FULLFLIGHTSIMULATOR':'FFS',
             'FTD':'FTD','FLIGHTTRAININGDEVICE':'FTD',
             'ATD':'ATD','AVIATIONTRAININGDEVICE':'ATD',
             'BATD':'BATD','BASICAVIATIONTRAININGDEVICE':'BATD',
             'AATD':'AATD','ADVANCEDAVIATIONTRAININGDEVICE':'AATD'}
    level = level.strip().upper()
    if not key:
        return ('ATD', level) if level in ('BATD','AATD') else ('',level)
    code = kinds.get(key)
    if not code:
        raise CSVValidationError('Device type: Select FFS, FTD, ATD, BATD or AATD.')
    if code in ('BATD','AATD'):
        if level and level != code:
            raise CSVValidationError('ATD type: Must match the selected device type.')
        return 'ATD', code
    return code, level
