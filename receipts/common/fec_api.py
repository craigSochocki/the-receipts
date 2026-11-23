"""One way to call the OpenFEC API: the key, a pause between calls, retries, a loud failure."""

import json
import os
import time
import urllib.error
import urllib.parse

from receipts.common.api_retry import open_with_retry, retry_settings, sanitize_url
from receipts.common.config import load_config

CFG = load_config()
API_BASE = 'https://api.open.fec.gov/v1'
API_KEY = os.environ.get(CFG['fec_api']['api_key_env'], CFG['fec_api']['api_key_default'])
SLEEP = max(CFG['fec_api']['sleep_between_requests_seconds'], 1.0)
RETRY = retry_settings(CFG)


def api_get(path, params):
    params = {**params, 'api_key': API_KEY}
    url = API_BASE + path + '?' + urllib.parse.urlencode(params)
    time.sleep(SLEEP)
    try:
        with open_with_retry(
            url,
            timeout=CFG['fec_api']['request_timeout_seconds'],
            retry=RETRY,
            label=f'FEC API {path}',
        ) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f'FEC API {path} failed: HTTP {e.code} {e.reason} (url {sanitize_url(url)})'
        ) from e
