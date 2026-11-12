# Ad spending — scoping research for the Congress money tracker

**Date:** November 12, 2026
**Status:** Research only. No dataset, methodology, or artifact changes were made.
**Decision context:** Craig chose ad spending as the next data layer after the FEC money
columns (individual, corporate PAC, AIPAC direct, UDP support/opposition credit).
Scope is 2026 federal House/Senate ad spending, per person, joined to the tracker
roster on FEC candidate/committee IDs.
**Design constraint:** per `architecture.md`, raw staged files come first (bronze),
then derived per-person columns (gold). Money is exact in the FEC layers; ad spend
breaks that rule (see §4) and must be stored and labeled as estimates.

## 0. Verdict up front

| Source | Build it? | Order | Why |
|---|---|---|---|
| Google Ads Transparency Center (via BigQuery public dataset) | Yes | **1st** | No approval needed; SQL over a public dataset; **FEC committee IDs are in the data** (advertiser verification requires them); weekly freshness; covers Search + YouTube + Display. |
| Meta Ad Library (official `ads_archive` API) | Yes | **2nd** | Official API, near-real-time, 7-year retention — but needs Craig's personal identity verification, a hand-built Page → candidate map, and a multi-day pull at 200 calls/hour. Spend is ranges only. |
| FCC political files (TV buys) | **Not in v1** | 3rd / deferred | No structured source exists. The FCC API lists files and serves PDFs; amounts live inside scanned/heterogeneous PDFs. The only structured TV data is commercial (AdImpact, via Wesleyan Media Project). TV is the biggest channel by dollars, so this is a real gap — but building it from PDFs is a separate project, not a column add. |

**What none of the three sources covers:** TikTok (bans US political ads), X/Twitter
(own transparency center, no bulk access found), Snapchat (own political library),
connected TV/streaming beyond Google/Meta, radio (FCC files exist but same PDF problem),
direct mail. Any "total ad spend" figure is therefore a **partial total of three
channels**, and must be labeled as such.

**The one rule that changes vs. the FEC layers:** ad spend is reported by both
platforms as **ranges, never exact dollars**. The tracker's "money is exact" rule
(architecture.md §6) cannot hold here. Ad columns must store min/max bounds plus a
midpoint estimate, and methodology must say these are estimates with a stated error
band. They must **never** be added into `total_accepted_career` or any other exact
FEC-money column.

---

## 1. Meta Ad Library

### (a) Access method and auth/approval

- **Official API:** `GET https://graph.facebook.com/v{version}/ads_archive`
  (Graph API; v26.0 current as of Oct 2026, v25 supported until July 2028 — pin the
  version at build time). Free, no per-call charges. Read-only, public archive data.
