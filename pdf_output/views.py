

from django.contrib.auth.decorators import login_required


from django.http import HttpResponse

from .pdf_generate_task import pdf_generate
from celery import Celery
from django.contrib import messages


@login_required
def PDFView(request, user_id):

    user_pk = request.user.pk

    pdf_generate.delay(user_pk)

    response = HttpResponse('Check your email')
    # response.write(pdf)
    # messages.add_message(request, messages.SUCCESS, "Logbook successfully created.")
    return response
