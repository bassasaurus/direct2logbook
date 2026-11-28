"""Read Linux memory counters without shell commands or process arguments."""
from pathlib import Path


PROCESS_NAMES = {
    'gunicorn': 'Django / Gunicorn',
    'celery': 'Celery',
    'postgres': 'PostgreSQL',
    'nginx': 'Nginx',
    'beam.smp': 'RabbitMQ',
}


def _counters(path):
    result = {}
    for line in path.read_text().splitlines():
        key, separator, value = line.partition(':')
        if separator:
            result[key] = value.strip()
    return result


def _kib(counters, key):
    return int(counters[key].split()[0])


def memory_snapshot(proc_root=Path('/proc')):
    """Return only memory figures; inaccessible process counters remain unknown."""
    try:
        memory = _counters(proc_root / 'meminfo')
        total = _kib(memory, 'MemTotal')
        available = _kib(memory, 'MemAvailable')
        swap_total = _kib(memory, 'SwapTotal')
        swap_free = _kib(memory, 'SwapFree')
    except (OSError, ValueError, KeyError):
        return {'available': False}

    groups = {}
    for entry in proc_root.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            counters = _counters(entry / 'status')
            name = counters.get('Name')
            if name not in PROCESS_NAMES:
                continue
            group = groups.setdefault(name, {
                'name': PROCESS_NAMES[name], 'count': 0,
                'rss': 0, 'swap': 0, 'swap_known': True,
            })
            group['count'] += 1
            group['rss'] += _kib(counters, 'VmRSS')
            if 'VmSwap' in counters:
                group['swap'] += _kib(counters, 'VmSwap')
            else:
                group['swap_known'] = False
        except (OSError, ValueError, KeyError):
            # Processes can exit or become inaccessible during the snapshot.
            continue

    processes = []
    for name in PROCESS_NAMES:
        if name in groups:
            group = groups[name]
            processes.append({
                **group,
                'rss': round(group['rss'] / 1024, 1),
                'swap': round(group['swap'] / 1024, 1) if group['swap_known'] else None,
            })
    return {
        'available': True,
        'total': round(total / 1024, 1),
        'used': round((total - available) / 1024, 1),
        'free': round(available / 1024, 1),
        'swap_total': round(swap_total / 1024, 1),
        'swap_used': round((swap_total - swap_free) / 1024, 1),
        'processes': processes,
    }
