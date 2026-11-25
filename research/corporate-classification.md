# Corporate-PAC classification check (Nov 25, 2026)

Snapshot `fec-bulk-2026-11-22`. Prompted by phase 3 of the cycle-neutral work: five
off-class senators judged on their last election came out dirty, two of them (Sanders,
Warren) on money they are known not to take.

## The rule being checked

Methodology §2: a committee is corporate when, in the **same cycle's** committee master
(`cm`), `CMTE_TP IN ('Q','N')` and `ORG_TP IN ('C','W')`. `ORG_TP` is the connected
organization type the filer reports on Form 1.

## Findings

1. **NEA Fund for Children and Public Education (C00003251) — one-cycle coding blip.**
   The National Education Association's PAC is `ORG_TP = L` (labor) in every cycle from
   2016 to 2026 except **2024, where the cm file has `C`**. Its 2024 money to roster
   members (227 people over all cycles; $1,310,000 career as "corporate") therefore counts
   as corporate PAC in 2024 only. It is all of Sanders' 2024 "corporate" money ($2,000) and
   $5,000 of Warren's ($7,500).
2. **Democracy Engine, Inc., PAC (C00468314) — a conduit coded corporate.** `CMTE_TP = N`,
   `ORG_TP = C`, `CMTE_DSGN = U` in every cycle. It is a payment processor that forwards
   individual donors' contributions (like ActBlue or WinRed). $502,745 to 101 roster people
   counts as corporate PAC. It is $176,783 of Warnock's 2022 corporate figure, and the
   **only** dirty money of Bob Brooks (PA-7, incoming) in 2026 ($19,129): his published
   `clean_2026` is False because of it.
3. **Associations and federations coded `C`.** Some trade and professional bodies report
   `ORG_TP = C` (or `W`): e.g. the Blue Cross and Blue Shield Association, the American
   Association of Orthopaedic Surgeons, the American College of Radiology Association, the
   Consumer Technology Association, the American Peanut Shellers Association, the Alabama
   Farmers Federation, the Iowa Farm Bureau Federation. Whether these are "corporate" is a
   judgement call: many are incorporated trade associations, which the FEC lets self-code.
4. **Democracy Engine is a pure conduit.** It is a for-profit payment platform for
   political donations; its FEC audit records the treasurer's statement that the PAC has
   never contributed to a candidate except as an individual's earmark. Business groups use
   it to route employees' individual donations to chosen candidates.
5. **The FEC code is noisy both ways.** 2,473 committee-cycles to roster people carry a
   code different from the committee's usual one. A "usual code" rule would fix NEA's 2024
   but would also move a hunters' club (Safari Club), a pilots' association (AOPA) and a law
   firm (Akin Gump) into corporate, and an accounting firm (PwC) out — so no automatic rule
   is right on its own.
