from django.test import SimpleTestCase
from django.urls import reverse, resolve
from csv_app.views import csv_download_view, csv_inspect_view, csv_upload_view


class TestCSVAppURLs(SimpleTestCase):

    def test_csv_download_url_resolves(self):
        url = reverse('csv_download')
        self.assertEqual(resolve(url).func, csv_download_view)

    def test_csv_inspect_url_resolves(self):
        url = reverse('csv_inspect')
        self.assertEqual(resolve(url).func, csv_inspect_view)

    def test_csv_upload_url_resolves(self):
        url = reverse('csv_upload')
        self.assertEqual(resolve(url).func, csv_upload_view)
