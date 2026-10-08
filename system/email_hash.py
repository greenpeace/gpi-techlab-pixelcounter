"""Email fingerprint formats and equivalent historical representations."""
import re


def hash_validation_mode(value, default='strict'):
    """Missing settings on existing counters use legacy; new counters use strict."""
    return value if value in ('strict', 'legacy') else default


def normalize_email_hash(value, mode):
    if re.fullmatch(r'[A-Za-z0-9_-]{16,128}', value):
        return value
    # Query decoding turns an unescaped '+' into a space. Accept only the
    # bounded legacy alphabet, with padding at the end, not arbitrary input.
    if mode == 'legacy' and re.fullmatch(r'[A-Za-z0-9_+/ -]{16,128}={0,2}', value):
        normalized = value.rstrip('=').replace(' ', '-').replace('+', '-').replace('/', '_')
        if 16 <= len(normalized) <= 128:
            return normalized
    return None


def historical_hash_values(normalized):
    """Find old random-ID records as well as prior deterministic-ID records."""
    standard = normalized.replace('-', '+').replace('_', '/')
    forms = (normalized, standard, standard.replace('+', ' '))
    return sorted({form + padding for form in forms for padding in ('', '=', '==')})
