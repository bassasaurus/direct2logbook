from django import template
from django.utils import timezone

from operations.server_memory import memory_snapshot

register = template.Library()


@register.inclusion_tag('admin/server_memory.html', takes_context=True)
def server_memory(context):
    request = context.get('request')
    if request is None or not request.user.is_active or not request.user.is_staff:
        return {'show_memory': False}
    return {'show_memory': True, 'memory': memory_snapshot(), 'checked_at': timezone.now()}
