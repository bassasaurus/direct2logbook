from django.conf import settings
from django.views.generic import TemplateView
from flights.models import Flight
from .pdf_output import pdf_output
from flights.views import UserObjectsMixin, LoginRequiredMixin
from django_weasyprint import WeasyTemplateResponseMixin
from django.core.mail import EmailMessage
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

from weasyprint import HTML, CSS

from redis import Redis
from rq import Queue
from rq.decorators import job

redis_conn = Redis()
q = Queue('pdf', connection = redis_conn)

@login_required
def PDFView(request, user_id):
    user = request.user
    objects = Flight.objects.filter(user=user).order_by('date')

    pdf_output(objects, user)

    user_pdf_cache = 'user_pdf_cache_{}'.format(user.id)
    data = cache.get(user_pdf_cache)
    return HttpResponse(data)

    # logbook = HTML('pdf_output/templates/pdf_output/log_table.html') #where pdf_output writes the file
    # logbook.write_pdf('logbook.pdf') # where can this be saved? Profile.file_field

    # user_email = request.user.email
    # if request.method == 'POST':
    #
    #     email = EmailMessage(
    #         'Your Logbook', #subject
    #         'This oughtta be a sweet Logbook.pdf', #message
    #         'no-reply@direct2logbook.com', #from
    #         [user_email], #to
    #         )
    #     attachment = open('pdf_output/templates/pdf_output/log_table.html', 'r')
    #     email.attach('log_table.html', attachment.read())
    #     email.send(fail_silently=False)
    # html = ""
    # return HttpResponse(html)
