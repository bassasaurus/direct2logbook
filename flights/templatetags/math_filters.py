from django import template

register = template.Library()


@register.simple_tag(name='addition')
def addition(*args):
    for i in args:
        if i == '':
            i = 0
        else:
            pass
        
    # return None
    return round(sum(list(args)), 1)
