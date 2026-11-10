from types import SimpleNamespace

from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse


class ContextLinkSpacingTests(SimpleTestCase):
    def render(self, name):
        kwargs = {'pk': 1} if name.endswith(('_detail', '_update', '_delete')) else {}
        request = RequestFactory().get(reverse(name, kwargs=kwargs))
        request.resolver_match = resolve(request.path)
        return Template("{% load page_navigation %}{% include 'blocks/breadcrumb.html' %}{% page_actions %}").render(Context({
            'request': request, 'user': SimpleNamespace(is_authenticated=True),
            'flight': SimpleNamespace(pk=1), 'aircraft': SimpleNamespace(pk=1),
            'tailnumber': SimpleNamespace(pk=1), 'can_delete': True,
            'previous_flight': SimpleNamespace(pk=2), 'next_flight': SimpleNamespace(pk=3),
        }))

    def test_detail_navigation_precedes_record_actions(self):
        for name in ('flight_detail', 'aircraft_detail', 'tailnumber_detail'):
            with self.subTest(name=name):
                html = self.render(name)
                self.assertLess(html.index('>Update</a>'), html.index('>Delete</a>'))
                self.assertLess(html.index('>Delete</a>'), html.index('>New Flight</a>'))
                self.assertEqual(html.count('>New Flight</a>'), 1)
                self.assertIn('context-navigation-links', html)

    def test_remarks_is_absent_from_general_action_rows(self):
        for name in ('flight_list', 'flight_detail'):
            with self.subTest(name=name):
                self.assertNotIn('>Remarks</a>', self.render(name))

    def test_home_pdf_controls_are_retained_with_shared_spacing(self):
        html = self.render('home')
        self.assertIn('context-navigation-links', html)
        self.assertIn('id="pdf"', html)
        self.assertIn('id="pdf-request-status"', html)
        self.assertLess(html.index('>New Flight</a>'), html.index('id="pdf"'))

    def test_previously_hidden_toolbars_are_still_hidden(self):
        for name in ('profile', 'flight_create'):
            with self.subTest(name=name):
                self.assertNotIn('>New Flight</a>', self.render(name))

    def test_aircraft_list_uses_aircraft_actions_once(self):
        html = self.render('aircraft_list')
        self.assertEqual(html.count('>New Aircraft</a>'), 1)
        self.assertEqual(html.count('>New Tailnumber</a>'), 1)
        self.assertNotIn('>New Flight</a>', html)
        self.assertEqual(html.count('class="page-action-divider"'), 1)

    def test_create_update_delete_pages_have_no_action_row_or_divider(self):
        for name in ('flight_create', 'aircraft_create', 'tailnumber_create', 'imported_create',
                     'flight_update', 'aircraft_update', 'tailnumber_update', 'imported_update',
                     'flight_delete', 'aircraft_delete', 'tailnumber_delete', 'imported_delete'):
            with self.subTest(name=name):
                html = self.render(name)
                self.assertNotIn('aria-label="Page actions"', html)
                self.assertNotIn('page-action-divider', html)

    def test_visible_rows_have_exactly_one_divider(self):
        for name in ('home', 'flight_list', 'flight_detail', 'aircraft_detail',
                     'tailnumber_detail', 'aircraft_list', 'remarks', 'flight_by_date'):
            with self.subTest(name=name):
                self.assertEqual(self.render(name).count('class="page-action-divider"'), 1)

    def test_home_button_spelling_and_status_url(self):
        request = RequestFactory().get(reverse('home'))
        request.resolver_match = resolve(request.path)
        from uuid import UUID
        identifier = UUID('00000000-0000-0000-0000-000000000001')
        html = Template('{% load page_navigation %}{% page_actions %}').render(Context({
            'request': request, 'pdf_request': SimpleNamespace(pk=identifier),
        }))
        self.assertIn('Print Logbook', html)
        self.assertIn('data-status-url="' + reverse('pdf_status', args=[identifier]) + '"', html)

    def test_logbook_range_is_oldest_to_newest(self):
        from datetime import date
        request = RequestFactory().get(reverse('flight_list'))
        request.resolver_match = resolve(request.path)
        html = Template('{% load page_navigation %}{% page_actions %}').render(Context({
            'request': request,
            'page_flights': [SimpleNamespace(date=date(2026, 11, 3)), SimpleNamespace(date=date(2026, 10, 1))],
        }))
        self.assertIn('Displayed Range', html)
        self.assertIn('10/01/2026 – 11/03/2026', html)

    def test_error_record_actions_keep_their_colors(self):
        request = RequestFactory().get(reverse('aircraft_detail', args=[1]))
        request.resolver_match = resolve(request.path)
        html = Template("{% include 'blocks/breadcrumb.html' %}").render(Context({
            'request': request, 'aircraft': SimpleNamespace(pk=1), 'detail_has_errors': True, 'can_delete': True,
        }))
        self.assertIn('btn btn-outline-danger', html)
        self.assertIn('text-danger detail-delete', html)