- **No App Review required** (no private user data), but three one-time setup steps:
  1. **Identity + location confirmation** by the person behind the token —
     government-issued ID and country of residence at facebook.com/ID. Approval
     typically takes a few days. **This is the gate: Craig would have to complete
     it himself with his own ID; it cannot be delegated.**
  2. A Meta for Developers app (free).
  3. An access token. Graph API Explorer tokens are short-lived (1–2 hours);
     exchange for a long-lived token (~60 days) or, for scheduled pulls, a
     **system-user token** (recommended; does not expire, rotatable independently
     of any one person's account). Some guides say the token needs the `ads_read`
     permission added; others report default permissions suffice once identity is
     confirmed — verify at build time.
- **Rate limits:** ~**200 calls/hour** per app/user token (error 613 on limit,
  error 190 on bad token). Paginated results capped at **1,000 ads per query**.
- **Query constraint that shapes the whole build:** every call must include either
  `search_terms` (keyword) **or** `search_page_ids` (max **10 Page IDs** per call).
  There is **no way to dump all ads for a region/date range**. Enumeration means
  one query per candidate name or per batch of 10 pages.
- **Scraping the web UI is not a fallback:** Meta's terms prohibit unauthorized
  scraping; sustained scraping risks IP bans. Use the API.
- **No bulk download:** there is no official downloadable bulk file of the Ad
  Library (the web UI offers per-search report downloads only). The API is the
  only programmatic path.

### (b) Exact fields available (political/issue ads)

Fields are requested via the `fields` parameter; the default response is minimal
(`id` only). For `ad_type=POLITICAL_AND_ISSUE_ADS`, US ads:

| Field | Notes |
|---|---|
| `id` | Library ad ID |
| `page_id`, `page_name` | Who ran it (the Facebook Page) |
| `ad_snapshot_url` | Meta-hosted rendered preview (not a downloadable media file) |
| `ad_creative_bodies`, `ad_creative_link_titles`, `ad_creative_link_captions` | Ad text; null on video/image-only creative |
| `ad_creation_time`, `ad_delivery_start_time`, `ad_delivery_stop_time` | Stop time null while active |
| `currency` | Currency the ad was paid in |
| `spend` | `{lower_bound, upper_bound}` — **range only** |
| `impressions` | `{lower_bound, upper_bound}` — **range only** |
| `demographic_distribution` | Age/gender breakdown of who *saw* it |
| `region_distribution` | Where it was seen (state-level) |
| `funding_entity` | Free-text "Paid for by …" disclaimer — **not an ID** |
| `publisher_platforms` | Facebook, Instagram, Messenger, Audience Network |
| `bylines` | Page/attribution bylines |
| `ad_type`, `ad_reached_countries` | Query parameters, not per-ad fields |

**Not returned:** exact spend, exact impressions, creative media files, click/CTR/
conversion data, landing-page/destination URL (never exposed as a field), targeting
criteria (only who saw it, not who was targeted), or any FEC/committee identifier.

Useful query parameters: `ad_reached_countries=['US']` (required),
`ad_type=POLITICAL_AND_ISSUE_ADS`, `ad_delivery_date_min`/`ad_delivery_date_max`
(YYYY-MM-DD), `sort_by` (impressions_high_to_low, longest_running, most_recent,
delivery-start ascending/descending). A 2026 addition: a low-impression filter that
excludes ads below 1,000 impressions from bulk results.

### (c) Attribution to a person in the tracker — and failure modes

- **No FEC ID anywhere in Meta's data.** The join key is the Facebook **Page**.
  Attribution requires a **Page → candidate/committee map** that does not exist
  yet and must be built: one or more Pages per candidate (official campaign page,
  plus personal/official pages that also run ads), verified by hand or
  semi-automatically (page name + "Paid for by" + link to the candidate's site).
  The roster has no page IDs today.
- **Keyword search (`search_terms`) is noisy:** searching a candidate's name
  returns their own ads *and* opponents' attack ads mentioning them, issue ads
  mentioning them, and unrelated same-name people. Every hit must be classified
  by page, not by keyword.
- **Page-ID search is clean but incomplete:** it only finds ads from pages we
  already know. A candidate running ads from a second page, a joint-fundraising
  page, or a party page will be missed.
- **Issue ads pollute the pool:** the archive includes social-issue ads, not just
  candidate ads. A page's ads may include non-candidate advocacy that must not
  be attributed to a candidate's total.
- **Funding entity is free text**, e.g. "Paid for by Friends of X" — useful as a
  cross-check against FEC committee names, but it is not normalized and does not
  always match the committee's legal name.
- **Deduplication trap:** the same creative run across Facebook + Instagram is
  one ad record with multiple platforms (fine), but the same creative re-uploaded
  as a new ad is a new record (spend must be summed across records, not
  de-duplicated by creative text).
- **Coverage blind spots:** ads rejected in review, ads that ran only to a narrow
  custom/lookalike audience, and ads that stopped delivering before the indexing
  pipeline caught them may never appear. Meta has not published exact retention
  for non-political ads; political/issue ads are retained 7 years.

### (d) Coverage and freshness for the 2026 cycle

- **Coverage:** all ads about social issues, elections, or politics delivered
  anywhere in the world, **7-year retention** — the 2026 cycle is fully in scope.
  US commercial ads are not in the API at all (irrelevant here). EU political ads
  ended Oct 6, 2025 (Meta stopped selling them under the EU TTPA regulation) —
  irrelevant for US 2026.
- **Freshness:** near-real-time; active ads are included, and spend/impression
  ranges update as ads run. A pull taken Nov 12, 2026 covers the cycle through
  Election Day (Nov 3, 2026) plus post-election ads; re-pull after the cycle
  closes to catch late activity.
- **Scale warning:** at 200 calls/hour, a full-universe pull is a multi-day job.
  One query per candidate name (or per 10 pages) × pagination × ~4,400 candidates
  in phase 2, plus re-pulls, is weeks of wall-clock time on a single token.
  **Scope Meta v1 to the 664-person roster** (or the 120th only) and expand later.

### (e) Exact vs. ranges; for/against

- **Spend and impressions are ranges only.** Documented bucket ladder (USD):
  <$100, $100–499, $500–999, $1K–5K, $5K–10K, $10K–50K, $50K–100K,
  $100K–500K, $500K–1M, **$1M+ (open-ended)**. The top bucket is the killer for
  this tracker: the biggest 2026 spenders (Senate races in the tens of millions)
  will sit in an unbounded bucket, so their Meta totals will be a lower bound
  with no usable upper bound. Standard practice is the midpoint of each band
  (geometric mean preferred over arithmetic for the wide bands); totals are
  estimates with a stated margin, never audited amounts.
- **For/against is NOT recorded.** There is no support/oppose field. Direction
  must be inferred: ads from the candidate's own page/committee are support;
  ads from an outside group naming the candidate require reading the creative
  (or matching the buyer to FEC Schedule E, which does record support/oppose for
  independent expenditures). Do not ship a for/against split in v1; ship totals
  first, add direction as a classified second step (see §5).

---

## 2. Google Ads Transparency Center

### (a) Access method and auth/approval

- **There is no official Transparency Center API.** Google publishes no documented
  endpoint for the Center's ad data, and the Google Ads API only reaches accounts
  your own credentials control — it cannot see a competitor's ads.
- **The supported programmatic path is the BigQuery public dataset
  `bigquery-public-data.google_political_ads`** — Google's own machine-readable
  record of election advertising, free to query. No identity verification, no
  approval, no application. Needs only a Google Cloud project; the first 1 TB of
  queries/month is free (on-demand pricing per TB beyond that — verify the current
  rate at build time; the queries here are small if filtered by region/date).
- **Two unofficial alternatives, not recommended as primary:**
  - The Center's undocumented internal RPC (the Angular front end posts to
    internal endpoints under adstransparency.google.com). Fragile, unversioned,
    breaks without notice.
  - Third-party vendor APIs that wrap the RPC (e.g. ReefAPI — paid credits,
    ~$0.67–$1.50 per 1,000 credits). A vendor dependency for a core data layer
    is the wrong call when an official dataset exists.
- **Reference implementation:** the Wesleyan Media Project's open-source
  `google_ads_archive` repo (github.com/Wesleyan-Media-Project/google_ads_archive)
  provides BigQuery scheduled-query scripts (daily advertiser-spend snapshots,
  hourly creative deltas) built for exactly this use — the CREATIVE project.
  Use it as the build template.

### (b) Exact fields available

Dataset tables (region-filtered; US = `region = 'US'`):

| Table | One row is… | Key fields |
|---|---|---|
| `creative_stats` | one ad creative | `ad_id`, `advertiser_id`, `advertiser_name`, format (text/image/video), `regions`, first/last shown dates, **spend range** (`spend_range_min_usd`, `spend_range_max_usd`, plus other currencies), **impressions band**, age/gender/geo targeting categories, ad URL/preview |
| `advertiser_stats` | one advertiser | `advertiser_id`, `advertiser_name`, **`public_ids_list`**, `regions`, `elections`, total creatives, **`spend_usd`** (lifetime) |
| `advertiser_weekly_spend` | advertiser × week | `advertiser_id`, week, **`spend_usd` reported in $100 increments** — the most precise Google figure (rounded to the nearest $100 at advertiser-week grain) |
| `advertiser_declared_stats` | one advertiser | regulatory/verification information on the advertiser |
| `geo_spend` | one region | total spend served into each region (all advertisers combined) |

The web UI (adstransparency.google.com) shows the same data per advertiser/creative
plus "Paid for by" disclosure; it has no download button. Election ads are kept up
to 7 years; commercial ads 1 year. New creatives take **48–72 hours** to appear.

### (c) Attribution to a person in the tracker — and failure modes

- **This is Google's decisive advantage: the FEC ID is in the data.**
  Google's US election-ads verification requires the advertiser to verify as a
  committee with its **exact legal name and its FEC ID** (federal committees) or
  state registration number / EIN. The Transparency Center shows the advertiser's
  registration ID for election advertisers, and `advertiser_stats.public_ids_list`
  carries the public IDs. Independent confirmation: the transparencyparty.org
  tracker cites "The library lists FEC committee number C00703843 for this
  advertiser, and the FEC committee file names this member as that committee's
  candidate." So the join is **Google advertiser → FEC committee ID → tracker
  person**, the same key the FEC layers already use. (Verify `public_ids_list`
  contents against the FEC committee master at build time — it is documented as
  public IDs, and the FEC ID should be among them; if it is not populated for
  some advertisers, fall back to exact legal-name matching against the FEC
  committee file, logged as a fallback per architecture.md §2.)
- **Failure modes:**
  - **Classifier gaps:** the dataset only includes ads Google classified as
    election-related from verified political advertisers. Ads that ran without
    verification, or that Google's classifier missed, are absent. Spend is
    therefore a **lower bound** on a candidate's true Google spend.
  - **Non-candidate advertisers in the set:** the dataset includes government
    departments, news-media companies, consultancies/vendors, and commercial
    brands the classifier caught by mistake (documented in the India ledger
    analysis of the same dataset). Advertisers must be filtered to
    candidate/committee/party/super-PAC entities before attributing.
  - **Agency/vendor pages:** a media-buying agency may run ads for many
    candidates under one advertiser account; the "Paid for by" disclosure and
    the creative itself are then the only attribution signal, and the FEC-ID
    join may point at the agency rather than the candidate.
  - **Joint fundraising / party committees:** ads paid for by a joint committee
    or the party name a candidate but benefit several; attributing the full
    amount to one person overstates it. Same class of problem as FEC joint
    fundraising — document the rule (attribute to the named candidate only when
    exactly one candidate is named; otherwise flag as unattributed party/joint
    spend).
  - **Currency:** US advertisers are USD; `spend_usd` is the field to use.
    Other-currency columns exist for other regions — ignore them.

### (d) Coverage and freshness for the 2026 cycle

- **Coverage:** election ads only, from 2018, 7-year retention. Third-party
  measurement (ReefAPI, Nov 3, 2026) counted **981,207 US election ads** in the
  Center — the full 2026 universe is in the dataset, at ad level.
- **Freshness:** `creative_stats` is updated several times a day;
  `advertiser_weekly_spend` weekly; the archive is officially updated weekly.
  A pull on Nov 12, 2026 covers the cycle through Election Day plus the
  post-election week; re-pull after the cycle closes.
- **Platforms covered:** Google Search, YouTube, Display, Shopping, Maps, Play —
  i.e. the largest digital video/search buy in federal races. This is the one
  source that captures YouTube pre-roll, which Meta cannot see and the FEC
  cannot break out.

### (e) Exact vs. ranges; for/against

- **Spend is ranges at creative level** (`spend_range_min_usd` /
  `spend_range_max_usd`); **rounded to $100 increments at advertiser-week
  level** (`advertiser_weekly_spend`). Impressions are bands. The recommended
  primary aggregation is `advertiser_weekly_spend` (most precise), with
  `creative_stats` ranges used for ad counts, dates, and targeting — and the
  midpoint rule applied consistently where ranges are unavoidable.
- **For/against is NOT recorded.** Same inference problem as Meta: candidate
  committee = support; outside group = read the creative or match the buyer to
  FEC Schedule E (support/oppose) to classify. Do not ship for/against in v1.

---

## 3. FCC political files (TV broadcast ad buys)

### (a) Access method and auth/approval

- **The source is the FCC's Online Public Inspection File (OPIF) at
  publicfiles.fcc.gov.** Free, no auth, no approval. The FCC's developer page
  (publicfiles.fcc.gov/developer) states the site itself is built off its own
  APIs and that the APIs are free to use under the FCC's terms.
- **What the API actually gives you is file discovery, not data:** entity search
  (call sign, facility ID, network, channel, ZIP for cable), per-entity document
  lists sorted by upload date, keyword search against **file names and folder
  paths** (not file contents), and RSS feeds of new uploads. The documents
  themselves are **PDFs** (contracts, order forms, invoices, rate cards) of
  highly variable quality — some typed, some scanned, some handwritten.
- **There is no documented structured endpoint for political-file contents.**
  No bulk download of structured buy data exists from the FCC. Any build must
  download PDFs per station and extract the fields by parsing/OCR.
- **Scale of the crawl:** ~1,700+ full-power commercial TV stations (plus Class A
  TV, radio, cable systems with 1,000+ subscribers, DBS, SDARS). Each station
  maintains its own political folder; formats differ by station group and by the
  media-buying agency that filed the paperwork.

### (b) Fields that exist per buy (inside the PDFs)

Under 47 CFR 73.1943 / 76.1701, the political file must contain, for each request
to purchase time by or on behalf of a candidate, or for a message on a political
matter of national importance:

- whether the request was **accepted or rejected**;
- the **rate charged** and the **class of time** purchased;
- the **date and time** the communication aired (schedule of spots);
- the **name of the candidate or issue** the ad refers to;
- the **name of the person purchasing the time**, and if on behalf of another
  person, that person's name (the sponsor/buyer — usually the committee or its
  media-buying agency);
