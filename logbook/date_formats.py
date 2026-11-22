"""Human-readable dates, independent of API and storage formats."""
from datetime import date, datetime

DISPLAY_DATE_FORMAT = 'M j, Y'
DATE_INPUT_FORMATS = ('%b %d, %Y', '%B %d, %Y', '%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y')
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def parse_date(value, formats=DATE_INPUT_FORMATS):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for pattern in formats:
        try:
            return datetime.strptime(str(value).strip(), pattern).date()
        except ValueError:
            continue
    raise ValueError('Enter a valid date, such as Nov 30, 2026.')


def display_date(value):
    if value is None or value == '':
        return ''
    value = parse_date(value)
    return f'{MONTHS[value.month - 1]} {value.day}, {value.year}'
