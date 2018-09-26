from django.conf import settings
from django.views.generic import TemplateView
from flights.models import Flight
from .pdf_output import pdf_output
from django.http import HttpResponse
from flights.views import UserObjectsMixin, LoginRequiredMixin
from django_weasyprint import WeasyTemplateResponseMixin
from rq.decorators import job
from redis import Redis
from rq import Queue
from multiprocessing import Process


q = Queue(connection=Redis())

class LogView(TemplateView, UserObjectsMixin, LoginRequiredMixin):
    # objects = Flight.objects.filter().order_by('date')[:50]
    objects = Flight.objects.filter().order_by('date') #ordered 'bottom up' model is 'top down'
    pdf_output(objects)
    template_name = 'pdf_output/pdf_output.html'

class PDFView(WeasyTemplateResponseMixin, LogView):
    pdf_stylesheets = [
        settings.BASE_DIR + '/pdf_output/static/pdf_output/css/pdf_output.css',
        settings.BASE_DIR + '/flights/static/flights/custom.css',
        settings.BASE_DIR + '/flights/static/flights/scss/bootstrap/bootstrap.css',
    ]
    # pdf_filename = 'logbook.pdf'

    @job('low', connection=Redis(), timeout='10m')
    def render_to_response(self, context, **response_kwargs):

        """
        Renders PDF document and prepares response by calling on
        :attr:`response_class` (default: :class:`WeasyTemplateResponse`).
        :returns: Django HTTP response
        :rtype: :class:`django.http.HttpResponse`
        """
        response_kwargs.update({
            'attachment': self.pdf_attachment,
            'filename': self.get_pdf_filename(),
            'stylesheets': self.get_pdf_stylesheets(),
        })
        return super(WeasyTemplateResponseMixin, self).render_to_response(
            context, **response_kwargs
        )

    render_to_response.delay(3, 4)