- for candidate ads, whether the ad was **authorized** by the candidate.

So the raw material for a per-person TV column exists in principle: buyer +
candidate named + amount + dates + station/market. It is just not machine-readable.

### (c) Attribution to a person in the tracker — and failure modes

- **Attribution path:** buyer name (committee or agency) → FEC committee file
  (name match) → person; and candidate named in the filing → person. Where the
  buyer is an agency, the candidate named in the filing is the attribution key.
- **Failure modes (these are why this is deferred, not just slow):**
  - **Unstructured PDFs:** no standard schema; amounts appear in contract
    totals, invoice line items, or rate-card math, in different places per
    station group. ProPublica's verdict after its Free the Files project:
    "we still can't get an accurate count of the money spent. The FCC's data
    is just too dirty" — and some filings are missing required information such
    as the candidate discussed.
  - **Contract vs. aired:** a contract amount is a *purchase*; spots get
    pre-empted, moved, or makegooded. The file also contains invoices and
    affidavits of performance; reconciling contract → actually-aired → actually-
    paid requires reading multiple documents per buy.
  - **Compliance gaps are documented:** in Oct 2026 the FCC settled with
    Nexstar after finding **43 stations had failed to promptly upload political
    records**. Uploads are required "promptly" but late/missing filings are a
    known, recurring fact.
  - **Retention is 2 years** for political files. 2026 files will age out of
    the online file around late 2028 — staging a copy now matters if this is
    ever built.
  - **Cable is patchier than broadcast:** cable systems' political files are
    less consistently online and less consistently structured than broadcast
    TV stations'.
  - **Market ≠ district:** a buy in a media market (DMA) covers many districts;
    the filing says which market, not which district the spend was aimed at.
    Statewide Senate buys are clean; House buys in multi-district markets need
    the candidate named in the filing to attribute, and issue ads naming no
    candidate cannot be attributed to a person at all.

