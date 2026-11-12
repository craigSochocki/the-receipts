# FEC bulk data — download inventory

**Staged:** Thu Nov 12, 2026 (downloads 12:13–12:19 UTC; extraction + verification 12:19–12:35 UTC).
**Location:** `data/raw/` (zips + extracted `.txt` side by side; `work/bulk/` before the Nov 12, 2026 restructure).
**Source doc:** `research/fec-sources.md` (verified Nov 12, 2026).
**Download method:** `curl -L --fail --retry 3 --retry-delay 5 -C -` per file from
`https://www.fec.gov/files/bulk-downloads/<cycle>/<file><YY>.zip`. Zero failures, zero retries
needed. `weball26.zip` and `cm26.zip` were copied from the verification agent's samples already staged on the VM (sizes match the doc exactly: 200,004 and 880,749 bytes); the other 82 files were downloaded.

## Totals

| File type | Cycles | Zip files | Zipped bytes | Extracted rows (wc -l) |
|---|---:|---:|---:|---:|
| weball (candidate summaries) | 1980–2026 (24) | 24 | 3,047,205 | 70,381 |
| cm (committee master) | 1980–2026 (24) | 24 | 13,397,117 | 298,679 |
| pas2 (committee → candidate contributions) | 1980–2026 (24) | 24 | 248,417,964 | 7,879,684 |
| oppexp (see ⚠️ warning below) | 2004–2026 (12) | 12 | 573,105,624 | 19,858,782 |
| **Total** | | **84** | **837,967,910 (~838 MB)** | **28,107,526** |

Total on disk (zips + extracted txt): 5,947,214,460 bytes (~5.9 GB; extracted .txt alone
5,109,246,550 bytes, ~5.1 GB).
Nothing missing, nothing failed, nothing corrupt: all 84 zips downloaded (82 OK + 2 pre-existing
samples skipped) and all 84 extracted with `unzip` exit code 0.

## Layout note — per-cycle subfolders for cm / pas2 / oppexp

`weballYY.zip` contains a per-cycle-named file (`weballYY.txt`), so those extract flat into
`data/raw/weball/`. But `cmYY.zip`, `pas2YY.zip`, and `oppexpYY.zip` all contain a single
generic-named file (`cm.txt`, `itpas2.txt`, `oppexp.txt`). Extracting them flat would overwrite
every cycle except the last — this happened on the first extraction pass and was caught by the
file count (only 3 `.txt` files for those three types). They were re-extracted into per-cycle
subfolders, so the pull agent should glob:

- `data/raw/weball/weballYY.txt`
- `data/raw/cm/<cycle>/cm.txt` (e.g. `data/raw/cm/2024/cm.txt`)
- `data/raw/pas2/<cycle>/itpas2.txt`
- `data/raw/oppexp/<cycle>/oppexp.txt`

## ⚠️ CRITICAL CORRECTION — `oppexp` is NOT independent expenditures

`fec-sources.md` §4 labels `oppexp` as "Independent expenditures (Schedule E)" with columns
`SPE_ID / CAN_ID / SUP_OPP / EXP_AMO`. **That is wrong, and the downloaded content proves it:**

- The extracted `oppexp.txt` files have **26 columns** and contain F3/F3X/F3P **Schedule B
  disbursements**: col 1 = committee ID, col 2 = amendment indicator (N/A/T), col 6 =
  transaction type (`17`, `21`, `21B`, `23` — e.g. 2024: 1,141,106× `17`, 904,689× `21B`,
  204,070× `23`, 47× `21`), col 7 = form type, col 9 = payee name, col 13 = date, col 14 =
  amount, col 16 = purpose, col 19 = memo code (X/Y). There is **no candidate-ID column, no
  SUP_OPP column, and no EXP_AMO column**.
