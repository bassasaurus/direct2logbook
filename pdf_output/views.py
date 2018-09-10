from django.conf import settings
from django.views.generic import ListView, TemplateView
from flights.models import Flight
from .pdf_output import pdf_output
from django_q.tasks import async_task

from django_weasyprint import WeasyTemplateResponseMixin

class LogView(TemplateView):
    # async_task(pdf_output())
    template_name = 'pdf_output/pdf_output.html'

class PDFView(WeasyTemplateResponseMixin, LogView):
    pdf_stylesheets = [
        settings.BASE_DIR + '/pdf_output/static/pdf_output/css/pdf_output.css',
        settings.BASE_DIR + '/flights/static/flights/custom.css',
        settings.BASE_DIR + '/flights/static/flights/scss/bootstrap/bootstrap.css',
    ]
