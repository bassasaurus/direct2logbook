from django import template
from logbook.date_formats import display_date

register = template.Library()

@register.filter(name='display_date')
def display_date_filter(value):
    try:
        return display_date(value)
    except (ValueError, TypeError):
        return value
