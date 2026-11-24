import uuid
from html.parser import HTMLParser
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from flights.forms import FlightForm
from flights.models import Aircraft


@override_settings(SECURE_SSL_REDIRECT=False)
class WebAircraftDefaultTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('web-default')
        self.user.profile.trial = True
        self.user.profile.save()
        self.other = get_user_model().objects.create_user('foreign-default')
        self.first = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        self.second = Aircraft.objects.create(user=self.user, aircraft_type='737')
        self.foreign = Aircraft.objects.create(user=self.other, aircraft_type='FOREIGN')
        self.web = APIClient(enforce_csrf_checks=True)
        self.web.force_login(self.user)
        page = self.web.get(reverse('aircraft_list'))
        self.assertEqual(page.status_code, 200)
        class CSRFInput(HTMLParser):
            token = None
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'input' and attrs.get('name') == 'csrfmiddlewaretoken':
                    self.token = attrs.get('value')
        parser = CSRFInput()
        parser.feed(page.content.decode())
        self.assertIsNotNone(parser.token)
        self.csrf = parser.token
        self.path = reverse('mobile_default_aircraft')
        self.mobile = APIClient()
        self.mobile.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.get_or_create(user=self.user)[0].key)

    def operation(self, code, revision=None):
        return {'operation_id': str(uuid.uuid4()), 'action': 'update',
                'base_revision': revision or self.web.get(self.path).data['revision'],
                'data': {'aircraft_type': code}}

    def post(self, payload):
        return self.web.post(self.path, payload, format='json', HTTP_X_CSRFTOKEN=self.csrf)

    def test_web_selection_is_the_same_account_default_mobile_downloads(self):
        self.assertEqual(self.post(self.operation('C172')).status_code, 200)
        self.assertEqual(self.mobile.get(self.path).data['aircraft_type'], 'C172')
        self.assertEqual(FlightForm(user=self.user).initial['aircraft_type'], self.first.pk)
        self.assertEqual(self.post(self.operation('737')).status_code, 200)
        self.assertEqual(list(Aircraft.objects.filter(user=self.user, is_default=True).values_list('pk', flat=True)), [self.second.pk])
        self.assertEqual(self.post(self.operation('')).status_code, 200)
        self.assertEqual(self.mobile.get(self.path).data['aircraft_type'], '')

    def test_mobile_selection_is_checked_when_web_list_loads(self):
        payload = self.operation('737')
        self.assertEqual(self.mobile.post(self.path, payload, format='json').status_code, 200)
        page = self.web.get(reverse('aircraft_list'))
        self.assertContains(page, f'id="default-aircraft-{self.second.pk}"')
        self.assertContains(page, 'data-default-aircraft-code="737" checked')
        self.assertNotContains(page, 'data-default-aircraft-code="FOREIGN"')
        self.assertEqual(FlightForm(user=self.user).initial['aircraft_type'], self.second.pk)

    def test_csrf_is_required_for_browser_writes(self):
        response = self.web.post(self.path, self.operation('C172'), format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Aircraft.objects.filter(user=self.user, is_default=True).exists())

    def test_foreign_aircraft_and_stale_web_selection_cannot_overwrite_default(self):
        self.assertEqual(self.post(self.operation('FOREIGN')).status_code, 400)
        stale = self.operation('C172')
        self.assertEqual(self.mobile.post(self.path, self.operation('737'), format='json').status_code, 200)
        self.assertEqual(self.post(stale).status_code, 409)
        self.assertEqual(self.web.get(self.path).data['aircraft_type'], '737')

    def test_list_includes_checkbox_for_types_without_tailnumbers(self):
        page = self.web.get(reverse('aircraft_list'))
        self.assertEqual(len(page.context['aircraft_groups']), 2)
        self.assertContains(page, f'id="default-aircraft-{self.first.pk}"')
        self.assertContains(page, f'id="default-aircraft-{self.second.pk}"')

    def test_explicit_create_selection_is_not_replaced_by_default(self):
        self.post(self.operation('C172'))
        form = FlightForm(user=self.user, initial={'aircraft_type': self.second.pk})
        self.assertEqual(form.initial['aircraft_type'], self.second.pk)
