from django.shortcuts import render
from django.views.generic import ListView
from flights.models import Flight
from easy_pdf.views import PDFTemplateView

class PrintView(PDFTemplateView, ListView):
    model = Flight
    template_name = 'pdf_output/pdf_output.html'
    context_object_name = 'flights'

    def object_list(self, **kwargs):
        return Flight.objects.all()[:40]

    def get_context_data(self, **kwargs):

        return super(PrintView, self).get_context_data(
            pagesize='A4',
            title='Logbook',
            **kwargs
        )
