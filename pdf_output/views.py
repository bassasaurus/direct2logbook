from django.conf import settings
from django.views.generic import ListView, TemplateView
from flights.models import Flight
from django.core.cache import cache
from .pdf_output import pdf_output

from django_weasyprint import WeasyTemplateResponseMixin


class PDFView(TemplateView):
    template_name = 'pdf_output/pdf_output.html'
    pdf_output()

class PrintView(WeasyTemplateResponseMixin, PDFView):
    pdf_stylesheets = [
        settings.BASE_DIR + '/pdf_output/static/pdf_output/css/pdf_output.css',
    ]
