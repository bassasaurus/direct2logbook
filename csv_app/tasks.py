import logging
from types import SimpleNamespace

from celery import shared_task
from django.contrib.auth import get_user_model
from django.http import Http404
from django.utils import timezone

from .csv_import import confirm_csv_import
from .models import CSVImportBatch
from .validation import CSVValidationError

logger = logging.getLogger('django.csv_app')


@shared_task(bind=True, ignore_result=True, soft_time_limit=900, time_limit=960, max_retries=0)
def import_csv_batch(self, user_pk, batch_id):
    task_id = self.request.id
    if not task_id:
        raise ValueError('A CSV import requires a task ID')
    claimed = CSVImportBatch.objects.filter(
        pk=batch_id, user_id=user_pk, task_id=task_id, completed=False,
        status__in=[CSVImportBatch.Status.QUEUED, CSVImportBatch.Status.UNCONFIRMED],
    ).update(status=CSVImportBatch.Status.PROCESSING, started_at=timezone.now(), updated_at=timezone.now())
    if not claimed:
        return
    try:
        user = get_user_model().objects.get(pk=user_pk)
        confirm_csv_import(SimpleNamespace(user=user), batch_id, expected_task_id=task_id)
    except (get_user_model().DoesNotExist, Http404):
        # Account deletion can remove the batch while a task is waiting.
        return
    except Exception as exc:
        message = str(exc) if isinstance(exc, CSVValidationError) else (
            'The import could not finish. No flights were imported. Upload and inspect the file again.'
        )
        # The import transaction has rolled back. A lost commit acknowledgement
        # may still have committed the receipt, so never overwrite completion.
        CSVImportBatch.objects.filter(
            pk=batch_id, task_id=task_id, completed=False,
            status=CSVImportBatch.Status.PROCESSING,
        ).update(status=CSVImportBatch.Status.FAILED, error_message=message,
                 content='', updated_at=timezone.now())
        logger.exception('Background CSV import failed batch_id=%s', batch_id)
        raise
