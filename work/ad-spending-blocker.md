# Google ad-spending build — BLOCKED: no GCP access on this machine

**Date:** November 12, 2026
**Status:** Stopped at step 1 of the Phase A plan (per the task's stop rule).
No data was pulled, no dataset/methodology/artifact files were changed, and no
ad figures were invented.

## What was checked (evidence)

| Check | Result |
|---|---|
| `gcloud` / `bq` CLI | Not installed (`command not found`) |
| `~/.config/gcloud` | Does not exist |
| `GOOGLE_APPLICATION_CREDENTIALS` / GCP env vars | None set |
| Service-account / credentials JSON in home | None found (searched `~`, maxdepth 4; the only grep hits in the workspace are unrelated "BigQuery" mentions in job-search files and feed research) |
| `google-cloud-bigquery` library (system Python) | Not installed; system Python is PEP 668 externally-managed, so plain `pip install` is refused |
| BigQuery client in a fresh venv (`/tmp/bq-venv`, library installed OK) | `bigquery.Client()` raises `DefaultCredentialsError: Your default credentials were not found` — the definitive failure: no project, no credentials |
| Alternative mirrors | Kaggle `sowparnikam/g-political-ads` is stale (updated 2024-01-24, 2.11 MB) — not 2026 data. Transparency Center has no official API and no download button. The undocumented internal RPC exists but the research file explicitly rules it out as primary (fragile, unversioned). Vendor APIs (e.g. ReefAPI) are paid dependencies. |

## Exactly what is missing (3 items)

1. **A Google Cloud project** with the BigQuery API enabled. Queries against
   the public dataset `bigquery-public-data.google_political_ads` are billed to
   the querying project; the first 1 TB/month is free on demand, and the
   Phase A queries (US region, 2025–2026 dates) are small.
2. **Credentials** — one of:
   - a service-account key (JSON) with roles **BigQuery Job User** and
     **BigQuery Data Viewer**, pointed to by `GOOGLE_APPLICATION_CREDENTIALS`; or
   - user auth via `gcloud auth application-default login` (needs `gcloud`
     installed and a Google account).
3. **Client tooling** — `gcloud`/`bq` CLI, or the `google-cloud-bigquery`
   Python library in a venv (a working venv already exists at `/tmp/bq-venv`
   with `google-cloud-bigquery` + `pandas` installed, but `/tmp` is ephemeral
   — recreate it, or install into a durable location, when credentials arrive).

## Setup steps (for the parent agent / Craig)

1. In Google Cloud Console: create a project, enable the BigQuery API.
2. Create a service account, grant BigQuery Job User (+ BigQuery Data Viewer),
   download the JSON key.
3. On this machine: set `GOOGLE_APPLICATION_CREDENTIALS` to the key path (or
   run `gcloud auth application-default login` after installing gcloud).
4. Re-run this task — the Phase A plan in `ad-spending-research.md` §5 is
   ready to execute as written (tables, bronze/silver/gold layout, join rules,
   columns, methodology §15).

## Notes

- The user's platform-connected Google accounts (Gmail, Google Calendar) are
  OAuth tokens scoped to those APIs only. They cannot be used for BigQuery
  and must not be extracted or repurposed for it.
- Nothing else in the tracker was touched. The dataset, methodology, and
  artifact are exactly as the Luria fix left them.
