"""Remove unfinished trailing route separators without changing airport codes."""
import re


def normalize_route(value):
    return re.sub(r'[-\s]+$', '', value) if isinstance(value, str) else value
