"""Other-committee diagnostics: what each file held, what was left out, and weball col 26."""

from receipts.common.files import write_json
from receipts.common.settings import settings
from receipts.domain.committee_classes import OTHER_COMMITTEE_CLASSES, CommitteeClass
from receipts.domain.money import ZERO, Money
from receipts.domain.roster import candidate_ids
from receipts.store.read import for_candidates

BUCKETS = [c.value for c in OTHER_COMMITTEE_CLASSES]

AIPAC = CommitteeClass.AIPAC.value

CORPORATE = CommitteeClass.CORPORATE.value

WINRED_COLUMN = 'winred'


def earmark(column):
    return f'{column}_earmark'


def weball_other_committee_money(db, cycle, roster_ids):
    return {
        candidate_id: Money(cents)
        for candidate_id, cents in for_candidates(
            db,
            'SELECT candidate_id, other_committee_contributions_cents FROM candidate_summaries '
            'WHERE cycle = ?',
            roster_ids,
            cycle,
        )
    }


def roster_total(roster, ledger, column):
    return Money.total(
        ledger.total(candidate_ids(p), settings().cycles.career, column) for p in roster.people
    )


DEDUP_FINDING = (
    'dedup-applied.json corrects the WEBALL double-count (identical '
    "TTL_INDIV_CONTRIB repeated under a chamber-switcher's House and "
    'Senate IDs). It does NOT change any pas2-derived column in this '
    'script: pas2 is transaction-level, so per-ID amounts differ and '
    'there is no duplicate copy to drop — the same finding '
    'the double-count record notes for AIPAC/corporate. It DOES affect the '
    'weball side of the reconciliation: col 26 (OTHER_POL_CMTE_CONTRIB) '
    'is duplicated under both IDs the same way, so the reconciliation '
    "zeroes the dropped IDs' col-26 copies (guarded by the same "
    'equality check the weball correction uses) and reports raw vs corrected '
    'residuals separately. No correction was invented for these columns.'
)


def unclassified_composition(rows, cycle=None):
    composition = {}
    for _candidate, row_cycle, column, kind, amount, _earmarked in rows:
        if column == CommitteeClass.UNCLASSIFIED.value and cycle in (None, row_cycle):
            composition[kind] = composition.get(kind, 0) + amount
    return dict(sorted(composition.items()))


FILE_READS = 'SELECT rows_read FROM files_read WHERE file = ? AND cycle = ?'


EXCLUDED = """
    SELECT count(*), COALESCE(SUM(amount_cents), 0), count(DISTINCT committee_id)
    FROM committee_contributions AS money
    WHERE cycle = ? AND {condition}"""


REGISTERED = (
    'EXISTS (SELECT 1 FROM committees AS registry '
    'WHERE registry.committee_id = money.committee_id AND registry.cycle = money.cycle)'
)


def cycle_diagnostics(db, cycle, roster_ids, ledger, rows):
    def excluded(condition):
        return for_candidates(db, EXCLUDED.format(condition=condition), roster_ids, cycle)[0]

    (cm_rows,) = db.execute(FILE_READS, ['cm', cycle]).fetchone()
    (pas2_rows,) = db.execute(FILE_READS, ['pas2', cycle]).fetchone()
    matched = excluded('TRUE')[0]
    voided_rows, voided_cents, _ = excluded("excluded_because = 'voided_earmark'")
    unregistered_rows, _, unregistered_committees = excluded(
        f"excluded_because IS DISTINCT FROM 'voided_earmark' AND NOT {REGISTERED}"
    )
    dropped_rows, dropped_cents, _ = excluded(
        f"excluded_because = 'reported_again' AND {REGISTERED}"
    )

    def kept(column):
        return Money.total(ledger.amount(c, cycle, column) for c in ledger.candidates_in(cycle))

    return {
        'cycle': cycle,
        'cm_rows': cm_rows,
        'pas2_rows': pas2_rows,
        'pas2_matched_roster': matched,
        'cm_missing_committees': unregistered_committees,
        'cm_missing_rows': unregistered_rows,
        'dedup_dropped_rows': dropped_rows,
        'dedup_dropped_cents': dropped_cents,
        'void_earmark_rows': voided_rows,
        'void_earmark_cents': voided_cents,
        'kept_cents': {bucket: kept(bucket).cents for bucket in BUCKETS},
        'kept_earmark_cents': {
            bucket: kept(earmark(bucket)).cents for bucket in BUCKETS if kept(earmark(bucket))
        },
        'kept_winred_cents': kept(WINRED_COLUMN).cents,
        'kept_corporate_cents': kept(CORPORATE).cents,
        'kept_corporate_earmark_cents': kept(earmark(CORPORATE)).cents,
        'kept_aipac_cents': kept(AIPAC).cents,
        'kept_aipac_earmark_cents': kept(earmark(AIPAC)).cents,
        'unclassified_composition_cents': unclassified_composition(rows, cycle),
    }


