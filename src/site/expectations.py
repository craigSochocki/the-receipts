"""What the site should show, computed from the embedded dataset in Python.

The site's figures are rendered by JavaScript from the dataset embedded
in the page. Both site checkers need an independent statement of what
those figures should be:

- `verify_site.py` pins each section against the committed baseline
  (`site.*` keys in data/source/baseline.json — see
  src/common/baseline.py), so a change in what the public page says is
  always a reviewed baseline diff, never a silent drift.
- `smoke_test.js` receives the same dict as a JSON file and asserts the
  rendered DOM shows these values.

Nothing here is a literal: every number, name, and formatted string is
derived from the decoded rows, so a new FEC snapshot moves the
expectations with the data. The definitions restate the page's rules
(methodology §12, §14, §17) in separate code — that independence is the
point of the check.
"""
from collections import Counter

TERRITORIES = {"AS", "DC", "GU", "MP", "PR", "VI"}


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def exact(v):
    """Exact dollars as the page prints them: $1,234,567.89."""
    return f"${v:,.2f}"


def compact(v):
    """Compact dollars as the page's fmtCompact prints them."""
    a = abs(v)
    if a >= 1e9:
        s = f"${a / 1e9:.2f}B"
    elif a >= 1e6:
        s = f"${a / 1e6:.2f}M"
    elif a >= 1e3:
        s = f"${a / 1e3:.1f}K"
    else:
        s = f"${a:.0f}"
    return ("-" if v < 0 else "") + s


def party_letter(r):
    p = r["party_120"] or r["party_119"] or "?"
    return {"Democrat": "D", "Republican": "R", "Independent": "I"}.get(p, p)


def seat_status(r):
    if r["clean_2026"] is True:
        return "clean"
    if r["clean_2026"] is False:
        return "dirty"
    return "unopposed" if r["unopposed_2026"] is True else "unverified"


def _seat_counts(rows):
    c = Counter(f"{seat_status(r)} {party_letter(r)}" for r in rows)
    return dict(sorted(c.items()))


TARGET_RULES = {
    "strict": lambda r: num(r["dirty_2026"]) > 0,
    "balanced": lambda r: r["tier_balanced_2026"] == "dirty",
    "lenient": lambda r: r["tier_lenient_2026"] == "dirty",
}


def targets_2028(incoming, preset):
    """(House Democrats, Class 3 Senate Democrats) on the 2028 watchlist
    under a tolerance preset, each in dirty-2026 order."""
    rule = TARGET_RULES[preset]
    by_dirty = lambda r: -num(r["dirty_2026"])  # noqa: E731
    house = sorted((r for r in incoming if r["chamber_120"] == "House"
                    and r["party_120"] == "Democrat" and rule(r)), key=by_dirty)
    senate = sorted((r for r in incoming if r["chamber_120"] == "Senate"
                     and r["party_120"] == "Democrat"
                     and r["senate_class"] == 3 and rule(r)), key=by_dirty)
    return house, senate


