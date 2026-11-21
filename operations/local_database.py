"""Connection rules shared by the restore command and the local settings profile."""
import re
from urllib.parse import urlsplit, urlunsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

LOCAL_PREFIX = 'd2l_local_'


def local_database_url(source, explicit=None):
    try:
        parts = urlsplit(explicit or source)
        config = dj_database_url.parse(explicit or source)
        if config['ENGINE'] != 'django.db.backends.postgresql':
            raise ValueError()
        if config.get('HOST') not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError()
        if parts.query or parts.fragment:
            raise ValueError()
        if explicit:
            name = config['NAME']
        else:
            name = LOCAL_PREFIX + 'production'
        if not re.fullmatch(r'd2l_local_[a-z0-9_]{1,40}', name):
            raise ValueError()
        return urlunsplit((parts.scheme, parts.netloc, '/' + name, '', ''))
    except (KeyError, TypeError, ValueError):
        raise ImproperlyConfigured(
            'Local restores require a PostgreSQL URL on localhost, 127.0.0.1 or ::1, '
            'without URL query options, and a database name starting with d2l_local_. '
            'Set LOCAL_RESTORE_DATABASE_URL; the normal DATABASE_URL is never overwritten on disk.'
        ) from None