### (d) Coverage and freshness for the 2026 cycle

- **Coverage in law is universal** (every full-power commercial TV/radio station,
  Class A TV, large cable systems, DBS, SDARS). **Coverage in practice is
  incomplete** for the reasons above.
- **Freshness:** stations must upload promptly (generally immediately unless
  unusual circumstances). In practice, filings appear within days of the buy,
  with the documented late-upload exceptions.
- **Scale of the channel (why the gap matters):** Wesleyan Media Project /
  AdImpact analysis through Oct 25, 2026 put total 2026 political ad spending at
  **~$7.1 billion**, with broadcast TV at **~53% of cycle spend** (63.5% in the
  final two weeks, Oct 12–25), ~$3B in Senate races and ~$2B in House races.
  Digital (all platforms) was only ~12.5% cycle-to-date. **A tracker with Meta +
  Google but no TV captures the minority of ad dollars.** Say so plainly in
  methodology; do not let a Meta+Google total be read as "ad spending."

### (e) Exact vs. ranges; for/against

- **Amounts are exact dollars** — this is the one source where spend is a real
  number (contract/invoice amounts), not a range. That is its main attraction.
- **For/against is not a coded field**, but it is usually inferable: the filing
  states whether the ad was authorized by the candidate, and the buyer's identity
  plus the candidate named normally determines direction (candidate committee
  buy = support; outside group naming an opponent = oppose). Ambiguous cases
  (party/joint buys, issue ads) need the creative or a cross-check against FEC
  Schedule E, which records support/oppose for independent expenditures.

