"""Named-route rules for the shared page action row."""
from django import template

register = template.Library()

FLIGHT_ACTION_PAGES = frozenset({
    'home', 'flight_list', 'flight_detail', 'remarks',
    'flight_by_date', 'flight_by_year', 'flight_by_month',
    'aircraft_detail', 'tailnumber_detail', 'tailnumber_list',
    'imported_list', 'imported_detail',
})


@register.inclusion_tag('blocks/page_actions.html', takes_context=True)
def page_actions(context):
    request = context.get('request')
    match = getattr(request, 'resolver_match', None)
    route = getattr(match, 'url_name', None)
    values = context.flatten()
    values.update({
        'show_page_actions': route in FLIGHT_ACTION_PAGES or route == 'aircraft_list',
        'aircraft_actions': route == 'aircraft_list',
        'show_remarks_action': route == 'flight_list',
        'show_pdf_action': route == 'home',
        'show_displayed_range': route == 'flight_list' and bool(context.get('page_flights')),
    })
    return values