- `grep` for UDP (`C00799031`) in 2022/2024/2026 oppexp returns 140 / 390 / 380 rows — but
  they are UDP's **operating expenditures** (payees "UBER TECHNOLOGIES INC", "FIRST NATIONAL
  BANK OF OMAHA", purposes TRAVEL / CREDIT CARD PAYMENT), not independent expenditures.
- `grep` for El-Sayed's candidate ID `S6MI00418` (the candidate in UDP's 2024 Schedule E API
  response) returns **0 rows** in oppexp 2022, 2024, and 2026.
- Corroboration: the FEC's own independent-expenditures file description
  (fetched Nov 12, 2026) lists 23 columns starting `CAN_ID, CAN_NAM, SPE_ID, SPE_NAM,
  ELE_TYP, …, EXP_AMO, …, SUP_OPP, PUR, PAY, …` — none of which matches the downloaded
  files; and a Sunlight/IRE guide to FEC master files states "the FEC recently added a weekly
  master file (oppexp) listing committees' operating expenditures, which are found on
  Schedule B."

**Consequence for the pull agent: UDP independent expenditures are NOT in these files.**
Do not sum `oppexp` for UDP support/oppose. The verified route for UDP Schedule E is the
OpenFEC API `/v1/schedules/schedule_e/?committee_id=C00799031` (verified working Nov 12:
1,269 rows for 2024; needs a registered api.data.gov key — DEMO_KEY is ~30 req/hr shared).
The 573 MB of oppexp files are valid FEC operating-expenditure data, staged and inventoried
below, but they do not serve any of the tracker's four money types as scoped. Whether to keep
or delete them is a coordinator decision; they are retained for now.

## Column spot-checks (measured Nov 12, 2026)

- **weball** — 30 columns. Per the FEC all-candidates file description (fetched Nov 12):
  `TTL_INDIV_CONTRIB` = col 18, `OTHER_POL_CMTE_CONTRIB` = col 26, `TTL_RECEIPTS` = col 6,
  `CVG_END_DT` = col 28, `INDIV_REFUNDS` = col 29, `CMTE_REFUNDS` = col 30. Confirmed on
  `weball26.txt` row 2 (Peltola): col 18 = 63252.17, col 19 = AK, col 20 = 00, col 28 =
  02/13/2026. ⚠️ Small correction to `fec-sources.md`: its sample annotation says row 1
  (Constant, H2AK00200) has `TTL_INDIV_CONTRIB` = 143,180.09 in col 18. Measured: col 17 =
  143180.09 (that is `DEBTS_OWED_BY` per the FEC layout) and col 18 = 0. The doc's column
  number (18) is right; the sample value was attached to the wrong column.
- **cm** — 15 columns. `CMTE_ID` col 1, `CMTE_TP` col 10, `ORG_TP` col 13. Confirmed on
  `cm/2026/cm.txt`: `C00797670|…|B|Q||M|M||` (CMTE_TP=Q, ORG_TP=M).
- **pas2** — 22 columns. `CMTE_ID` col 1, `TRANSACTION_TP` col 6, `TRANSACTION_AMT` col 15,
  `CAND_ID` col 17. Confirmed on `pas2/2024/itpas2.txt` row 1: `C00777706|…|24K|…|5000|…|S4WV00159`.
- **oppexp** — 26 columns, Schedule B disbursement layout (see warning above). Do not use the
  `SPE_ID / CAN_ID / SUP_OPP / EXP_AMO` column map from `fec-sources.md` §4 for these files.

## Smoke tests — target committees

- **Committee master:** `C00797670` (AIPAC PAC) and `C00799031` (UDP) each appear exactly once
  in `cm/2022/cm.txt`, `cm/2024/cm.txt`, and `cm/2026/cm.txt`, and **zero times in every
  cycle 1980–2020** — consistent with first filings Dec 2021 / Jan 2022.
