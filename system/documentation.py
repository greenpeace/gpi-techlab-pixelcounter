"""Validate documentation sources and construct trusted Google Docs URLs."""

import re
from urllib.parse import urlparse

_DOC_ID = re.compile(r'[A-Za-z0-9_-]{20,200}')
_DOC_PATH = re.compile(r'/document/(?:u/\d+/)?d/([A-Za-z0-9_-]{20,200})(?:/[^\s]*)?')


def google_doc_id(value):
    """Accept a document ID or regular Google Docs link, never arbitrary embeds."""
    value = str(value or '').strip()
    if _DOC_ID.fullmatch(value):
        return value
    parsed = urlparse(value)
    if parsed.scheme == 'https' and parsed.netloc == 'docs.google.com':
        match = _DOC_PATH.fullmatch(parsed.path)
        if match:
            return match.group(1)
    raise ValueError('Enter a Google Doc ID or a link like https://docs.google.com/document/d/DOCUMENT_ID/edit.')


def documentation_urls(stored_id):
    """Revalidate stored settings before placing a URL in a page."""
    try:
        document_id = google_doc_id(stored_id)
    except ValueError:
        return None
    base = f'https://docs.google.com/document/d/{document_id}'
    return {'id': document_id, 'view': base + '/edit', 'embed': base + '/preview'}
