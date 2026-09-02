"""Safe, bounded HTTP fetching for user-supplied public URLs."""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import requests


MAX_RESPONSE_BYTES = 1_000_000
MAX_REDIRECTS = 3


def _validate_public_url(url):
    parsed = urlsplit(url or '')
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Only public HTTP and HTTPS URLs are allowed')
    if parsed.username or parsed.password:
        raise ValueError('URLs containing credentials are not allowed')

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror as exc:
        raise ValueError('The URL hostname could not be resolved') from exc

    for result in addresses:
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError('Private, local, and reserved network addresses are not allowed')


def fetch_public_html(url):
    """Fetch at most 1 MB while validating every redirect destination."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        _validate_public_url(current_url)
        response = requests.get(
            current_url,
            allow_redirects=False,
            stream=True,
            timeout=(3, 7),
            headers={'User-Agent': 'Greenpeace-PixelCounter/1.0'},
        )
        response.raise_for_status()

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get('Location')
            response.close()
            if not location:
                raise ValueError('Redirect response did not include a destination')
            current_url = urljoin(current_url, location)
            continue

        content_type = response.headers.get('Content-Type', '').lower()
        if content_type and 'html' not in content_type:
            response.close()
            raise ValueError('The target URL did not return HTML')

        chunks = []
        size = 0
        for chunk in response.iter_content(16_384):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                response.close()
                raise ValueError('The target page is too large')
            chunks.append(chunk)
        encoding = response.encoding or 'utf-8'
        response.close()
        return b''.join(chunks).decode(encoding, errors='replace')

    raise ValueError('The target URL redirected too many times')