6. **Name matching is not a rule.** A keyword scan also catches real corporations (AFLAC,
   Union Pacific, Abbott Laboratories, TIAA, USAA, Honeywell's "council"). Any fix needs a
   reviewed list or a code-based rule, never a name pattern.

## Totals (career, roster people, money counted as corporate PAC)

From a name scan, so indicative only: corporate-looking names $929.3M; labor-looking
$24.5M (mostly real corporations, see 4); association-looking $21.0M; conduit-looking
$0.6M (Democracy Engine is almost all of it).

## Options (for Craig)

- **A committee's type across cycles**, not the same cycle's alone: e.g. use the code it
  reports in most cycles, so a one-cycle blip (NEA 2024) does not flip a class.
- **A reviewed override list** in `data/source/` (committee ID, class, evidence), for
  conduits such as Democracy Engine and any association judged non-corporate.
- **Conduit money out of the corporate column**: forwarded contributions come from
  individuals. The tracker already singles WinRed out as a conduit (inside
  `other_unclassified`); Democracy Engine could be handled the same way.

## Reviewed list — the 69 committees holding 90% of the shaky money

Shaky = the committee's corporate status changes between cycles, or its name says
association, federation, society, union, fund, council, club or similar while it is coded
corporate (380 committees, $67.3M to roster people over all cycles). "Codes" is the
`ORG_TP` per cycle, oldest first (`-` blank). Each committee's FEC record:
`https://www.fec.gov/data/committee/<id>/`. "Proposed" is a judgement from the connected
organization the committee reports, for Craig to accept or change.

| $ to roster (all cycles) | Committee | Codes | What it is | Proposed |
|---:|---|---|---|---|
| 5,986,247 | C00010470 Union Pacific Corp. Fund For Effective Governmen | `CCCCCCCCCCCCCCCCCCCCCCCC` | Union Pacific Corporation (railroad) | corporate |
| 4,572,100 | C00164145 United Services Automobile Association Employee  | `CCCCCCCCCCCCCCWWWWWWWWW` | USAA, a member-owned financial services and insurance company | corporate |
| 4,455,286 | C00343137 Political Action Committee Of The American Assoc | `TTTTTMCCCCMMMM` | American Association of Orthopaedic Surgeons, a professional association | trade |
| 3,453,800 | C00431361 Teachers Insurance Annuity Association Of Americ | `WWWWWWWWWW` | TIAA, a financial services company | corporate |
| 3,378,000 | C00107235 Pricewaterhousecoopers Political Action Committe | `WMMMMMMMMMMMMMMMMMM--CCC` | PwC, an accounting and consulting firm (partnership) | corporate |
| 2,795,071 | C00186288 Verizon Communications, Inc. Political Action Co | `CCCCCCCCCCCCCCCCCCCCCC` | Verizon Communications Inc. | corporate |
| 2,728,450 | C00131185 Aircraft Owners And Pilots Association Political | `TTTWWWWWWWWWWTMMMMMMMMMM` | Aircraft Owners and Pilots Association, a membership organization | membership |
| 2,620,000 | C00003251 Nea Fund For Children And Public Education | `LLLLLLLLLLLLLLLLLLLLLLCL` | National Education Association, a teachers' union | labor |
| 2,118,060 | C00194746 Bluepac - Blue Cross Blue Shield Association Pac | `CCCCCCCCTTTMCCCCCCCCC` | Blue Cross Blue Shield Association, the national federation of BCBS insurers | trade |
| 1,944,600 | C00094573 Elect - The Pac Of The Alabama Farmers Federatio | `TTTTTTTTTTTTTTCCCCCCCCCC` | Alabama Farmers Federation (state Farm Bureau), a farmers' membership organization | membership |
| 1,890,933 | C00122101 Safari Club International Pac (Sci-Pac) | `CCCCCCCCCCCCCWWWMMMMMMMM` | Safari Club International, a hunters' membership organization | membership |
| 1,810,500 | C00096156 Honeywell International Inc. Technologies Public | `CCCCCCCCCCCCCCCCCCCCCCCC` | Honeywell International Inc. | corporate |
| 1,553,181 | C00104901 Akin Gump Strauss Hauer & Feld Llp Civic Action  | `MWWWWWWWWWWWWWWWWWW-----` | Akin Gump Strauss Hauer & Feld LLP, a law firm | corporate |
| 1,389,232 | C00343459 American College Of Radiology Association Pac | `-TTTMMCCM-----` | American College of Radiology Association, a professional association | trade |
| 1,266,800 | C00375048 Consumer Technology Association Pac | `TTTTTTTTTTCCC` | Consumer Technology Association, a trade association | trade |
| 1,032,000 | C00214148 American Peanut Shellers Association Political A | `TTTTTTTTTTTCCCCCCCCC` | American Peanut Shellers Association, a trade association | trade |
| 936,500 | C00048579 Salt River Valley Water Users' Association Polit | `CCCCCCCCCCCCCCCCCCCCCCCC` | Salt River Valley Water Users' Association (SRP), a landowner-owned water association tied to a public power district | cooperative |
| 776,450 | C00355677 Biotechnology Innovation Organization Pac (Bio P | `CCCCCCCCTTTTTT` | Biotechnology Innovation Organization, a trade association | trade |
| 616,800 | C00087874 Conagra Brands, Inc. Good Government Association | `CCCCCCCCCCCCCCCCCCCCCCCC` | Conagra Brands, Inc. | corporate |
| 594,000 | C00379180 National Association Of Chemical Distributors Re | `TTTTTTTTTTCCC` | National Association of Chemical Distributors, a trade association | trade |
| 582,500 | C00173153 American Association Of Nurse Anesthetists Separ | `TTTTTTTTTTTTMMMCMMMMMM` | American Association of Nurse Anesthetists, a professional association | trade |
| 550,500 | C00219444 National Structured Settlements Trade Associatio | `WWWWWWWWWWTTTTTTTTTT` | National Structured Settlements Trade Association | trade |
| 531,892 | C00151340 Dla Piper Llp (Us) Political Action Committee (D | `CCCCCCCCCCCCCCCCCC-----` | DLA Piper LLP, a law firm | corporate |
| 529,641 | C00171504 Eyepac Political Action Committee For American S | `WWWWWWWWWWWTCMMMM-----` | American Society of Cataract and Refractive Surgery, a professional society | trade |
| 524,350 | C00163048 Cap-Pac Separate Segregated Fund Of The National | `MTTTTTTTTTTTCTWWWWWMMMM` | National Community Action Foundation, a nonprofit network of anti-poverty agencies | membership |
| 508,000 | C00466813 Humane World Action Fund Political Action Commit | `CCMCMMMMM` | Humane Society Legislative Fund (now Humane World Action Fund), an animal-welfare advocacy group | membership |
| 502,745 | C00468314 Democracy Engine, Inc., Pac | `CCCCCCCCC` | Democracy Engine, a payment platform that forwards individuals' earmarked contributions | conduit |
| 488,500 | C00035675 Bristol-Myers Squibb Company Political Action Co | `CCCCCCCCCCCCCCCCCCCCCCCC` | Bristol-Myers Squibb Company | corporate |
| 488,450 | C00149104 Chs Inc. Political Action Committee | `VVVVVVVVVVVCCCCCCCCCCVV` | CHS Inc., a farmer-owned cooperative | cooperative |
| 468,300 | C00012245 Ubs Americas Inc. Political Action Committee (Ub | `CCCCCCCCCCCCCCCCCCCCCCCC` | UBS Americas Inc. | corporate |
| 452,950 | C00080135 Blue Diamond Growers Political Action Committee | `WWWWWWWWWWWWWWWWVVVVVVVV` | Blue Diamond Growers, an almond growers' cooperative | cooperative |
| 443,095 | C00386904 Faegre Drinker Political Action Committee (Faegr | `CCCCCCC-----` | Faegre Drinker, a law firm | corporate |
| 428,986 | C00021295 Bracepac | `CCCCCCCCCCCCCCCCCCC-----` | Bracewell LLP, a law firm | corporate |
| 417,000 | C00014878 General Aviation Manufacturers Association Polit | `TTTTTTTTTTTTTTTTTTTTCCTT` | General Aviation Manufacturers Association, a trade association | trade |
| 400,500 | C00410407 Edj Holding Company, Inc. Political Action Commi | `----------C` | EDJ Holding Company (Edward Jones), a brokerage | corporate |
| 361,000 | C00161570 American Public Power Association, Public Owners | `TTTTTTTTTTTTTTTTTTTCCCT` | American Public Power Association, the trade association of public power utilities | trade |
| 348,500 | C00109819 Coalpac, A Political Action Committee Of The Nat | `TTTTTTTTTTTCCCCTTTTTTTTT` | National Mining Association, a trade association | trade |
| 339,100 | C00084061 Blue Cross Blue Shield Of Michigan Pac | `WWWWWWWWWWWWWTMMMMMMMMMM` | Blue Cross Blue Shield of Michigan, a health insurer | corporate |
| 321,000 | C00233304 Commercial Real Estate Development Pac (Creda Pa | `TMTTTTTTTTTTTTTCCCCT` | NAIOP, the Commercial Real Estate Development Association | trade |
| 319,250 | C00387878 Energysolutions, Inc. Fund For Effective Governm | `CCCCCCCCCCCC` | EnergySolutions, Inc. | corporate |
| 299,250 | C00393520 Federal National Mortgage Association Political  | `CCCC` | Fannie Mae, a government-sponsored mortgage company | corporate |
| 294,103 | C00034827 Eaton Corporation Public Policy Association | `CCCCCCCCCCCCCCCCCCCCCCCC` | Eaton Corporation | corporate |
| 281,500 | C00349746 California Dairies, Inc. Federal Political Actio | `CCCCCCVVVVVVVV` | California Dairies, Inc., a dairy farmers' cooperative | cooperative |
| 263,000 | C00408260 The Grant Thornton Advisors Llc Political Action | `----------CC` | Grant Thornton Advisors LLC, an accounting firm | corporate |
| 251,450 | C00101766 United Airlines, Inc. Political Action Committee | `CCCCCCCCCCCCCCCCCCCCCCCC` | United Airlines, Inc. | corporate |
| 245,071 | C00314617 Planned Parenthood Action Fund Inc Pac, Dba Plan | `CCCCCTMMMMMMMMMM` | Planned Parenthood Action Fund, a nonprofit advocacy organization | membership |
| 237,250 | C00313700 Transunion Political Action Committee (Tu Pac) | `CCCCCCCCCCCCCCCC` | TransUnion LLC, a credit bureau | corporate |
| 226,430 | C00151019 National Farmers Union Pac | `WWWCCCCCCCCCCCCCMMMMMMM` | National Farmers Union, a farmers' membership organization | membership |
| 216,799 | C00328401 The Lincoln Club Of Orange County Federal Pac | `CCCCCCCMMM-----` | The Lincoln Club of Orange County, a conservative political club | membership |
| 214,500 | C00114702 Ocean Spray Cranberries Inc. Political Action Co | `CCCCCCCCCCCCCCCCCCCCCVVV` | Ocean Spray Cranberries, a growers' cooperative | cooperative |
| 205,499 | C00383976 Friends Of Community Oncology Pac | `-------CCC---` | Community Oncology Alliance, a professional association | trade |
| 205,400 | C00204008 National Funeral Directors Association Of The Un | `TTTTTTTTWWWWMMMMMMMMM` | National Funeral Directors Association, a trade association | trade |
| 183,000 | C00148882 Lincoln Club Of Northern California Federal Pac | `MMMMMMMMMMMMMMCCCCCCCCC` | Lincoln Club of Northern California, a conservative political club | membership |
| 181,250 | C00130658 Cpac Action Pac | `WWWWWWWWWWWTTTTMMMMMM--M` | American Conservative Union (CPAC), an ideological organization | membership |
| 179,000 | C00558700 Rothman Institute Pac | `CCCCCCC` | Rothman Institute, an orthopedic medical practice | corporate |
| 178,000 | C00035535 Consumer Bankers Association Pac | `TTTTTTTTTTTTTTTTTTTTTTTC` | Consumer Bankers Association, a trade association | trade |
| 177,000 | C00497545 Concorde Career Colleges And Universal Technical | `--CCCCCC` | Universal Technical Institute / Concorde Career Colleges, for-profit schools | corporate |
| 167,500 | C00004952 Electric Cooperatives Of Mississippi Action Comm | `TTTTTTTTTTTTTCCCCCCCCCCC` | Electric Cooperatives of Mississippi, an association of electric cooperatives | cooperative |
| 167,000 | C00237065 American Cement Association (Cement Pac) | `TTTTTTTTTTTTMTTCTTT` | Portland Cement Association, a trade association | trade |
| 166,750 | C00096362 Michigan Farm Bureau Political Action Committee | `WWWWWWWWWWWWWWMMMMM-----` | Michigan Farm Bureau, a farmers' membership organization | membership |
| 164,000 | C00273003 American Association Of Clinical Urologists Pac  | `TTTTTTTTCTTTMMMMMM` | American Association of Clinical Urologists, a professional association | trade |
| 159,500 | C00032607 Pinnacle Financial Partners, Inc. Fund For Effec | `CCCCCCCCCCCCCCCCCCCCCCCC` | Pinnacle Financial Partners, a bank | corporate |
| 158,416 | C00185686 South Texas Sugar Cane Producers Pac Rio Grande  | `CCCCCCCCCCCCCCVVVVVVV` | Rio Grande Valley Sugar Growers, a growers' cooperative | cooperative |
| 154,800 | C00076588 Cf Industries, Inc. Employees' Good Government F | `VVVVVVVVVVVVCCCCCCCCCCCC` | CF Industries, Inc. | corporate |
| 152,000 | C00079681 National Propane Gas Association Pac | `TTTTTTTTTTTTCCCTTTTTTTTT` | National Propane Gas Association, a trade association | trade |
| 150,147 | C00110197 Dickstein Shapiro Llp Pac | `MMMMMMMMMMMMMCCCCCC` | Dickstein Shapiro LLP, a law firm | corporate |
| 149,500 | C00304634 Minepac, A Political Action Committee Of The Nat | `TTTCCCCTTTTTTTTT` | National Mining Association, a trade association | trade |
| 146,500 | C00161604 Cooperative Of American Physicians Federal Polit | `VVVVVVVVVVTTTMMMCCCCCCC` | Cooperative of American Physicians, a physician-owned cooperative | cooperative |
| 144,000 | C00571042 Motorsports Acceptance Corporation Political Act | `----CCC` | Motorsports Acceptance Corporation, a finance company | corporate |

## What the proposed classes would move

```
moves INTO corporate: $9,207,313.00 from 12 committees
   $4,224,125.00  PwC, an accounting and consulting firm (partnership)
   $1,553,181.00  Akin Gump Strauss Hauer & Feld LLP, a law firm
   $1,044,550.00  Grant Thornton Advisors LLC, an accounting firm
   $  531,892.00  DLA Piper LLP, a law firm
   $  483,650.00  EDJ Holding Company (Edward Jones), a brokerage
   $  443,095.00  Faegre Drinker, a law firm
   $  428,986.00  Bracewell LLP, a law firm
   $  339,100.00  Blue Cross Blue Shield of Michigan, a health insurer
moves OUT of corporate: $15,315,309.00 from 42 committees
   $2,227,643.00  American Association of Orthopaedic Surgeons, a professional association
   $1,907,510.00  Blue Cross Blue Shield Association, the national federation of BCBS insurers
   $1,310,000.00  National Education Association, a teachers' union
   $  972,300.00  Alabama Farmers Federation (state Farm Bureau), a farmers' membership organization
   $  936,750.00  Salt River Valley Water Users' Association (SRP), a landowner-owned water association tied to a public power district
   $  694,616.00  American College of Radiology Association, a professional association
   $  633,400.00  Consumer Technology Association, a trade association
   $  524,350.00  National Community Action Foundation, a nonprofit network of anti-poverty agencies
   $  516,000.00  American Peanut Shellers Association, a trade association
   $  502,745.00  Democracy Engine, a payment platform that forwards individuals' earmarked contributions

incoming members whose 2026 dirty/clean flips: 4
   ('Bob Brooks', 'House', 19129.0, 0.0)
   ('Kimberlyn King-Hinds', 'House', 0.0, 2000.0)
   ('Edward J. Markey', 'Senate', -1000.0, 2000.0)
   ('Jon Ossoff', 'Senate', 5250.0, 0.0)
2026 dirty money changes for 365 people
```

Classes outside corporate never count as dirty money; moving a committee between trade,
membership, labor and cooperative changes only the other-committee breakdown.

## Sources

- FEC committee master files (`cm`), every cycle 1980–2026, snapshot `fec-bulk-2026-11-22`.
- Democracy Engine: [Democracy Engine — InfluenceWatch](https://www.influencewatch.org/for-profit/democracy-engine/),
  [Business Groups Sidestep Unpopular PACs With New Giving Avenue — Bloomberg Government](https://about.bgov.com/insights/news/business-groups-sidestep-unpopular-pacs-with-new-giving-avenue/),
  [FEC Advisory Opinion 2022-03](https://beta.fec.gov/files/legal/aos/2022-03/2022-03.pdf).
- Salt River Valley Water Users' Association: [Salt River Project — Wikipedia](https://en.wikipedia.org/wiki/Salt_River_Project), [About SRP](https://srpnet.com/about/about-srp).
- Lincoln Club of Orange County: [The Markup](https://themarkup.org/election-2026/2026/03/09/it-was-john-waynes-political-club-now-its-spending-millions-on-online-influence), [FEC committee C00328401](https://www.fec.gov/data/committee/C00328401/).
