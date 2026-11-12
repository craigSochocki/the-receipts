# Congress money-tracker roster — build notes

Built Nov 12, 2026. Files: `roster.csv`, `roster.json` (665 persons).

## Counts
- Total persons: 665
- In 119th only: 125
- In 120th only: 125 (of which 119 brand-new to Congress, 6 returning former members)
- In both: 410
- In 119th, 120th membership unknown: 5
- In 119th total: 540; in 120th total (named): 535

## Sources
- 119th: `legislators-current.yaml` from unitedstates/congress-legislators
  (fetched Nov 12, 2026; 539 persons). The repo has no 2027-start terms and no
  leadership file, so 120th membership and leadership came from elsewhere.
- 120th membership: Wikipedia "120th United States Congress" (crawled Nov 12,
  2026 11:26 UTC) — full Senate + House + delegate lists, transcribed to
  `120th_roster.json`. Cross-checked against Wikipedia "List of new members of
  the 120th United States Congress" (crawled Nov 12, 2026 04:43 UTC).
  Validation: per-state House counts match apportionment exactly (430 named of
  435 seats); Senate 99 named of 100.
- Returning former members (bioguide + FEC IDs): `legislators-historical.yaml`
  from the same repo.
- FEC IDs for 120th freshmen: api.open.fec.gov with DEMO_KEY, matched on
  office + state + district + party for the 2026 cycle; 113 of 121 found
  automatically, 7 more found with manual name-variant queries (see below).
- 119th leadership: Wikipedia 119th Congress leadership section + House
  history.house.gov + Senate/House leadership pages (all 17 roles verified).

## Scope decisions (flag for review)
- "119th" = persons in `legislators-current.yaml` (539) + Sherrod Brown
  (takes his Senate seat Dec 15, 2026, still during the 119th). People who
  served in the 119th but left before Nov 2026 (e.g. JD Vance, Marco Rubio,
  Lindsey Graham, David Scott, Sylvester Turner, Raúl Grijalva, Gerry
  Connolly, Mark Green, Mikie Sherrill, Marjorie Taylor Greene, Doug LaMalfa,
  Tony Gonzales, Eric Swalwell, Sheila Cherfilus-McCormick, Markwayne Mullin,
  Mike Waltz) are NOT in the roster — they are not in the repo's current
  file. Add them from `legislators-historical.yaml` if full "anyone who
  served in the 119th" coverage is wanted.
- Delegates (6) are included as House members with district 0, matching the
  repo's convention (district 0 = at-large/delegate).
- Party labels: DFL (Minnesota) normalized to Democrat; PR Resident
  Commissioner Pablo Hernández Rivera kept as PPD with a note.
- Kevin Kiley (CA-03) is recorded as Independent in the 119th (he left the
  Republican Party Mar 9, 2026; repo `party_affiliations` confirms).

## 120th membership unknown (in_120th = "unknown", 5 persons)
- Dan Sullivan (R-AK, Senate) — race uncalled.
- Nick Begich III (R-AK, House at-large) — race uncalled.
- Mike Thompson (D-CA-04) — seat listed TBD (D).
- Jay Obernolte (R-CA-23) — seat listed TBD.
- Cleo Fields (D-LA-06) — runoff Dec 12, 2026.
- Also TBD with no incumbent row: LA-05 (Julia Letlow left for the Senate).
  No roster row can be created for an unknown winner; re-run after these
  races are called. All other 120th results are media calls, uncertified.

## Early / special swearing-ins (in both congresses)
- Kevin Hern (OK): House in 119th; sworn in to the Senate Nov 30, 2026.
- Sherrod Brown (OH): takes Senate seat Dec 15, 2026 (defeated Jon Husted
  in the special election); serves the remainder of the term to Jan 2029.
- Jon Husted serves until Dec 15, 2026; Alan Armstrong (OK, appointed)
  serves until Nov 30, 2026; Darline Graham (SC, appointed) serves to Jan 3, 2027.
- Ashley Moody (FL) was re-elected in the Nov 3 special election and serves
  in both congresses.
- Amy Klobuchar (MN) and Marsha Blackburn (TN) were elected governor and
  plan to resign from the Senate in Jan 2027; counted as in the 120th as
  seated at its start, with successors TBD (appointed).

## Unverified / open items
- 120th leadership: ALL TBD in the file. Leadership elections are Nov 18-19,
  2026. The Wikipedia 120th page lists Republican leaders (Thune, Barrasso,
  Cotton, Moreno; Jordan, Emmer, McClain, Brian Jack) — those names are kept
  in the affected rows' notes as UNVERIFIED, not in leadership_120.
- Jasmine Clark (GA-13): Wikipedia's new-members note says she was elected
  in a special election to replace David Scott; whether she is seated before
  Jan 3, 2027 is unverified — counted as 120th-only pending confirmation.
- FEC IDs: only Alan Armstrong has none (appointed senator who never ran
  for the seat — no FEC candidate record found). Manual fixes applied:
  Flanagan (filed as Margaret Flanagan, S6MN00440), Kingston (James Morris
  Kingston, H6GA01109), Jake Johnson (Jacob Johnson, H6MN01190), Bob Harvie
  (Robert J. Harvie, H6PA01181), Matt Little (H6MN02230, party DFL),
  Janelle Sarauw (H6VI01065, FEC party IND though listed D), Darline Graham
  (S6SC04437). DFL filers list party DFL at the FEC, not DEM.
- Chamber switchers (House → Senate, 6): Andy Barr, Harriet Hageman,
  Kevin Hern, Julia Letlow, Barry Moore, Chris Pappas.
- Freshmen returning to Congress after prior service (6): Jerry Carl,
  Hilda Solis, Melissa Bean, Colin Allred, Ben McAdams, Elaine Luria.
  Their FEC IDs are the historical ones from the repo; confirm they match
  the 2026 candidacy before joining to FEC data (candidate IDs usually
  persist across cycles for the same office).
