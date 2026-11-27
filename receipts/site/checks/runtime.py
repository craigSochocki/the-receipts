"""The pages run: their scripts parse, they serve, the smoke test passes, the build repeats."""

import re
import subprocess
import tempfile
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from receipts.common.log import log
from receipts.common.settings import settings
from receipts.site.build_site import main as build_main

# Plain <script> blocks per page (the vendored libraries and the page's
# own script, inlined by the build; JSON payloads carry attributes and
# are not counted), and a marker proving the right script is embedded.
EXPECTED_SCRIPTS = {'story': 4, 'explore': 1, 'methodology': 0}
SCRIPT_MARKERS = {'story': 'const STORY_STEPS', 'explore': 'const PAGE_SIZES'}

ROUTES = {'story': '/', 'explore': '/explore/', 'methodology': '/methodology/'}
NEEDLES = {
    'story': ['The Receipts', 'id="story-data"', 'Find your member', 'Data as of'],
    'explore': [
        'The Receipts',
        'id="receipts-data"',
        'id="explore-table"',
        'Find your member of Congress',
    ],
    'methodology': ['The Receipts', 'How we flagged members', 'Next FEC update', 'Data as of'],
}


def javascript_parses(audit, site):
    """JS syntax"""
    for page in site.pages():
        scripts = re.findall(r'<script>(.*?)</script>', page.html, re.DOTALL)
        audit.check(
            f'every app script is embedded ({page.kind})',
            len(scripts) == EXPECTED_SCRIPTS[page.kind],
            f'got {len(scripts)}, want {EXPECTED_SCRIPTS[page.kind]}',
        )
        marker = SCRIPT_MARKERS.get(page.kind)
        if marker:
            audit.check(
                f'the embedded script is the page script ({page.kind})',
                any(marker in src for src in scripts),
            )
        node_ok = True
        for i, src in enumerate(scripts):
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
                f.write(src)
                tmp = f.name
            r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
            if r.returncode != 0:
                node_ok = False
                log.info(f'  node --check {page.kind} script {i} failed:\n{r.stderr[:2000]}')
            Path(tmp).unlink(missing_ok=True)
        audit.check(f'page JavaScript parses (node --check) ({page.kind})', node_ok)


def served_page(audit, site):
    """serve docs/ locally"""
    handler = partial(SimpleHTTPRequestHandler, directory=str(settings().paths.site))
    srv = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    try:
        for page in site.pages():
            with urllib.request.urlopen(
                f'http://127.0.0.1:{port}{ROUTES[page.kind]}', timeout=10
            ) as resp:
                body = resp.read().decode('utf-8')
                status = resp.status
            audit.check(f'local serve returns 200 ({page.kind})', status == 200, f'got {status}')
            for needle in NEEDLES[page.kind]:
                audit.check(f'served page contains {needle!r} ({page.kind})', needle in body)
            audit.check(
                f'served page size matches file ({page.kind})',
                len(body.encode('utf-8')) == page.path.stat().st_size,
            )
    except Exception as e:  # noqa: BLE001 - report as a failed check
        audit.check(f'local serve works ({e})', False)
    finally:
        srv.shutdown()


def run_smoke_test(explore_path, story_path, expected):
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
            tab.goto(explore_path.resolve().as_uri())
            tab.add_script_tag(path=site / 'smoke_test.js')
            observed = tab.evaluate('exp => smoke.main(exp)', expected)
            tab.goto(story_path.resolve().as_uri())
            tab.add_script_tag(path=site / 'smoke_test.js')
            tab.evaluate('exp => smoke.story(exp)', expected)
            for reduce in (True, False):
                tab.emulate_media(reduced_motion='reduce' if reduce else 'no-preference')
                tab.evaluate('expected => smoke.reducedMotion(expected)', reduce)
            if errors:
                raise RuntimeError(f'page errors: {errors}')
            return observed
        finally:
            browser.close()


def runtime_smoke_test(audit, site):
    """runtime smoke test (the pages' JS runs in headless Chromium)"""
    try:
        observed = run_smoke_test(site.explore.path, site.story.path, site.explore.expected)
    except Exception as e:  # noqa: BLE001 - report as a failed check
        audit.check('runtime smoke test (render, search, drawer, story)', False, str(e)[:2000])
        return
    audit.check('runtime smoke test (render, search, drawer, story)', True)
    audit.pin('rows the page decodes', 'rows.count', observed.pop('rows'))
    for key, value in sorted(observed.items()):
        audit.pin(f'smoke test {key}', f'site.smoke.{key}', value)


def deterministic(audit, site):
    """determinism (apart from the generation timestamp)"""
    pages = site.pages()
    before = {page.kind: page.path.read_bytes() for page in pages}
    build_main()

    def strip_ts(b):
        return re.sub(rb'Generated [0-9-]+ [0-9:]+ UTC', b'Generated TS', b)

    for page in pages:
        after = page.path.read_bytes()
        audit.check(
            f'generator deterministic apart from timestamp ({page.kind})',
            strip_ts(before[page.kind]) == strip_ts(after),
        )
