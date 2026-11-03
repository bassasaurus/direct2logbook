from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse


class ContextLinkSpacingTests(SimpleTestCase):
    def render(self, name):
        kwargs = {'pk': 1} if name in ('flight_detail', 'aircraft_detail', 'tailnumber_detail') else {}
        request = RequestFactory().get(reverse(name, kwargs=kwargs))
        request.resolver_match = resolve(request.path)
        return render_to_string('blocks/breadcrumb.html', {
            'request': request, 'user': SimpleNamespace(is_authenticated=True),
            'flight': SimpleNamespace(pk=1), 'aircraft': SimpleNamespace(pk=1),
            'tailnumber': SimpleNamespace(pk=1),
            'previous_flight': SimpleNamespace(pk=2), 'next_flight': SimpleNamespace(pk=3),
        })

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
