"""Inspect persisted job outcomes without contacting Celery, Stripe, or users."""
from datetime import timedelta

from django.db.models import Q

from csv_app.models import CSVImportBatch, CSV_IMPORT_STALE_AFTER
from payments.models import BillingProvisioning
from pdf_output.models import PDFRequest


DETAIL_LIMIT = 30


def problem_jobs(now):
    recent = now - timedelta(hours=24)
    pdf = PDFRequest.objects.filter(
        Q(status='failed', updated_at__gte=recent)
        | Q(status='delivery_uncertain')
        | Q(status__in=['queued', 'unconfirmed', 'processing', 'retrying', 'sending'],
            updated_at__lt=now - timedelta(minutes=15))
    )
    csv = CSVImportBatch.objects.filter(completed=False).filter(
        Q(status='failed', updated_at__gte=recent)
        | Q(status__in=['queued', 'unconfirmed', 'processing'],
            updated_at__lte=now - CSV_IMPORT_STALE_AFTER)
    )
    billing = BillingProvisioning.objects.exclude(status='completed').filter(
        Q(status='failed') | Q(outcome_uncertain=True)
        | Q(status='pending', updated_at__lte=now - timedelta(minutes=15))
        | Q(status='processing', processing_started_at__lte=now - timedelta(minutes=15))
        | Q(status='processing', processing_started_at__isnull=True)
    )
    result = []
    for label, queryset in [('PDF', pdf), ('CSV', csv), ('Trial provisioning', billing)]:
        count = queryset.count()
        if not count:
            continue
        # No email addresses, CSV data, tokens, or raw exception text in the digest.
        lines = [f'{label}: {count} unresolved job(s)']
        for pk, status, updated in queryset.order_by('updated_at', 'pk').values_list(
            'pk', 'status', 'updated_at',
        )[:DETAIL_LIMIT]:
            lines.append(f'  id={pk} status={status} updated_at={updated.isoformat()}')
        if count > DETAIL_LIMIT:
            lines.append(f'  Showing oldest {DETAIL_LIMIT} of {count}.')
        result.append((count, '\n'.join(lines)))
    return result
