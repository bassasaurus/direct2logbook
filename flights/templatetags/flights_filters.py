from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import urlize
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def distance_display(value, unit='nm'):
    from flights.mileage import format_distance
    return format_distance(value, unit)


@register.filter
def remarks_links(value):
    # Treat remarks as plain text before Django generates escaped links.
    text = str.__str__(str(value))
    links = urlize(text, nofollow=True, autoescape=True)
    return mark_safe(links.replace('<a href="', '<a target="_blank" href="'))


@register.filter("iconbool", is_safe=True)
def iconbool(value):
    """Given a boolean value, this filter outputs an icon + the
    word "Yes" or "No"

    Example Usage:

        {{ user.has_widget|iconbool }}

    """
    if bool(value):
        result = '<i class="material-icons">done</i>'
    else:
        result = '-'
    return mark_safe(result)


@register.filter
def zero_dash(value):
    """Display numeric zero as a dash without changing nonzero formatting."""
    if value is None or isinstance(value, bool):
        return value
    try:
        if Decimal(str(value).strip()).is_zero():
            return '-'
    except (InvalidOperation, ValueError, TypeError):
        pass
    return value
