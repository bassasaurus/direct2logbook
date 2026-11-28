"""Persistent account-scoped upload identity, independent of filenames."""
import hashlib
from .models import CSVImportBatch


def upload_digest(text):
    normalized = text.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n').rstrip('\n')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def submitted_copy(user, digest, exclude=None):
    if not digest:
        return None
    copies = CSVImportBatch.objects.filter(user=user, source_digest=digest,
        status__in=('queued', 'unconfirmed', 'processing', 'completed'))
    if exclude is not None:
        copies = copies.exclude(pk=exclude)
    return copies.order_by('-created_at').first()
