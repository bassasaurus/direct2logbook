from django import template
from django.utils.safestring import mark_safe

register = template.Library()

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