### ProPublica Free the Files — status

- **Not a 2026 source.** Free the Files was ProPublica's 2012 project (33 swing
  markets) that crowdsourced transcription of FCC PDFs into structured data and
  exposed an API (markets / stations / committees / filings, including FEC IDs
  where known). The API and its codebook still exist, but the data is 2012-era.
  It is a proof that the PDF-extraction approach *can* work with enough human
  review — and a warning about the effort involved (nearly 1,000 volunteers,
  and still no accurate total). **Do not build on it for 2026.**

### The structured TV alternative: AdImpact / Wesleyan Media Project

- The only structured, per-race TV dataset is commercial: **AdImpact**
  (formerly Kantar/CMAG) monitors airings and estimates spend across broadcast,
  cable, CTV, radio, and digital. The Wesleyan Media Project analyzes AdImpact
  data and publishes aggregate findings (race-level totals, sponsor shares,
  tone/attack coding, AI-ad tracking) — e.g. the Oct 29, 2026 release on Senate
  spending. WMP's detailed per-ad data is available to researchers on request,
  not as a public bulk download, and AdImpact itself is enterprise-priced.
- **Recommendation:** do not license AdImpact for v1. Revisit if/when the tracker
  goes public and TV becomes the missing piece worth paying for, or if WMP
  grants researcher access to the underlying 2026 file. OpenSecrets also
  republishes AdImpact-based ad-spending totals by race — usable as a
  cross-check at race level, not a per-person source.

