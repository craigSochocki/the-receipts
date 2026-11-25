# Pro-Israel PAC list — where it comes from

The committee IDs in `data/source/pro_israel_pacs.csv` are Track AIPAC's published
"View all Pro-Israel PACs" sheet, linked from https://www.trackaipac.com/about/aipac and
downloaded on Nov 25, 2026 from
https://docs.google.com/spreadsheets/d/1h3JASnY_LJ3sOOvBeXkDExfiL5a8Mx_5Oy2hZrCn6TU
(CSV export via the sheet's gviz endpoint). Columns kept as published: name, FEC ID,
year registered, status. Craig chose this list (Nov 25, 2026) so the tracker's figures
compare directly with Track AIPAC's.

## Their method, in their words

- FAQ (https://www.trackaipac.com/about/faq): "Figures reflect federal career totals from
  all pro-Israel PACs & their large donors: PACs: Direct and earmarked donations from
  pro-Israel PACs to candidates; IE: Independent Expenditures (ad spending etc.) by
  pro-Israel PACs on behalf of candidates."
- Methodology post (https://www.trackaipac.com/media/blog/updated-methodology): V2 (2025)
  pulled direct donations and IEs from the FEC; V3 (2026) added "FEC reportable ($200 or
  more) donors with a history of giving to pro-Israel PACs who were also making
  contributions to candidates." The donor list and matching rules are not published.

## What the tracker covers

Direct contributions and supporting IEs from listed committees, from the pinned bulk
files. Not covered: conduit (bundled) checks and the donor-network layer — see
methodology §8 item 22.

## The case that prompted it: John Fetterman (Nov 25, 2026)

Track AIPAC showed an "Israel Lobby Total" of $487,491. FEC sources:

| Source | Amount |
|---|---|
| AIPAC PAC and UDP, every cycle (bulk pas2 and the FEC API, both sides) | $0 |
| Direct contributions from listed PACs, bulk pas2 (2022–2026) | $32,381 |
| Supporting IEs by listed PACs, IE files (JDCA PAC $284,716.79, Democratic Jewish Outreach PA $3,895.40) | $288,612.19 |
| J Street PAC conduit checks, FEC API Schedule B (2022 $214,625; 2024 $1,386) — not in bulk | $216,011 |
| JACPAC ActBlue earmarks, FEC API (2022) — not in bulk | $10,757 |
| NORPAC 2026 earmarked donations, FEC API — not in the pinned snapshot | $25,000 |

The RJC Victory Fund's $1,802,782.73 of IEs opposing Fetterman (2022) is opposition and
is not counted. A Washington Examiner review of FEC filings since 2022 also found no
AIPAC PAC or AIPAC-earmarked money to Fetterman.

## Entries worth a second look

The list is used as published, but some entries are not obviously pro-Israel lobby
groups by name: Phoenix Education Partners / Apollo Ed's governance fund, American
Principles, Affordable Chicago Now, Chicago Progressive Partnership, Elect Chicago Women,
Mainstream Democrats PAC, and Bend the Arc is absent while J Street is present.
