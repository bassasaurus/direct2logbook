import logging
import uuid

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from .models import PDFRequest
from kombu.exceptions import OperationalError

from .pdf_generate_task import pdf_generate


logger = logging.getLogger('django.pdf_output')


@login_required
@require_POST
@csrf_protect
def PDFView(request, user_id):
    # The URL and request body must never choose another user's export.
    job = PDFRequest.objects.create(user=request.user, task_id=str(uuid.uuid4()))
    status_url = reverse('pdf_status', args=[job.pk])
    try:
        pdf_generate.apply_async(
            args=(request.user.pk,), kwargs={'request_id': str(job.pk)},
            task_id=job.task_id, retry=False,
        )
    except OperationalError:
        logger.exception('Could not confirm PDF task submission for user_id=%s', request.user.pk)
        PDFRequest.objects.filter(pk=job.pk, status=PDFRequest.Status.QUEUED).update(
            status=PDFRequest.Status.UNCONFIRMED, updated_at=timezone.now(),
        )
        return JsonResponse({
            'status_url': status_url,
            'status': 'unconfirmed',
            'message': (
                'We could not confirm your Lobook request. It may still have been queued. '
                'Please check your email before requesting another copy.'
            ),
        }, status=503)

    return JsonResponse({
        'status': 'queued',
        'task_id': job.task_id,
        'status_url': status_url,
        'email': request.user.email,
    }, status=202)


@login_required
@require_GET
def pdf_status(request, request_id):
    job = get_object_or_404(PDFRequest, pk=request_id, user=request.user)
    messages = {
        'queued': f'Lobook request received. We will email it to {request.user.email} when ready.',
        'unconfirmed': 'Queue submission could not be confirmed. Check here and your email before requesting another copy.',
        'processing': 'Your Lobook is being generated.',
        'sending': 'Emailing your Lobook…',
        'sent': 'Check your email',
        'failed': 'Your Lobook could not be generated or submitted. The print button will return shortly so you can try again, or contact support.',
        'delivery_uncertain': 'We could not confirm email delivery. Check your inbox and spam folder before requesting another copy.',
    }
    status = job.status
    if (timezone.now() - job.updated_at).total_seconds() > 900:
        if status == PDFRequest.Status.SENDING:
            status = PDFRequest.Status.UNCERTAIN
        elif status in (PDFRequest.Status.QUEUED, PDFRequest.Status.PROCESSING):
            status = 'delayed'
            messages[status] = 'Your Lobook request is taking longer than expected. Contact support before requesting another copy.'
    payload = {'status': status, 'message': messages[status]}
    if status == PDFRequest.Status.SENT:
        age_ms = (timezone.now() - job.updated_at).total_seconds() * 1000
        payload['hide_after_ms'] = max(0, min(30000, int(30000 - age_ms)))
    response = JsonResponse(payload)
    response['Cache-Control'] = 'no-store'
    return response
