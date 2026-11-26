# Vendored libraries

The scrollytelling story renders its standard charts with these
libraries, vendored as files so the built page stays one
self-contained file with no live third-party dependency — nothing is
fetched from a CDN at view time, and there is no build step,
package.json, or node_modules.

| File | Version | Source | sha256 |
| --- | --- | --- | --- |
| `d3.min.js` | d3 7.9.2 | https://cdn.jsdelivr.net/npm/d3@7.9.2/dist/d3.min.js | `912111098ea99503a6f4967361d2bbdc9dbf58cf9c678c8e27e5b02d1a07f0c1` |
| `plot.umd.min.js` | @observablehq/plot 0.6.19 (UMD) | https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.19/dist/plot.umd.min.js | `0c1f1a0f0ea13cc8fc143bf014dd14ca90abb92d06f9e22a28bb76e42000d131` |
| `scrollama.min.js` | scrollama 3.2.0 | https://cdn.jsdelivr.net/npm/scrollama@3.2.0/build/scrollama.min.js | `17d8c6db877708006d0f22a42d030b192fa68a721292253ce70a7d85301e7433` |

Total: 497,250 bytes raw (164,042 bytes gzipped). Each file was
downloaded from the source URL above and its sha256 verified against
the value in this table before committing; a mismatch is a stop, not
something to commit around.

Load order in the built page is d3, then Plot (its UMD build reads
the `d3` global), then scrollama, then the tracker's own scripts.
`build_site.py` inlines these files and fails loudly if one is
missing — it never silently emits a page without its libraries.