- **AIPAC PAC in pas2** (`CMTE_ID = C00797670`, `grep -c '^C00797670|'`):
  2022: **943** rows; 2024: **1,933** rows; 2026: **1,311** rows; total **4,187** rows.
  Transaction types across the three cycles: 4,185× `24K`, 2× `24Z`.
  Smoke-only amount check (NOT a publishable total — no dedup, no memo/refund handling):
  sum of `TRANSACTION_AMT` (col 15) for AIPAC 2024 = **$2,455,814**.
- **UDP in oppexp:** 140 / 390 / 380 rows (2022/2024/2026) — operating expenditures only,
  see warning above. No UDP independent-expenditure data is staged.

## Per-file inventory


### cm

| Zip file | Zip bytes | Extracted .txt | Txt bytes | Rows (wc -l) |
|---|---|---|---|---|
| `cm/cm00.zip` | 448,764 | `cm/2000/cm.txt` | 1,279,675 | 9,577 |
| `cm/cm02.zip` | 445,668 | `cm/2002/cm.txt` | 1,221,313 | 9,103 |
| `cm/cm04.zip` | 465,679 | `cm/2004/cm.txt` | 1,248,880 | 9,322 |
| `cm/cm06.zip` | 469,614 | `cm/2006/cm.txt` | 1,248,670 | 9,282 |
| `cm/cm08.zip` | 504,959 | `cm/2008/cm.txt` | 1,330,985 | 10,017 |
| `cm/cm10.zip` | 512,207 | `cm/2010/cm.txt` | 1,476,123 | 11,138 |
| `cm/cm12.zip` | 608,802 | `cm/2012/cm.txt` | 1,790,053 | 14,455 |
| `cm/cm14.zip` | 624,425 | `cm/2014/cm.txt` | 1,824,091 | 14,905 |
| `cm/cm16.zip` | 732,154 | `cm/2016/cm.txt` | 2,153,204 | 17,651 |
| `cm/cm18.zip` | 809,262 | `cm/2018/cm.txt` | 2,256,629 | 19,022 |
| `cm/cm20.zip` | 782,585 | `cm/2020/cm.txt` | 2,206,934 | 18,286 |
| `cm/cm22.zip` | 838,217 | `cm/2022/cm.txt` | 2,376,160 | 19,792 |
| `cm/cm24.zip` | 883,375 | `cm/2024/cm.txt` | 2,500,592 | 20,937 |
| `cm/cm26.zip` | 880,749 | `cm/2026/cm.txt` | 2,520,251 | 21,057 |
| `cm/cm80.zip` | 359,492 | `cm/1980/cm.txt` | 1,039,292 | 7,884 |
| `cm/cm82.zip` | 383,479 | `cm/1982/cm.txt` | 1,112,048 | 8,291 |
| `cm/cm84.zip` | 393,423 | `cm/1984/cm.txt` | 1,151,997 | 8,465 |
| `cm/cm86.zip` | 399,304 | `cm/1986/cm.txt` | 1,168,760 | 8,518 |
| `cm/cm88.zip` | 431,553 | `cm/1988/cm.txt` | 1,260,064 | 9,218 |
| `cm/cm90.zip` | 431,588 | `cm/1990/cm.txt` | 1,256,310 | 9,134 |
| `cm/cm92.zip` | 502,548 | `cm/1992/cm.txt` | 1,442,071 | 10,759 |
| `cm/cm94.zip` | 505,698 | `cm/1994/cm.txt` | 1,440,537 | 10,815 |
| `cm/cm96.zip` | 517,003 | `cm/1996/cm.txt` | 1,466,566 | 11,075 |
| `cm/cm98.zip` | 466,569 | `cm/1998/cm.txt` | 1,335,938 | 9,976 |

### oppexp

