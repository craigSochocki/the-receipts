import email.message
import io
import urllib.error
from pathlib import Path

import pytest

from receipts.common.fec_api import FecApi, Retry, parse_retry_after, public
from receipts.common.settings import RetrySettings, settings

EVIDENCE = Path(__file__).resolve().parents[1] / 'data' / 'evidence'
FILINGS = (EVIDENCE / 'f6_constantino.json').read_bytes()


def http_error(code, retry_after=None):
    headers = email.message.Message()
    if retry_after is not None:
        headers['Retry-After'] = retry_after
    return urllib.error.HTTPError('u', code, 'reason', headers, None)


class FakeFec:
    """Answers with the queued errors first, then the recorded body."""

    def __init__(self, *errors, body=FILINGS):
        self.errors = list(errors)
        self.body = body
        self.urls = []
        self.sleeps = []

    def urlopen(self, url, timeout):
        self.urls.append(url)
        if self.errors:
            raise self.errors.pop(0)
        return io.BytesIO(self.body)

    def api(self, retry=None):
        return FecApi(
            'SECRET', 'DEMO_KEY', 30, retry, urlopen=self.urlopen, sleep=self.sleeps.append
        )


def test_get_adds_the_key_and_pauses_first():
    fec = FakeFec()
    data = fec.api().get('/filings/', {'form_type': 'F6'})
    assert data['results'][0]['file_number'] == 2044138
    assert fec.urls == ['https://api.open.fec.gov/v1/filings/?form_type=F6&api_key=SECRET']
    assert fec.sleeps == [1.0]


def test_retry_after_is_honoured_and_the_log_hides_the_key(capsys):
    fec = FakeFec(http_error(429, '7'))
    fec.api().get('/filings/', {})
    assert fec.sleeps == [1.0, 7.0]
    log = capsys.readouterr().err
    assert 'waiting 7s (Retry-After: 7s)' in log
    assert 'SECRET' not in log


def test_without_retry_after_the_wait_backs_off_exponentially():
    fec = FakeFec(http_error(429), http_error(429), http_error(429))
    fec.api().get('/filings/', {})
    assert fec.sleeps == [1.0, 2.0, 4.0, 8.0]


def test_backoff_is_capped():
    assert Retry(backoff_base_seconds=2, backoff_cap_seconds=5).backoff(4) == 5


def test_attempts_run_out_loudly():
    fec = FakeFec(*[http_error(429)] * 5)
    with pytest.raises(SystemExit) as failure:
        fec.api().get('/filings/', {})
    message = str(failure.value)
    assert 'rate-limited on every attempt (5 attempts, waited 30s total)' in message
    assert 'apiinfo@fec.gov' in message
    assert 'SECRET' not in message


def test_a_wait_past_the_budget_fails_instead_of_sleeping():
    fec = FakeFec(http_error(429, '901'))
    with pytest.raises(SystemExit) as failure:
        fec.api().get('/filings/', {})
    assert 'would exceed the 900s per-request wait budget' in str(failure.value)
    assert fec.sleeps == [1.0]


def test_other_http_errors_exit_at_once_without_the_key():
    fec = FakeFec(http_error(500))
    with pytest.raises(SystemExit) as failure:
        fec.api().get('/filings/', {})
    assert str(failure.value) == (
        'FEC API /filings/ failed: HTTP 500 reason (url https://api.open.fec.gov/v1/filings/)'
    )
    assert len(fec.urls) == 1


def test_docquery_text_has_no_key_no_pause_and_its_own_rate_note():
    csv = (EVIDENCE / 'f6_2044138.csv').read_bytes()
    fec = FakeFec(*[http_error(429)] * 5, body=csv)
    with pytest.raises(SystemExit) as failure:
        fec.api().fetch_text('https://docquery.fec.gov/csv/138/2044138.csv')
    assert str(failure.value).startswith('docquery CSV failed: HTTP 429')
    assert 'docquery.fec.gov rate limit' in str(failure.value)
    fec = FakeFec(body=csv)
    assert fec.api().fetch_text('https://docquery.fec.gov/csv/138/2044138.csv').startswith('"HDR"')
    assert fec.sleeps == []


def test_parse_retry_after():
    assert parse_retry_after({'Retry-After': '12'}) == 12.0
    assert parse_retry_after({'Retry-After': '-3'}) == 0.0
    assert parse_retry_after({'Retry-After': 'Wed, 21 Oct 2015 07:28:00 GMT'}) == 0.0
    assert parse_retry_after({'Retry-After': 'soon'}) is None
    assert parse_retry_after({}) is None
    assert parse_retry_after(None) is None


def test_public_drops_only_the_key():
    url = 'https://api.open.fec.gov/v1/filings/?form_type=F6&api_key=SECRET&page=2'
    assert public(url) == 'https://api.open.fec.gov/v1/filings/?form_type=F6&page=2'


def test_demo_key_is_recognised():
    assert FecApi('DEMO_KEY', 'DEMO_KEY', 30).key_type == 'demo'
    assert FecApi('SECRET', 'DEMO_KEY', 30).key_type == 'registered'


def test_retry_settings_come_from_config():
    retry = Retry.from_settings(RetrySettings(0, 2.0, 300.0, 5.0))
    assert retry == Retry(max_attempts=1, max_wait_seconds=5.0)
    assert Retry.from_settings(settings().fec_api.retry) == Retry()
