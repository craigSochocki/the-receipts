"""Shared HTTP 429 retry handling for the FEC freshness pulls.

A standard registered api.data.gov key is limited to 1,000 requests/hour.
A full freshness ``--all`` run makes ~2,200-2,350 keyed API calls in
~45-60 minutes, so it hits HTTP 429 (OVER_RATE_LIMIT) part-way through.
Before this module, every ``api_get`` raised ``SystemExit`` on the first
HTTP error, so one 429 killed the whole run.

``open_with_retry`` wraps a single ``urllib.request.urlopen`` call:

- On HTTP 429 it waits and retries, bounded by ``max_attempts``.
- The wait is the ``Retry-After`` header when present (seconds, or an
  HTTP-date), otherwise exponential backoff: ``base * 2**(attempt-1)``,
  capped at ``backoff_cap_seconds``.
- Each wait is logged to stderr (never stdout — the pull scripts emit
  JSON on stdout) with the label/URL, attempt number, and seconds.
  Logged URLs have the ``api_key`` query param stripped, so the key
  never lands in CI logs.
- If the projected wait would push the total waited past
  ``max_wait_seconds``, or attempts run out, it fails loudly with a
  ``SystemExit`` naming the rate limit and the raise path
  (email apiinfo@fec.gov to request 120 calls/min = 7,200/hour).
- Non-429 HTTP errors are re-raised untouched, so callers keep their
  current behaviour (immediate ``SystemExit``).

The tunables live in ONE place: ``fec_api.retry`` in config.yaml
(single source of truth). ``retry_settings`` reads them, with the same
values as fallbacks so a config without the section still behaves.

The docquery CSV fetch in pull_f6.py uses the same helper: docquery
needs no API key, so the api.data.gov 1,000/hr limit does not apply to
it, but a 429 there would kill a run the same way — hence the same
retry, with a docquery-specific failure note.
"""
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Defaults mirror config.yaml fec_api.retry; config.yaml wins.
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_BASE_SECONDS = 2.0
DEFAULT_BACKOFF_CAP_SECONDS = 300.0
DEFAULT_MAX_WAIT_SECONDS = 900.0

FEC_API_RATE_LIMIT_NOTE = (
    "FEC API rate limit: a standard registered api.data.gov key allows "
    "1,000 requests/hour. To raise it, email apiinfo@fec.gov to request "
    "120 calls/min (= 7,200/hour)."
)
DOCQUERY_RATE_LIMIT_NOTE = (
    "docquery.fec.gov rate limit (no API key; the api.data.gov "
    "1,000 requests/hour limit does not apply here). Wait and retry the "
    "run later; if it persists, check FEC service status."
)


def retry_settings(cfg):
    """Retry tunables from config.yaml (``fec_api.retry``), with defaults.

    ``cfg`` is the dict from ``src.common.config.load_config()``.
    Returns ``{'max_attempts': int, 'backoff_base_seconds': float,
    'backoff_cap_seconds': float, 'max_wait_seconds': float}``.
    """
    retry = (cfg.get('fec_api') or {}).get('retry') or {}
    return {
        'max_attempts': int(retry.get('max_attempts', DEFAULT_MAX_ATTEMPTS)),
        'backoff_base_seconds': float(retry.get(
            'backoff_base_seconds', DEFAULT_BACKOFF_BASE_SECONDS)),
        'backoff_cap_seconds': float(retry.get(
            'backoff_cap_seconds', DEFAULT_BACKOFF_CAP_SECONDS)),
        'max_wait_seconds': float(retry.get(
            'max_wait_seconds', DEFAULT_MAX_WAIT_SECONDS)),
    }


def parse_retry_after(headers):
    """Seconds to wait from a Retry-After header value, or None.

    Handles a plain integer (seconds) and an HTTP-date. Returns None
    when the header is absent, empty, or unparsable — the caller then
    falls back to exponential backoff.
    """
    if headers is None:
        return None
    try:
        value = headers.get('Retry-After')
    except Exception:
        return None
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        seconds = float(value)
        return max(seconds, 0.0)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max((dt - datetime.now(timezone.utc)).total_seconds(), 0.0)
    except (ValueError, TypeError, OverflowError):
        return None


def _backoff_seconds(attempt, retry):
    """Exponential backoff for a retry (attempt is 1-based, the attempt
    that just got the 429): base * 2**(attempt-1), capped."""
    return min(retry['backoff_base_seconds'] * (2 ** (attempt - 1)),
               retry['backoff_cap_seconds'])


def _sanitize_url(url):
    """URL with the api_key query param stripped, for logs and errors.

    Retry waits are logged to stderr (and loud failures surface in CI
    logs), and the request URL carries the key — never log the key.
    """
    parts = urllib.parse.urlparse(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query)
             if k != 'api_key']
    return urllib.parse.urlunparse(parts._replace(
        query=urllib.parse.urlencode(query)))


def _fail_loudly(label, url, reason, limit_note):
    raise SystemExit(
        f'{label} failed: {reason} (url {_sanitize_url(url)}). {limit_note}')


def open_with_retry(url, timeout, retry, label,
                    limit_note=FEC_API_RATE_LIMIT_NOTE):
    """``urllib.request.urlopen`` with bounded HTTP 429 retry.

    Returns the response object on success (caller uses it as a context
    manager, as before). Non-429 ``HTTPError`` is re-raised untouched.
    On 429 exhaustion or on a projected wait past the budget, raises
    ``SystemExit`` with the rate-limit message. Each 429 wait is logged
    to stderr with label, URL, attempt number, and seconds.
    """
    max_attempts = max(retry['max_attempts'], 1)
    waited = 0.0
    for attempt in range(1, max_attempts + 1):
        try:
            return urllib.request.urlopen(url, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            if attempt >= max_attempts:
                _fail_loudly(
                    label, url,
                    f'HTTP 429 rate-limited on every attempt '
                    f'({max_attempts} attempts, waited {waited:.0f}s total)',
                    limit_note)
            retry_after = parse_retry_after(e.headers)
            if retry_after is not None:
                wait = retry_after
                source = f'Retry-After: {retry_after:.0f}s'
            else:
                wait = _backoff_seconds(attempt, retry)
                source = (f'exponential backoff '
                          f'(base {retry["backoff_base_seconds"]:g}s, '
                          f'attempt {attempt})')
            if waited + wait > retry['max_wait_seconds']:
                _fail_loudly(
                    label, url,
                    f'HTTP 429 rate-limited (attempt {attempt}/'
                    f'{max_attempts}); projected wait {wait:.0f}s ({source}) '
                    f'would exceed the {retry["max_wait_seconds"]:.0f}s '
                    f'per-request wait budget '
                    f'(already waited {waited:.0f}s)',
                    limit_note)
            print(f'[{label}] HTTP 429 rate-limited (attempt {attempt}/'
                  f'{max_attempts}): waiting {wait:.0f}s ({source}) '
                  f'before retrying {_sanitize_url(url)}',
                  file=sys.stderr, flush=True)
            time.sleep(wait)
            waited += wait
    # Unreachable: the loop either returns, re-raises, or fails loudly.
    raise AssertionError('open_with_retry: retry loop ended without a result')
