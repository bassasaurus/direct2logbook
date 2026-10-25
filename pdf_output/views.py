import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from kombu.exceptions import OperationalError

from .pdf_generate_task import pdf_generate


logger = logging.getLogger('django.pdf_output')


@login_required
@require_POST
@csrf_protect
def PDFView(request, user_id):
    # The URL and request body must never choose another user's export.
    try:
        task = pdf_generate.apply_async(args=(request.user.pk,), retry=False)
    except OperationalError:
        logger.exception('Could not confirm PDF task submission for user_id=%s', request.user.pk)
        return JsonResponse({
            'status': 'unconfirmed',
            'message': (
                'We could not confirm your PDF request. It may still have been queued. '
                'Please check your email before requesting another copy.'
            ),
        }, status=503)

    return JsonResponse({
        'status': 'queued',
        'task_id': task.id,
        'email': request.user.email,
    }, status=202)