---

## 4. Cross-cutting limitations (all sources)

1. **Ranges, not exact dollars (Meta + Google).** Store min/max/midpoint; label
   every ad figure an estimate. This is a deliberate, documented exception to
   architecture.md §6 ("money is exact"). The standing audit still applies in
   adapted form: per-cycle bounds must sum to the career bounds, and the
   midpoint must be the defined function of the bounds (midpoint of the summed
   bounds, not the sum of per-ad midpoints — pick one rule and document it).
2. **No for/against field anywhere.** Direction is a classification step, not a
   source field. Ship totals first; add for/against only after a documented
   classification rule (advertiser identity → FEC Schedule E cross-check →
   creative read for the top spenders).
3. **Attribution is to the *spender*, not the *beneficiary*.** A super PAC's ads
   for Candidate A are the PAC's spend, not A's. The per-person columns must
   distinguish "ads paid for by the person's own committee" from "ads paid for
   by others naming/benefiting the person." This mirrors the existing UDP
   support/opposition-credit distinction — reuse that framing.
4. **Coverage is partial by construction.** Meta+Google ≈ digital; TV/radio/
   mail/CTV outside Google are missing. Never present an "ad spend total" without
   the channel list and the "partial" label.
5. **Double-counting risk across sources.** A dollar of TV spend also appears in
   FEC disbursements (committee → media buyer) and a dollar of digital spend
   appears in FEC disbursements too. Ad columns and FEC columns are **different
   lenses on overlapping money** — never add them together, and say so in
   methodology (same discipline as the existing "UDP is not accepted money" rule).
6. **Classifier noise.** Google's election-ad classifier and Meta's political-ad
   classifier both include issue advocacy and misclassify some commercial ads.
   Both exclude some real political ads. Totals are lower bounds with noise.
7. **2026 cycle is partial.** Pulls taken Nov 12, 2026 cover through Election Day
   plus one post-election week. Re-pull after the cycle closes (and after the
   FEC 2026 re-pull) for final figures.

---

## 5. Recommended build plan

### Phase A — Google first (estimated effort: days, no approvals)

1. **Access:** create a GCP project; enable BigQuery; confirm the free-tier
   headroom for the queries below (filter by `region = 'US'` and 2025–2026 dates
   to keep bytes scanned small).
2. **Bronze (raw, immutable, dated):**
   `work/bulk/ad_spending/google/`
   - `google_political_ads_2026-11-12_advertiser_weekly_spend.csv` — full US
     extract of `advertiser_weekly_spend` (2025-01-01 → pull date).
   - `..._advertiser_stats.csv` — full US `advertiser_stats` (one row per
     advertiser, with `public_ids_list`).
   - `..._creative_stats.csv` — full US `creative_stats` for 2026-cycle ads
     (large; store as received, partitioned by month if needed).
   - A `pull-log-google.md` recording the queries, row counts, and pull date.
   - Optionally reuse the Wesleyan CREATIVE repo's scheduled-query SQL as the
     pull template.