| Zip file | Zip bytes | Extracted .txt | Txt bytes | Rows (wc -l) |
|---|---|---|---|---|
| `oppexp/oppexp04.zip` | 25,734,364 | `oppexp/2004/oppexp.txt` | 168,173,606 | 954,706 |
| `oppexp/oppexp06.zip` | 30,217,068 | `oppexp/2006/oppexp.txt` | 196,090,957 | 1,104,753 |
| `oppexp/oppexp08.zip` | 43,785,331 | `oppexp/2008/oppexp.txt` | 289,573,859 | 1,639,878 |
| `oppexp/oppexp10.zip` | 37,478,492 | `oppexp/2010/oppexp.txt` | 242,359,398 | 1,339,329 |
| `oppexp/oppexp12.zip` | 45,382,905 | `oppexp/2012/oppexp.txt` | 299,958,848 | 1,656,089 |
| `oppexp/oppexp14.zip` | 38,894,605 | `oppexp/2014/oppexp.txt` | 249,571,328 | 1,351,071 |
| `oppexp/oppexp16.zip` | 51,856,704 | `oppexp/2016/oppexp.txt` | 329,929,014 | 1,744,187 |
| `oppexp/oppexp18.zip` | 52,731,735 | `oppexp/2018/oppexp.txt` | 343,941,837 | 1,800,080 |
| `oppexp/oppexp20.zip` | 64,556,004 | `oppexp/2020/oppexp.txt` | 436,137,842 | 2,310,524 |
| `oppexp/oppexp22.zip` | 61,909,594 | `oppexp/2022/oppexp.txt` | 376,665,034 | 1,962,279 |
| `oppexp/oppexp24.zip` | 67,913,840 | `oppexp/2024/oppexp.txt` | 429,583,034 | 2,249,912 |
| `oppexp/oppexp26.zip` | 52,644,982 | `oppexp/2026/oppexp.txt` | 335,560,739 | 1,745,974 |

### pas2

| Zip file | Zip bytes | Extracted .txt | Txt bytes | Rows (wc -l) |
|---|---|---|---|---|
| `pas2/pas200.zip` | 7,810,034 | `pas2/2000/itpas2.txt` | 41,810,658 | 247,340 |
| `pas2/pas202.zip` | 8,277,293 | `pas2/2002/itpas2.txt` | 40,932,103 | 237,106 |
| `pas2/pas204.zip` | 8,093,031 | `pas2/2004/itpas2.txt` | 37,889,491 | 245,668 |
| `pas2/pas206.zip` | 9,107,274 | `pas2/2006/itpas2.txt` | 42,133,670 | 266,703 |
| `pas2/pas208.zip` | 10,318,415 | `pas2/2008/itpas2.txt` | 49,624,916 | 305,735 |
| `pas2/pas210.zip` | 10,947,926 | `pas2/2010/itpas2.txt` | 51,654,496 | 325,095 |
| `pas2/pas212.zip` | 12,328,281 | `pas2/2012/itpas2.txt` | 63,583,038 | 395,069 |
| `pas2/pas214.zip` | 11,947,422 | `pas2/2014/itpas2.txt` | 56,158,056 | 350,272 |
| `pas2/pas216.zip` | 15,450,184 | `pas2/2016/itpas2.txt` | 86,837,811 | 516,385 |
| `pas2/pas218.zip` | 12,556,308 | `pas2/2018/itpas2.txt` | 60,392,609 | 349,820 |
| `pas2/pas220.zip` | 28,978,598 | `pas2/2020/itpas2.txt` | 158,316,082 | 887,829 |
| `pas2/pas222.zip` | 25,588,555 | `pas2/2022/itpas2.txt` | 130,910,515 | 749,163 |
| `pas2/pas224.zip` | 24,678,487 | `pas2/2024/itpas2.txt` | 122,359,279 | 703,163 |
| `pas2/pas226.zip` | 9,165,919 | `pas2/2026/itpas2.txt` | 41,677,716 | 239,201 |
| `pas2/pas280.zip` | 3,935,442 | `pas2/1980/itpas2.txt` | 22,272,324 | 132,147 |
| `pas2/pas282.zip` | 5,078,054 | `pas2/1982/itpas2.txt` | 28,738,063 | 167,410 |
| `pas2/pas284.zip` | 5,967,971 | `pas2/1984/itpas2.txt` | 33,717,911 | 198,674 |
| `pas2/pas286.zip` | 4,582,818 | `pas2/1986/itpas2.txt` | 40,935,659 | 213,355 |
| `pas2/pas288.zip` | 4,717,525 | `pas2/1988/itpas2.txt` | 42,025,556 | 214,008 |
| `pas2/pas290.zip` | 4,458,886 | `pas2/1990/itpas2.txt` | 39,983,656 | 199,434 |
| `pas2/pas292.zip` | 5,002,001 | `pas2/1992/itpas2.txt` | 45,120,096 | 228,783 |
| `pas2/pas294.zip` | 6,937,647 | `pas2/1994/itpas2.txt` | 38,787,959 | 227,032 |
| `pas2/pas296.zip` | 5,432,149 | `pas2/1996/itpas2.txt` | 49,632,546 | 250,679 |
| `pas2/pas298.zip` | 7,057,744 | `pas2/1998/itpas2.txt` | 39,568,566 | 229,613 |

