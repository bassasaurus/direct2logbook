from django import template

register = template.Library()

@register.simple_tag(name='addition')
def addition(*args):
    return round(sum(list(args)), 1)
