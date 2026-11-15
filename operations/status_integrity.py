from django.db.models import Q

JOB_MODELS = ('pdf_output.PDFRequest', 'csv_app.CSVImportBatch', 'payments.BillingProvisioning')


def status_integrity_issues(app_registry, using):
    """Read-only audit; status repair must never reopen or requeue a job."""
    issues = []
    for label in JOB_MODELS:
        model = app_registry.get_model(label)
        allowed = [value for value, _ in model._meta.get_field('status').choices]
        rows = model.objects.using(using).filter(~Q(status__in=allowed) | Q(status__isnull=True)).order_by('pk')
        if rows.exists():
            sample = [str(pk) for pk in rows.values_list('pk', flat=True)[:10]]
            issues.append(f'{label}: {rows.count()} unsupported status value(s); sample IDs {sample}')
    return issues