### weball

| Zip file | Zip bytes | Extracted .txt | Txt bytes | Rows (wc -l) |
|---|---|---|---|---|
| `weball/weball00.zip` | 107,797 | `weball/weball00.txt` | 304,623 | 2,604 |
| `weball/weball02.zip` | 112,278 | `weball/weball02.txt` | 303,375 | 2,445 |
| `weball/weball04.zip` | 114,547 | `weball/weball04.txt` | 308,777 | 2,468 |
| `weball/weball06.zip` | 114,900 | `weball/weball06.txt` | 306,324 | 2,410 |
| `weball/weball08.zip` | 123,944 | `weball/weball08.txt` | 331,200 | 2,600 |
| `weball/weball10.zip` | 149,485 | `weball/weball10.txt` | 402,776 | 3,173 |
| `weball/weball12.zip` | 151,707 | `weball/weball12.txt` | 411,156 | 3,272 |
| `weball/weball14.zip` | 135,851 | `weball/weball14.txt` | 371,667 | 2,989 |
| `weball/weball16.zip` | 132,259 | `weball/weball16.txt` | 361,800 | 2,904 |
| `weball/weball18.zip` | 171,196 | `weball/weball18.txt` | 466,301 | 3,687 |
| `weball/weball20.zip` | 183,085 | `weball/weball20.txt` | 502,998 | 3,979 |
| `weball/weball22.zip` | 190,724 | `weball/weball22.txt` | 526,028 | 4,153 |
| `weball/weball24.zip` | 174,296 | `weball/weball24.txt` | 485,783 | 3,857 |
| `weball/weball26.zip` | 200,004 | `weball/weball26.txt` | 555,025 | 4,372 |
| `weball/weball80.zip` | 67,922 | `weball/weball80.txt` | 253,885 | 2,523 |
| `weball/weball82.zip` | 62,655 | `weball/weball82.txt` | 235,060 | 2,331 |
| `weball/weball84.zip` | 85,472 | `weball/weball84.txt` | 250,418 | 2,209 |
| `weball/weball86.zip` | 84,167 | `weball/weball86.txt` | 242,870 | 2,114 |
| `weball/weball88.zip` | 97,882 | `weball/weball88.txt` | 269,977 | 2,283 |
| `weball/weball90.zip` | 93,572 | `weball/weball90.txt` | 259,707 | 2,213 |
| `weball/weball92.zip` | 128,393 | `weball/weball92.txt` | 356,249 | 3,016 |
| `weball/weball94.zip` | 128,733 | `weball/weball94.txt` | 361,998 | 3,103 |
| `weball/weball96.zip` | 127,676 | `weball/weball96.txt` | 356,796 | 3,045 |
| `weball/weball98.zip` | 108,660 | `weball/weball98.txt` | 306,342 | 2,631 |