def without_double_counted_summaries(reported, dedup_records, cycle):
    """Zero the copies weball repeats under a chamber-switcher's second ID."""
    corrected, zeroed, mismatched = dict(reported), 0, 0
    for record in dedup_records:
        if record['cycle'] != cycle:
            continue
        for dropped_id in record['dropped_ids']:
            if dropped_id in corrected and record['kept_id'] in corrected:
                if corrected[dropped_id] == corrected[record['kept_id']]:
                    corrected[dropped_id] = ZERO
                    zeroed += 1
                else:
                    mismatched += 1
    return corrected, zeroed, mismatched


PARTY = CommitteeClass.PARTY.value


COL_26_COLUMNS = [b for b in BUCKETS if b != PARTY] + [CORPORATE, AIPAC]


def pas2_comparable(ledger, candidate_id, cycle):
    """What weball col 26 covers: committee money other than party (Form 3 line 11(c))."""
    columns = COL_26_COLUMNS
    gross = Money.total(ledger.amount(candidate_id, cycle, c) for c in columns)
    earmarked = Money.total(ledger.amount(candidate_id, cycle, earmark(c)) for c in columns)
    return gross, earmarked


def comparison_row(candidate_id, raw, corrected, ledger, cycle):
    gross, earmarked = pas2_comparable(ledger, candidate_id, cycle)
    return {
        'candidate_id': candidate_id,
        'raw': raw.get(candidate_id, ZERO).cents,
        'corrected': corrected.get(candidate_id, ZERO).cents,
        'gross': gross.cents,
        'earmarked': earmarked.cents,
        'net': gross.cents - earmarked.cents,
        'party': ledger.amount(candidate_id, cycle, PARTY).cents,
    }


def largest_residuals(rows, reverse):
    ranked = sorted(
        rows, key=lambda r: (r['corrected'] - r['net'], r['candidate_id']), reverse=reverse
    )
    return [
        {
            'candidate_id': r['candidate_id'],
            'residual_cents': r['corrected'] - r['net'],
            'weball_corrected_cents': r['corrected'],
            'pas2_net_cents': r['net'],
        }
        for r in ranked[:5]
    ]


def reconcile_cycle(db, cycle, roster_ids, ledger, dedup_records):
    """Weball col 26 against the pas2 money it covers, raw and with double counts zeroed."""
    raw = weball_other_committee_money(db, cycle, roster_ids)
    corrected, zeroed, mismatched = without_double_counted_summaries(raw, dedup_records, cycle)
    rows = [
        comparison_row(c, raw, corrected, ledger, cycle)
        for c in set(raw) | ledger.candidates_in(cycle)
    ]
    considered = [r for r in rows if r['raw'] or r['gross']]

    def total(key):
        return sum(r[key] for r in rows)

    def residual(weball, pas2):
        return sum(r[weball] - r[pas2] for r in considered)

    def exact(weball, pas2):
        return sum(r[weball] == r[pas2] for r in considered)

    return {
        'cycle': cycle,
        'candidates_with_weball_or_pas2': len(considered),
        'weball_other_pol_total_cents': Money.total(raw.values()).cents,
        'weball_corrected_total_cents': Money.total(corrected.values()).cents,
        'pas2_nonparty_gross_cents': total('gross'),
        'pas2_nonparty_net_of_earmarks_cents': total('gross') - total('earmarked'),
        'pas2_earmark_transmitted_cents': total('earmarked'),
        'pas2_party_committees_cents': total('party'),
        'residual_weball_raw_minus_pas2_gross_cents': residual('raw', 'gross'),
        'residual_weball_corrected_minus_pas2_gross_cents': residual('corrected', 'gross'),
        'residual_weball_corrected_minus_pas2_net_cents': residual('corrected', 'net'),
        'exact_matches_raw': exact('raw', 'gross'),
        'exact_matches_corrected': exact('corrected', 'gross'),
        'exact_matches_corrected_net': exact('corrected', 'net'),
        'dedup_dropped_ids_zeroed': zeroed,
        'dedup_dropped_ids_col26_mismatch': mismatched,
        'largest_positive_residuals': largest_residuals(considered, reverse=True),
        'largest_negative_residuals': largest_residuals(considered, reverse=False),
    }


def write_diagnostics(roster, ledger, rows, diagnostics, reconciliation, lamb, checks):
    write_json(
        settings().paths.other_committees_diagnostics,
        {
            'per_cycle': diagnostics,
            'unclassified_composition_career_cents': unclassified_composition(rows),
            'roster_totals_cents': {b: roster_total(roster, ledger, b).cents for b in BUCKETS},
            'roster_earmark_transmitted_cents': {
                b: roster_total(roster, ledger, earmark(b)).cents for b in BUCKETS
            },
            'roster_winred_included_cents': ledger.column_total(WINRED_COLUMN).cents,
            'cross_checks_vs_methodology': {
                column: {'recomputed_cents': a, 'methodology_cents': b, 'match': a == b}
                for column, (a, b) in checks.items()
            },
            'reconciliation_vs_weball_col26': reconciliation,
            'lamb_validation': lamb,
            'dedup_applied_finding': DEDUP_FINDING,
        },
    )
