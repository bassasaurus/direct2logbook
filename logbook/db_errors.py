"""Safe database failure feedback. Never put database exception text in a response."""
import logging
from django.db import DatabaseError
from django.http import HttpResponse

logger = logging.getLogger(__name__)
MESSAGES = {
    'reminder_ipc_complete': ('ipc_completed_date', 'Enter the IPC completion date.'),
    'reminder_instructor_complete': ('instructor_period_start', 'Enter the recent-experience period start date.'),
    'reminder_condition_valid': ('condition', 'Choose a flight condition.'),
    'reminder_condition_required': ('condition', 'Choose a flight condition.'),
    'reminder_user_flight_review_unique': ('kind', 'A Flight Review reminder already exists. Edit it to record your latest qualifying event.'),
    'reminder_flight_review_complete': (None, 'Enter the last qualifying date and choose a completion type.'),
    'aircraft_user_type_ci_unique': ('aircraft_type', 'This aircraft type already exists in your logbook.'),
    'tailnumber_user_reg_ci_unique': ('registration', 'This tailnumber already exists in your logbook.'),
    'unique tailnumber': ('registration', 'This tailnumber already exists in your logbook.'),
    'aircraft_type_nonempty': ('aircraft_type', 'Required'),
    'flight_route_nonempty': ('route', 'Required'),
    'flight_registration_required': ('registration', 'Choose a tailnumber.'),
    'flight_device_type_valid': ('device_type', 'Select device type.'),
    'tailnumber_reg_nonempty': ('registration', 'Required'),
    'reminder_target_positive': ('target_hours', 'Target hours must be greater than 0.'),
    'reminder_milestone_target': ('target_hours', 'Required'),
    'reminder_company_date_order': ('company_end_date', 'End date must be on or after the start date.'),
    'reminder_type_aircraft': ('aircraft', 'Required'),
    'flight_hours_nonnegative': (None, 'Hours cannot be negative.'),
    'imported_hours_nonnegative': (None, 'Hours cannot be negative.'),
    'flight_tailnumber_aircraft_fk': ('registration', 'Choose a tailnumber assigned to the selected aircraft type.'),
}
for name, field, label in (
    ('tailnumber_aircraft_owner_fk', 'aircraft', 'aircraft'),
    ('flight_aircraft_owner_fk', 'aircraft_type', 'aircraft'),
    ('flight_tailnumber_owner_fk', 'registration', 'tailnumber'),
    ('imported_aircraft_owner_fk', 'aircraft_type', 'aircraft'),
    ('reminder_aircraft_owner_fk', 'aircraft', 'aircraft'),
):
    MESSAGES[name] = (field, f'This {label} is no longer available. Choose one from your list.')


def database_feedback(error, resource='record'):
    constraint = getattr(getattr(error.__cause__, 'diag', None), 'constraint_name', None)
    if constraint in MESSAGES:
        field, message = MESSAGES[constraint]
        return {field or 'non_field_errors': [message]}, 400
    return {'non_field_errors': [f'Couldn’t save this {resource}. Please try again.']}, 503


def exception_handler(error, context):
    from rest_framework.views import exception_handler as default_handler
    from rest_framework.response import Response
    if not isinstance(error, DatabaseError):
        return default_handler(error, context)
    logger.exception('Database failure during API write', exc_info=error)
    data, status = database_feedback(error)
    return Response(data, status=status)


class FriendlyDatabaseErrorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, error):
        if isinstance(error, DatabaseError):
            logger.exception('Database failure during web request', exc_info=error)
            # Standalone HTML: rendering a database-backed layout during an outage can fail again.
            return HttpResponse('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>Please try again</title><main style="max-width:40rem;margin:3rem auto;padding:1rem;font-family:system-ui">'
                '<h1>Couldn’t complete this request.</h1><p>Please try again. Your saved records have not been removed.</p>'
                '<p>Use your browser’s Back button to return to your form.</p></main></html>', status=503)