3. **Silver (staging):** `work/ad_spending_google_staging.json` —
   advertisers filtered to federal political entities; FEC committee ID joined
   via `public_ids_list` (verified against the FEC committee master already
   staged in `work/bulk/`); name-match fallback logged per architecture.md §2;
   joint/party advertisers flagged unattributed where more than one candidate is
   named; weekly spend summed to per-(advertiser, cycle).
4. **Gold (per-person columns, 2026 cycle):**
   - `google_ad_spend_2026_min`, `google_ad_spend_2026_max`,
     `google_ad_spend_2026` (midpoint — the display value), `google_ad_count_2026`
     (number of creatives), `google_ad_first_seen_2026`, `google_ad_last_seen_2026`.
   - Attribution split, from the start: `google_ad_spend_own_2026` (paid for by
     the person's own committee) vs. `google_ad_spend_other_2026` (paid for by
     others naming the person). This split is derivable from the FEC-ID join
     and does not need a for/against classifier.
   - Career columns are **not** needed in v1 — ad data is 2026-cycle only
     (the dataset goes back to 2018, but the tracker has no pre-2026 ad
     columns; adding earlier cycles is a later decision, and per architecture.md
     §7 the per-cycle grain makes it a query, not a re-pull).
5. **Methodology §15:** source, tables, fields, the $100-increment and
   range/midpoint rules, the FEC-ID join and its fallback, the own/other split,
   the lower-bound + classifier-noise caveats, and the "never add to FEC money"
   rule. Same change as the data (architecture.md §10).
6. **Audit:** per-cycle bounds sum to career bounds (trivially true in v1 with
   one cycle); row counts reconcile bronze → silver → gold; spot-check the top
   10 Google spenders against the Transparency Center web UI.

### Phase B — Meta second (estimated effort: 1–2 weeks, needs Craig)

1. **Access (Craig):** complete identity/location confirmation at facebook.com/ID;
   create the developer app; issue a system-user token. This is the only step
   that needs Craig, and it is a hard gate — start it first, in parallel with
   Phase A, because approval takes days.
2. **Build the Page map first:** for the 664-person roster, collect each
   person's official campaign Facebook Page ID (web UI search + page "About"
   info + "Paid for by" cross-check against FEC committee names). Store as
   `work/page_map.csv` with `person_key, page_id, page_name, verified_date,
   source`. Pages that cannot be verified stay out and are counted as a coverage
   gap, not silently skipped.
3. **Bronze:** `work/bulk/ad_spending/meta/` — raw `ads_archive` JSON responses
   per page batch, dated; one file per pull run. Pull by `search_page_ids`
   (10 per call), `ad_type=POLITICAL_AND_ISSUE_ADS`, `ad_reached_countries=['US']`,
   `ad_delivery_date_min=2025-01-01`. Throttle to the 200/hour limit; expect a
   multi-day pull for the full roster — run it as a background job with resume
   state, and log progress per page.
4. **Silver:** dedupe by ad `id`; parse spend/impression bounds; classify each
   ad's spender as own-committee vs. other (via the page map); flag issue-only
   ads for exclusion.
5. **Gold (per-person columns, 2026 cycle):**
   - `meta_ad_spend_2026_min`, `meta_ad_spend_2026_max`,
     `meta_ad_spend_2026` (midpoint), `meta_ad_count_2026`,
     `meta_ad_impressions_2026_min/max`.
   - Same own/other split as Google: `meta_ad_spend_own_2026`,
     `meta_ad_spend_other_2026`.
   - **Top-bucket warning:** any person whose spend includes a $1M+ bucket ad
     gets a `meta_ad_spend_top_bucket=true` flag and a note — their total is a
     lower bound with no meaningful upper bound.
6. **Methodology §15 (extended):** the page-map method, the 200/hour limit and
   pull window, the bucket ladder, the midpoint rule, the top-bucket flag.
7. **Audit:** same as Google; spot-check top 10 Meta spenders against the Ad
   Library web UI; reconcile Meta totals against FEC disbursements to Meta
   (order-of-magnitude only — the two will not match exactly, and the gap is
   itself informative).

### Phase C — combined view + for/against (after A and B land)

1. **Combined columns (2026 cycle):**
   `ad_spend_total_2026_min/max` and `ad_spend_total_2026` (midpoint) =
   Google + Meta only, **labeled "digital (Google + Meta), partial — TV/radio/
   mail excluded."** Plus `ad_spend_sources_2026` (which channels have data for
   this person) so a zero is distinguishable from "no data."
