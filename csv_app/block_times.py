"""Calculate elapsed block time without guessing time zones or overnight dates."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .validation import CSVValidationError


class OvernightConfirmationRequired(CSVValidationError):
    pass


def elapsed_hours(out_value, in_value, allow_overnight=False):
    values = [str(out_value).strip(), str(in_value).strip()]
    clocks = [re.fullmatch(r'([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?', value) for value in values]
    if all(clocks):
        seconds = [int(match[1]) * 3600 + int(match[2]) * 60 + int(match[3] or 0) for match in clocks]
        elapsed = seconds[1] - seconds[0]
        if elapsed < 0:
            if not allow_overnight:
                raise OvernightConfirmationRequired('Confirm that Block In is the next day, or include dates in the block times.')
            elapsed += 24 * 3600
    elif not any(clocks):
        try:
            if not all(re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', value) for value in values):
                raise ValueError()
            out_time, in_time = [datetime.fromisoformat(value.replace('Z', '+00:00')) for value in values]
            if (out_time.utcoffset() is None) != (in_time.utcoffset() is None):
                raise ValueError()
            elapsed = (in_time - out_time).total_seconds()
        except (ValueError, TypeError):
            raise CSVValidationError('Use HH:MM for both block times, or YYYY-MM-DD HH:MM with matching time zones or UTC offsets.') from None
    else:
        raise CSVValidationError('Use clock times for both block columns, or include dates in both.')
    if elapsed <= 0:
        raise CSVValidationError('Block In must be later than Block Out.')
    return (Decimal(str(elapsed)) / Decimal(3600)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def rounded_duration(value, time_units='hours'):
    value = str(value).strip()
    clock = re.fullmatch(r'(\d{1,3}):([0-5]\d)', value)
    try:
        number = Decimal(clock[1]) + Decimal(clock[2]) / 60 if clock else Decimal(value)
        if not number.is_finite() or number < 0:
            raise InvalidOperation()
        if not clock and time_units == 'minutes':
            number /= 60
        return number.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
