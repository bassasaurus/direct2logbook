import logging
import uuid

from django.http import Http404
from django.utils import timezone

from .models import CSVImportBatch, CSV_PREVIEW_MAX_AGE
from .tasks import import_csv_batch
from .validation import CSVPreviewExpired

logger = logging.getLogger('django.csv_app')


def queue_csv_import(user, batch_id):
    try:
        batch = CSVImportBatch.objects.get(pk=batch_id, user=user)
    except CSVImportBatch.DoesNotExist:
        raise Http404('Import not found')
    if batch.completed or batch.status != CSVImportBatch.Status.PREVIEW:
        return batch, True
    if batch.is_expired:
        raise CSVPreviewExpired('This CSV preview has expired. Upload and inspect the file again.')
    task_id = str(uuid.uuid4())
    now = timezone.now()
    # This CAS is committed before publishing (the HTTP view is non-atomic).
    # It keeps resubmissions fast even while a worker holds the import row lock.
    changed = CSVImportBatch.objects.filter(
        pk=batch.pk, user=user, status=CSVImportBatch.Status.PREVIEW,
        completed=False, created_at__gt=now - CSV_PREVIEW_MAX_AGE,
    ).update(status=CSVImportBatch.Status.QUEUED, task_id=task_id,
             submitted_at=now, updated_at=now, error_message='')
    if changed:
        try:
            import_csv_batch.apply_async(args=(user.pk, str(batch.pk)), task_id=task_id, retry=False)
        except Exception:
            logger.exception('Could not confirm CSV queue submission batch_id=%s', batch.pk)
            CSVImportBatch.objects.filter(
                pk=batch.pk, task_id=task_id, status=CSVImportBatch.Status.QUEUED,
            ).update(status=CSVImportBatch.Status.UNCONFIRMED, updated_at=timezone.now())
    batch.refresh_from_db()
    if batch.is_expired:
        raise CSVPreviewExpired('This CSV preview has expired. Upload and inspect the file again.')
    return batch, not bool(changed)