2. **For/against classification (second step, not v1):** rule in order —
   (i) spender is the person's own committee → support; (ii) spender matches a
   committee with FEC Schedule E rows in the same race → use the FEC
   support/oppose coding; (iii) otherwise read the creative (top spenders only)
   or leave direction `unknown`. Columns only when the rule is documented:
   `ad_spend_for_2026`, `ad_spend_against_2026`, `ad_spend_direction_unknown_2026`.
3. **Tracker presentation:** an "Ad spending (2026, partial)" section per person
   with source breakdown and the estimate warning; a leaderboard by
   `ad_spend_total_2026`; a filter for "no ad data" vs. "zero ads."

### Phase D — TV (deferred; decide separately)

Do **not** start in v1. When/if Craig wants it, the options in order of
practicality are:
1. **Researcher access to Wesleyan Media Project / AdImpact 2026 data** —
   ask WMP for the underlying file; if granted, stage it as bronze and map
   sponsor → FEC committee ID the same way as Google.
2. **FCC PDF extraction pilot** — pick the top 10 media markets by 2026 House/
   Senate spend, download the political folders, and build an extraction +
   human-review pipeline; measure accuracy against FEC disbursements before
   scaling. This is a project in its own right (OCR, form variance, contract-
   vs-aired reconciliation), not a column add.
3. **FEC-disbursement proxy** — sum committee disbursements to known media
   buyers as a rough TV-spend indicator. Cheap but crude (includes production,
   commissions, and digital buys routed through the same firms); label it a
   proxy, not TV spend.

## 6. Decisions needed from Craig

1. **Google first, Meta second — agreed?** (Phase A needs no approval to start;
   Phase B needs his ID verification.)
2. **Scope of Meta v1:** 664-person roster, or 120th only? (Recommend the roster;
   the page map is the same work either way.)
3. **Midpoint rule:** arithmetic midpoint of each band, or geometric mean?
   (Recommend geometric mean for the wide Meta bands; arithmetic for Google's
   $100-increment weekly figures, which are already near-exact. Document the
   choice.)
4. **Earlier cycles:** 2026 only in v1, or backfill Google to 2018 for career ad
   columns? (Recommend 2026 only; the dataset makes backfill cheap later.)
5. **TV:** leave deferred, or pursue WMP/AdImpact access in parallel?
   (Recommend deferred — but note the 2-year FCC retention clock: if PDF
   extraction is ever wanted, the raw PDFs should be staged before late 2028.)

## Sources consulted (Nov 12, 2026)

- Meta Ad Library API: Meta for Developers `ads_archive` reference (via
  third-party guides checked against it Oct 28–Nov 4, 2026 — adsuploader.com,
  admanage.ai, adlibrary.com, adspo.co, primores.org, admapix.com,
  gethookd.ai, lilachbullock.com, dailyintelservice.com).
- Google Ads Transparency Center: adextract.co (Nov 2026), admakeai.com,
  tryadlicio.com, reefapi.com/docs/google-ads-transparency (Nov 3, 2026
  measurement: 981,207 US election ads); Wesleyan Media Project
  `google_ads_archive` repo (github.com/Wesleyan-Media-Project/google_ads_archive);
  vishalsingh.org "What's in the Ledger" (Sep 15, 2026, on the BigQuery dataset's
  structure); Google election-ads verification guides (bluelist.ai / electbase.com,
  Sep 25, 2026); transparencyparty.org (FEC ID in the Transparency Center,
  verified example C00703843).
- FCC: publicfiles.fcc.gov/developer, /about, /faq (accessed Nov 12, 2026);
  47 CFR 73.1943 / 76.1701 (OMB supporting statement, Sep 2026);
  fcc.gov political programming page; ProPublica Free the Files (2012 project;
  source.opennews.org; RPublica package README); Nexstar political-file
  settlement (thedesk.net, Oct 28, 2026).
- Wesleyan Media Project / AdImpact 2026 releases (mediaproject.wesleyan.edu,
  Oct 15 and Oct 29, 2026) and Insideradio summary (Nov 2026): $7.1B cycle
  ad spend through Oct 25, 2026; broadcast ~53% cycle-to-date.
