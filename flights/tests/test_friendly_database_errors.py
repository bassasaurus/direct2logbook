from types import SimpleNamespace
from django import forms
from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError
from django.http import JsonResponse
from django.test import RequestFactory, TestCase
from django.views.generic import CreateView
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from flights.forms import UserOwnedRelationsFormMixin
from flights.models import Aircraft
from flights.views import UserOwnedFormViewMixin
from logbook.db_errors import database_feedback, FriendlyDatabaseErrorsMiddleware


def failure(constraint=None):
    error = IntegrityError('PRIVATE SQL and record values')
    cause = Exception('PRIVATE driver diagnostics')
    cause.diag = SimpleNamespace(constraint_name=constraint)
    error.__cause__ = cause
    return error


class ExampleForm(UserOwnedRelationsFormMixin, forms.ModelForm):
    class Meta:
        model = Aircraft
        fields = ['aircraft_type']


class FailingView(UserOwnedFormViewMixin, CreateView):
    model = Aircraft
    form_class = ExampleForm

    def form_valid(self, form):
        Aircraft.objects.bulk_create([Aircraft(user=self.request.user, aircraft_type='ROLLBACK')])
        raise failure(self.request.GET.get('constraint'))

    def render_to_response(self, context, **kwargs):
        form = context['form']
        return JsonResponse({'value': form['aircraft_type'].value(), 'errors': dict(form.errors)}, **kwargs)


class FriendlyDatabaseErrorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.bulk_create([get_user_model()(username='friendly-errors')])[0]

    def test_known_duplicate_is_field_feedback_and_unknown_is_retryable(self):
        data, status = database_feedback(failure('aircraft_user_type_ci_unique'))
        self.assertEqual(status, 400)
        self.assertEqual(data['aircraft_type'], ['This aircraft type already exists in your logbook.'])
        data, status = database_feedback(failure('internal_summary_constraint'), 'flight')
        self.assertEqual(status, 503)
        self.assertEqual(data['non_field_errors'], ['Couldn’t save this flight. Please try again.'])
        self.assertNotIn('PRIVATE', str(data))

    def test_web_save_preserves_input_and_rolls_back_partial_writes(self):
        for constraint, status in [('aircraft_user_type_ci_unique', 400), ('unknown', 503)]:
            request = RequestFactory().post('/?constraint=' + constraint, {'aircraft_type': 'A320'})
            request.user = self.user
            with self.assertLogs('logbook.db_errors', level='ERROR'):
                response = FailingView.as_view()(request)
            self.assertEqual(response.status_code, status)
            self.assertIn('A320', response.content.decode())
            self.assertNotIn('PRIVATE', response.content.decode())
            self.assertFalse(Aircraft.objects.filter(aircraft_type='ROLLBACK').exists())

    def test_api_database_error_never_returns_driver_text(self):
        class BrokenAPI(APIView):
            authentication_classes = []
            permission_classes = []
            def post(self, request):
                raise failure('tailnumber_user_reg_ci_unique')
        with self.assertLogs('logbook.db_errors', level='ERROR'):
            response = BrokenAPI.as_view()(APIRequestFactory().post('/'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'registration': ['This tailnumber already exists in your logbook.']})

    def test_database_outage_fallback_does_not_render_database_backed_template(self):
        with self.assertLogs('logbook.db_errors', level='ERROR'):
            response = FriendlyDatabaseErrorsMiddleware(lambda request: None).process_exception(
                RequestFactory().get('/'), DatabaseError('PRIVATE SQL'))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('PRIVATE', response.content.decode())

    def test_mismatch_and_negative_hours_are_friendly_before_database_write(self):
        from flights.forms import FlightForm, ImportedForm
        from flights.models import TailNumber
        first, second = Aircraft.objects.bulk_create([
            Aircraft(user=self.user, aircraft_type='A320'), Aircraft(user=self.user, aircraft_type='737')])
        tail = TailNumber.objects.bulk_create([TailNumber(user=self.user, aircraft=second, registration='N123AB')])[0]
        form = FlightForm(data={'date': '01/01/2026', 'route': 'KIAH', 'duration': '-1',
            'aircraft_type': first.pk, 'registration': tail.pk, 'pilot_in_command': True}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['registration'], ['N123AB is assigned to 737. Choose a tailnumber for A320.'])
        self.assertTrue(all(message == 'Hours cannot be negative.' for message in form.errors['duration']))
        self.assertIn('is-invalid', form.fields['duration'].widget.attrs['class'])
        imported = ImportedForm(data={'aircraft_type': first.pk, 'total_time': '-1'}, user=self.user)
        self.assertFalse(imported.is_valid())
        self.assertEqual(imported.errors['total_time'], ['Hours cannot be negative.'])
        self.assertNotIn('Constraint', str(imported.errors))
