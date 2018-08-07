from django.conf import settings
from django.views.generic import ListView, TemplateView
from flights.models import Flight
from .pdf_output import pdf_output

from django_weasyprint import WeasyTemplateResponseMixin


class LogView(TemplateView):
    pdf_output()
    template_name = 'pdf_output/pdf_output.html'


class PDFView(WeasyTemplateResponseMixin, LogView):
    pdf_stylesheets = [
        settings.BASE_DIR + '/pdf_output/static/pdf_output/css/pdf_output.css',
    ]
