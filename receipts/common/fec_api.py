"""One client for the OpenFEC API and docquery: key added, calls paced, 429s retried, failures loud."""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from receipts.common.config import load_config

API_BASE = 'https://api.open.fec.gov/v1'
MIN_PAUSE_SECONDS = 1.0

FEC_API_RATE_LIMIT_NOTE = (
    'FEC API rate limit: a standard registered api.data.gov key allows '
    '1,000 requests/hour. To raise it, email apiinfo@fec.gov to request '
    '120 calls/min (= 7,200/hour).'
)
DOCQUERY_RATE_LIMIT_NOTE = (
    'docquery.fec.gov rate limit (no API key; the api.data.gov '
    '1,000 requests/hour limit does not apply here). Wait and retry the '
    'run later; if it persists, check FEC service status.'
)


@dataclass(frozen=True)
class Retry:
    """How long to keep retrying an HTTP 429 (config.yaml fec_api.retry)."""

    max_attempts: int = 5
    backoff_base_seconds: float = 2.0
    backoff_cap_seconds: float = 300.0
    max_wait_seconds: float = 900.0

    @classmethod
    def from_config(cls, cfg):
        retry = (cfg.get('fec_api') or {}).get('retry') or {}
        defaults = cls()
        return cls(
            max_attempts=max(int(retry.get('max_attempts', defaults.max_attempts)), 1),
            backoff_base_seconds=float(
                retry.get('backoff_base_seconds', defaults.backoff_base_seconds)
            ),
            backoff_cap_seconds=float(
                retry.get('backoff_cap_seconds', defaults.backoff_cap_seconds)
            ),
            max_wait_seconds=float(retry.get('max_wait_seconds', defaults.max_wait_seconds)),
        )

    def backoff(self, attempt):
        return min(self.backoff_base_seconds * 2 ** (attempt - 1), self.backoff_cap_seconds)

    def wait_for(self, attempt, headers):
        """(seconds, why) for the wait after a 429 on this 1-based attempt."""
        retry_after = parse_retry_after(headers)
        if retry_after is not None:
            return retry_after, f'Retry-After: {retry_after:.0f}s'
        why = f'exponential backoff (base {self.backoff_base_seconds:g}s, attempt {attempt})'
        return self.backoff(attempt), why


def parse_retry_after(headers):
    """Seconds from a Retry-After header (seconds or an HTTP-date), or None."""
    value = str(headers.get('Retry-After') or '').strip() if headers is not None else ''
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max((when - datetime.now(timezone.utc)).total_seconds(), 0.0)


def public(url):
    """The URL with its api_key removed, safe to log."""
    parts = urllib.parse.urlparse(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != 'api_key']
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(query)))


class FecApi:
    def __init__(
        self,
        key,
        demo_key,
        timeout,
        retry=None,
        pause=MIN_PAUSE_SECONDS,
        urlopen=urllib.request.urlopen,
        sleep=time.sleep,
    ):
        self.key = key
        self.demo_key = demo_key
        self.timeout = timeout
        self.retry = retry or Retry()
        self.pause = pause
        self._urlopen = urlopen
        self._sleep = sleep

    @classmethod
    def from_config(cls, cfg=None):
        cfg = cfg or load_config()
        api = cfg['fec_api']
        return cls(
            key=os.environ.get(api['api_key_env'], api['api_key_default']),
            demo_key=api['api_key_default'],
            timeout=api['request_timeout_seconds'],
            retry=Retry.from_config(cfg),
            pause=max(api['sleep_between_requests_seconds'], MIN_PAUSE_SECONDS),
        )

    @property
    def is_demo_key(self):
        return self.key == self.demo_key

    @property
    def key_type(self):
        return 'demo' if self.is_demo_key else 'registered'

    def get(self, path, params):
        """Parsed JSON from one OpenFEC API path, e.g. get('/filings/', {...})."""
        url = f'{API_BASE}{path}?{urllib.parse.urlencode({**params, "api_key": self.key})}'
        self._sleep(self.pause)
        label = f'FEC API {path}'
        with self._open(url, label, FEC_API_RATE_LIMIT_NOTE) as resp:
            return json.load(resp)

    def fetch_text(self, url):
        """Text of one docquery file (no key, no pause)."""
        with self._open(
            url, 'docquery CSV fetch', DOCQUERY_RATE_LIMIT_NOTE, 'docquery CSV'
        ) as resp:
            return resp.read().decode('utf-8', errors='replace')

    def _open(self, url, label, limit_note, rate_label=None):
        """urlopen, retrying 429s within the wait budget; any other HTTP error exits."""
        rate_label = rate_label or label
        try:
            return self._open_retrying(url, rate_label, limit_note)
        except urllib.error.HTTPError as e:
            raise SystemExit(f'{label} failed: HTTP {e.code} {e.reason} (url {public(url)})') from e

    def _open_retrying(self, url, label, limit_note):
        retry = self.retry
        waited = 0.0
        for attempt in range(1, retry.max_attempts + 1):
            try:
                return self._urlopen(url, timeout=self.timeout)
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                if attempt == retry.max_attempts:
                    reason = (
                        f'HTTP 429 rate-limited on every attempt '
                        f'({retry.max_attempts} attempts, waited {waited:.0f}s total)'
                    )
                    raise _rate_limited(label, url, reason, limit_note) from e
                wait, why = retry.wait_for(attempt, e.headers)
                tried = f'attempt {attempt}/{retry.max_attempts}'
                if waited + wait > retry.max_wait_seconds:
                    reason = (
                        f'HTTP 429 rate-limited ({tried}); projected wait {wait:.0f}s ({why}) '
                        f'would exceed the {retry.max_wait_seconds:.0f}s per-request wait '
                        f'budget (already waited {waited:.0f}s)'
                    )
                    raise _rate_limited(label, url, reason, limit_note) from e
                print(
                    f'[{label}] HTTP 429 rate-limited ({tried}): waiting {wait:.0f}s ({why}) '
                    f'before retrying {public(url)}',
                    file=sys.stderr,
                    flush=True,
                )
                self._sleep(wait)
                waited += wait


def _rate_limited(label, url, reason, limit_note):
    return SystemExit(f'{label} failed: {reason} (url {public(url)}). {limit_note}')


fec_api = FecApi.from_config()
