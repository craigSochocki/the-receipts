"""The page runs: its scripts parse, it serves, the smoke test passes, the build repeats."""

import re
import subprocess
import tempfile
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from receipts.common.settings import settings
from receipts.site.build_site import main as build_main


def javascript_parses(audit, page):
    """JS syntax"""
    app_scripts = re.findall(r'<script>(.*?)</script>', page.html, re.DOTALL)
    audit.check('two app scripts present', len(app_scripts) == 2, f'got {len(app_scripts)}')
    node_ok = True
    for i, src in enumerate(app_scripts):
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
            f.write(src)
            tmp = f.name
        r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
        if r.returncode != 0:
            node_ok = False
            print(f'  node --check script {i} failed:\n{r.stderr[:2000]}')
        Path(tmp).unlink(missing_ok=True)
    audit.check('page JavaScript parses (node --check)', node_ok)


def served_page(audit, page):
    """serve docs/ locally"""
    handler = partial(SimpleHTTPRequestHandler, directory=str(settings().paths.site))
    srv = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/index.html', timeout=10) as resp:
            body = resp.read().decode('utf-8')
            status = resp.status
        audit.check('local serve returns 200', status == 200, f'got {status}')
        for needle in [
            'The Receipts',
            'receipts-data',
            'Methodology',
            'primary targets',
            '2028 primary targets',
            'Clean money',
            'Leaderboards',
            'Data as of',
            'Find your member',
            'took no dirty money in 2026',
            'Dirtiest in 2026',
            'Explore the full data',
        ]:
            audit.check(f'served page contains {needle!r}', needle in body)
        audit.check(
            'served page size matches file',
            len(body.encode('utf-8')) == page.path.stat().st_size,
        )
    except Exception as e:  # noqa: BLE001 - report as a failed check
        audit.check(f'local serve works ({e})', False)
    finally:
        srv.shutdown()


def run_smoke_test(page_path, expected):
    """Run smoke_test.js in headless Chromium; the counts it saw, or an error at the first failure."""
    from playwright.sync_api import sync_playwright

    site = settings().root / 'receipts' / 'site'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            tab = browser.new_page(viewport={'width': 1024, 'height': 800})
            errors = []
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.add_init_script(path=site / 'smoke_prelude.js')
            tab.goto(page_path.resolve().as_uri())
            tab.add_script_tag(path=site / 'smoke_test.js')
            observed = tab.evaluate('exp => smoke.main(exp)', expected)
            tab.set_viewport_size({'width': 500, 'height': 800})
            tab.evaluate('smoke.narrow()')
            tab.set_viewport_size({'width': 1024, 'height': 800})
            tab.evaluate('smoke.wide()')
            for reduce in (True, False):
                tab.emulate_media(reduced_motion='reduce' if reduce else 'no-preference')
                tab.evaluate('expected => smoke.reducedMotion(expected)', reduce)
            if errors:
                raise RuntimeError(f'page errors: {errors}')
            return observed
        finally:
            browser.close()


def runtime_smoke_test(audit, page):
    """runtime smoke test (the page's JS runs in headless Chromium)"""
    try:
        observed = run_smoke_test(page.path, page.expected)
    except Exception as e:  # noqa: BLE001 - report as a failed check
        audit.check('runtime smoke test (render, tabs, detail, CSV)', False, str(e)[:2000])
        return
    audit.check('runtime smoke test (render, tabs, detail, CSV)', True)
    audit.pin('rows the page decodes', 'rows.count', observed.pop('rows'))
    for key, value in sorted(observed.items()):
        audit.pin(f'smoke test {key}', f'site.smoke.{key}', value)


def deterministic(audit, page):
    """determinism (apart from the generation timestamp)"""
    before = page.path.read_bytes()
    build_main()
    after = page.path.read_bytes()

    def strip_ts(b):
        return re.sub(rb'Generated [0-9-]+ [0-9:]+ UTC', b'Generated TS', b)

    audit.check('generator deterministic apart from timestamp', strip_ts(before) == strip_ts(after))
