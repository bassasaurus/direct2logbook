from django.views.generic import ListView
from flights.models import Flight
from easy_pdf.views import PDFTemplateResponseMixin, PDFTemplateView
from django.core.paginator import Paginator


class PDFTemplateResponseMixin(PDFTemplateResponseMixin):
    download_filename = "logbook.pdf"

class PDFTemplateView(PDFTemplateView):
    template_name = "pdf_output/pdf_output.html"

class PrintView(ListView, PDFTemplateView, PDFTemplateResponseMixin):
    model = Flight
    context_object_name = 'flights'

    def object_list(self, **kwargs):
        object_list = Flight.objects.all()[:80]
        return(object_list)