def site_expectations(decoded, opp):
    """`decoded`: the embedded rows, decoded to dataset records.
    `opp`: the embedded opposition-credit payload (person_key -> entries)."""
    incoming = [r for r in decoded if r["in_120th"] == "yes"]
    house = [r for r in incoming if r["chamber_120"] == "House"]
    house_voting = [r for r in house if r["state"] not in TERRITORIES]
    delegates = [r for r in house if r["state"] in TERRITORIES]
    senate = [r for r in incoming if r["chamber_120"] == "Senate"]

    # ---- dirtiest in 2026 (front-door hook + list) ----
    dirty = sorted((r for r in decoded if num(r["dirty_2026"]) > 0),
                   key=lambda r: -num(r["dirty_2026"]))[:5]
    top1 = num(dirty[0]["dirty_2026"])
    next4 = sum(num(r["dirty_2026"]) for r in dirty[1:])
    headline = {
        "top5": [[r["full_name"], r["dirty_2026"]] for r in dirty],
        "top1_key": dirty[0]["person_key"],
        "top1_compact": compact(top1),
        "top1_returning": dirty[0]["in_120th"] == "yes",
        "next_four_total": next4,
        "next_four_compact": compact(next4),
        "exceeds_next_four": top1 > next4,
        "ratio": f"{top1 / next4:.2f}",
    }

    # ---- career dirty (explainer + leaderboard) ----
    dc = sorted((r for r in decoded if isinstance(r["dirty_career"], (int, float))),
                key=lambda r: -r["dirty_career"])
    dc_total = sum(r["dirty_career"] for r in dc)
    career_dirty = {
        "total_compact": compact(dc_total),
        "top3": [r["full_name"] for r in dc[:3]],
        "top1_exact": exact(dc[0]["dirty_career"]),
    }

    # ---- clean (Strict) ----
    clean_none = [r for r in decoded if r["clean_2026"] is None]
    h_clean = [r for r in house if r["clean_2026"] is True]
    career_clean_house = [
        r for r in house
        if num(r["corporate_pac_career"]) == 0 and num(r["aipac_pac_direct_career"]) == 0
        and num(r["udp_ie_support_career"]) == 0
        and num(r["udp_ie_opposing_opponents_career"]) == 0]
    clean = {
        "true_total": sum(1 for r in decoded if r["clean_2026"] is True),
        "null_unopposed": sorted(r["full_name"] for r in clean_none
                                 if r["unopposed_2026"] is True),
        "null_unverified": sorted(r["full_name"] for r in clean_none
                                  if r["unopposed_2026"] is not True),
        "unopposed_total": sum(1 for r in decoded if r["unopposed_2026"] is True),
        "house_120": len(h_clean),
        "house_120_democrat": sum(1 for r in h_clean if r["party_120"] == "Democrat"),
        "house_120_republican": sum(1 for r in h_clean if r["party_120"] == "Republican"),
        "senate_120": sum(1 for r in senate if r["clean_2026"] is True),
        "all_120": sum(1 for r in incoming if r["clean_2026"] is True),
        "career_clean_house_120": len(career_clean_house),
    }

    # ---- tolerance tiers ----
    def tier_counts(key):
        c = Counter(r[key] for r in incoming)
        return {"clean": c.get("clean", 0), "below_threshold": c.get("below_threshold", 0),
                "dirty": c.get("dirty", 0), "null": c.get(None, 0)}

    def not_dirty(rows, key):
        return sum(1 for r in rows if r[key] in ("clean", "below_threshold"))

    tiers = {
        "balanced": tier_counts("tier_balanced_2026"),
        "lenient": tier_counts("tier_lenient_2026"),
        "not_dirty_120": {"balanced": not_dirty(incoming, "tier_balanced_2026"),
                          "lenient": not_dirty(incoming, "tier_lenient_2026")},
        "house_not_dirty_balanced": [not_dirty(house, "tier_balanced_2026"), len(house)],
        "flag_120": sum(1 for r in incoming if r["aipac_udp_flag_2026"] is True),
        "flag_all": sum(1 for r in decoded if r["aipac_udp_flag_2026"] is True),
        "incoming_total": len(incoming),
    }

    # ---- composition charts ----
    charts = {
        "house": _seat_counts(house_voting),
        "house_named": len(house_voting),
        "senate": _seat_counts(senate),
        "senate_named": len(senate),
        "delegates": _seat_counts(delegates),
    }

    # ---- 2028 watchlist ----
    t28 = {}
    for preset in TARGET_RULES:
        h, s = targets_2028(incoming, preset)
        t28[preset] = [len(h), len(s)]
    bal_h, bal_s = targets_2028(incoming, "balanced")
    strict_s = targets_2028(incoming, "strict")[1]
    t28["balanced_house_order"] = [r["full_name"] for r in bal_h[:2]]
    t28["balanced_house_top_dirty_exact"] = exact(bal_h[0]["dirty_2026"])
    t28["balanced_senate_order"] = [r["full_name"] for r in bal_s]
    t28["balanced_senate_top_dirty_exact"] = exact(bal_s[0]["dirty_2026"])
    t28["balanced_senate_top_career_exact"] = exact(bal_s[0]["dirty_career"])
    t28["strict_senate_top3"] = [r["full_name"] for r in strict_s[:3]]
    t28["targets_2026_house"] = len(targets_2028(incoming, "strict")[0])

    # ---- leaderboards + drill-down spot values ----
    top10 = [r["full_name"] for r in sorted(
        (x for x in decoded if x["rank_total_accepted"] is not None),
        key=lambda x: x["rank_total_accepted"])[:10]]
    const = next(r for r in decoded if "Constantino" in r["full_name"])
    top1_opp = {f"{e['cycle']} {e['phase']}": e["amount"]
                for e in opp.get(headline["top1_key"], [])}
    detail = {
        "top10_total_accepted": top10,
        "constantino_self_funding_exact": exact(const["self_funding_career"]),
        "constantino_clean": const["clean_2026"],
        "top1_opposition_credit": top1_opp,
        "top1_opposition_credit_exact": [exact(v) for v in top1_opp.values()],
    }

    return {"headline": headline, "career_dirty": career_dirty, "clean": clean,
            "tiers": tiers, "charts": charts, "targets_2028": t28, "detail": detail}


def figure_literals(exp):
    """Strings that must NOT appear typed into the page's static prose —
    if one does, somebody hardcoded a figure the next snapshot strands."""
    h = exp["headline"]
    lits = [f"{amt:,.2f}".rsplit(".", 1)[0] for _, amt in h["top5"]]
    lits += [f"{h['next_four_total']:,.2f}".rsplit(".", 1)[0],
             h["top1_compact"], h["next_four_compact"]]
    return lits
