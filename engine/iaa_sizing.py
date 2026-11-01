#!/usr/bin/env python3
"""Inter-annotator agreement for pass/fail audits where almost everything passes, and how big a
double-audit overlap has to be. Stdlib only.

At a 98% pass rate two auditors with no skill at all agree on 96% of items, so raw agreement
(and Gwet's AC1) measure how easy the passes are. The figure that carries information is FAIL
AGREEMENT, the positive specific agreement p_pos = 2a / (2a + b + c): when one auditor fails an
item, how often does the other? Precision on it comes from the number of fails both auditors saw,
not from the number of items, so an overlap is sized in fails.

    python3 engine/iaa_sizing.py counts --a 11 --b 4 --c 5 --d 980
    python3 engine/iaa_sizing.py size --pass-rate 0.98 --target-fails 50 --catch 0.75
    python3 engine/iaa_sizing.py size --pass-rate 0.98 --target-fails 50 --catch 0.75 \\
        --enriched-share 0.17 --enriched-fail-share 0.60

Cells: a = both fail, b = first fails only, c = second fails only, d = both pass.
Formulas: Hripcsak & Rothschild 2005 (specific agreement); Cohen 1960 (kappa); Gwet 2008 (AC1),
Feinstein & Cicchetti 1990 (the paradox). The planning rule (50 to 100 fails per auditor pair)
follows from the widths below, which a simulation over the stated population reproduces.
"""
import argparse
import math
import random
import sys


def agreement_from_counts(a, b, c, d):
    """Every agreement figure for a 2x2 pass/fail table, with the ones not to headline marked."""
    n = a + b + c + d
    if n <= 0:
        raise ValueError("empty table")
    raw = (a + d) / n
    p_pos = (2 * a / (2 * a + b + c)) if (2 * a + b + c) > 0 else float("nan")
    p_neg = (2 * d / (2 * d + b + c)) if (2 * d + b + c) > 0 else float("nan")
    f1 = (a + b) / n   # first auditor's fail rate
    f2 = (a + c) / n   # second auditor's fail rate
    pe_kappa = f1 * f2 + (1 - f1) * (1 - f2)
    kappa = (raw - pe_kappa) / (1 - pe_kappa) if pe_kappa < 1 else float("nan")
    pi = (f1 + f2) / 2
    pe_ac1 = 2 * pi * (1 - pi)
    ac1 = (raw - pe_ac1) / (1 - pe_ac1) if pe_ac1 < 1 else float("nan")
    return {
        "n": n,
        "fail_agreement_p_pos": p_pos,      # headline
        "kappa": kappa,                     # report beside it
        "pass_agreement_p_neg": p_neg,
        "raw_agreement": raw,               # do not headline
        "ac1": ac1,                         # do not headline
        "prevalence_index": (a - d) / n,
        "bias_index": (b - c) / n,          # positive: the first auditor fails more
        "fail_rate_first": f1,
        "fail_rate_second": f2,
    }


def bootstrap_ci(a, b, c, d, reps=2000, seed=20261101, level=0.95):
    """Percentile bootstrap over items (multinomial resample of the four cells) for p_pos and kappa.
    Items that cluster (one audio file, one annotator) should be resampled by cluster instead;
    this helper takes counts, so it cannot, and says so in its output."""
    n = a + b + c + d
    rng = random.Random(seed)
    probs = [a / n, b / n, c / n, d / n]
    pp, kk = [], []
    for _ in range(reps):
        cells = [0, 0, 0, 0]
        for _ in range(n):
            u = rng.random()
            acc = 0.0
            for i, p in enumerate(probs):
                acc += p
                if u < acc:
                    cells[i] += 1
                    break
            else:
                cells[3] += 1
        r = agreement_from_counts(*cells)
        if not math.isnan(r["fail_agreement_p_pos"]):
            pp.append(r["fail_agreement_p_pos"])
        if not math.isnan(r["kappa"]):
            kk.append(r["kappa"])
    lo, hi = (1 - level) / 2, 1 - (1 - level) / 2

    def q(xs, p):
        if not xs:
            return float("nan")
        xs = sorted(xs)
        k = min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))
        return xs[k]

    return {
        "p_pos_ci": (q(pp, lo), q(pp, hi)),
        "kappa_ci": (q(kk, lo), q(kk, hi)),
        "p_pos_undefined_share": 1 - len(pp) / reps,   # samples with no fail at all
        "reps": reps,
        "note": "resampled by item from counts; resample by cluster when items share a file or an annotator",
    }


def population_cells(fail_rate, catch, false_fail):
    """Expected 2x2 cell shares for two independent auditors on a population with a true fail rate,
    each catching a true fail with probability `catch` and failing a true pass with probability
    `false_fail`. The report's realistic case is (0.02, 0.75, 0.005); the zero-skill case is
    (p, p, p) for any p, which reduces to two coins."""
    a = fail_rate * catch ** 2 + (1 - fail_rate) * false_fail ** 2
    bc = fail_rate * 2 * catch * (1 - catch) + (1 - fail_rate) * 2 * false_fail * (1 - false_fail)
    d = 1 - a - bc
    return a, bc / 2, bc / 2, d


def expected_fails(items, fail_rate, catch=1.0, false_fail=0.0):
    """How many items one auditor fails, in expectation, in `items` randomly drawn items."""
    return items * (fail_rate * catch + (1 - fail_rate) * false_fail)


def overlap_for_fails(target_fails, fail_rate, catch=1.0, false_fail=0.0,
                      enriched_share=None, enriched_fail_share=None):
    """Items each auditor pair must share to see `target_fails` fails per auditor.

    Random stratum: fails per item = fail_rate*catch + (1-fail_rate)*false_fail.
    Fail-enriched stratum: a selector flags a share s of items that hold a share e of the true
    fails, so the true fail rate inside the flagged stratum is fail_rate * e / s (capped at 1);
    report p_pos across strata (it ignores the both-pass cell), and reweight anything else by
    inverse sampling probability."""
    per_item_random = fail_rate * catch + (1 - fail_rate) * false_fail
    out = {"target_fails_per_auditor": target_fails,
           "random_items_needed": math.ceil(target_fails / per_item_random) if per_item_random > 0 else float("inf")}
    if enriched_share and enriched_fail_share:
        fr_in = min(1.0, fail_rate * enriched_fail_share / enriched_share)
        per_item_enriched = fr_in * catch + (1 - fr_in) * false_fail
        out["enriched_fail_rate"] = fr_in
        out["enriched_items_needed"] = math.ceil(target_fails / per_item_enriched) if per_item_enriched > 0 else float("inf")
    return out


def _fmt(x):
    if isinstance(x, float):
        return "nan" if math.isnan(x) else f"{x:.3f}"
    return str(x)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="iaa_sizing", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("counts", help="agreement figures for a 2x2 pass/fail table")
    for k in ("a", "b", "c", "d"):
        c.add_argument(f"--{k}", type=int, required=True)
    c.add_argument("--reps", type=int, default=2000)
    s = sub.add_parser("size", help="overlap needed to see a target number of fails per auditor")
    s.add_argument("--pass-rate", type=float, required=True)
    s.add_argument("--target-fails", type=int, default=50)
    s.add_argument("--catch", type=float, default=1.0, help="probability an auditor catches a true fail")
    s.add_argument("--false-fail", type=float, default=0.0, help="probability an auditor fails a true pass")
    s.add_argument("--enriched-share", type=float, default=None, help="share of items a selector flags")
    s.add_argument("--enriched-fail-share", type=float, default=None, help="share of true fails inside the flagged items")
    args = ap.parse_args(argv)

    if args.cmd == "counts":
        r = agreement_from_counts(args.a, args.b, args.c, args.d)
        ci = bootstrap_ci(args.a, args.b, args.c, args.d, reps=args.reps)
        print(f"n = {r['n']}  (both fail {args.a}, first only {args.b}, second only {args.c}, both pass {args.d})")
        print(f"HEADLINE  fail agreement p_pos  {_fmt(r['fail_agreement_p_pos'])}  95% CI [{_fmt(ci['p_pos_ci'][0])}, {_fmt(ci['p_pos_ci'][1])}]")
        print(f"          kappa                 {_fmt(r['kappa'])}  95% CI [{_fmt(ci['kappa_ci'][0])}, {_fmt(ci['kappa_ci'][1])}]")
        print(f"also      pass agreement p_neg  {_fmt(r['pass_agreement_p_neg'])}   bias index {_fmt(r['bias_index'])}   prevalence index {_fmt(r['prevalence_index'])}")
        print(f"not a headline  raw agreement {_fmt(r['raw_agreement'])}   AC1 {_fmt(r['ac1'])}   (both track how easy the passes are)")
        if ci["p_pos_undefined_share"] > 0:
            print(f"warning: p_pos undefined in {ci['p_pos_undefined_share']:.1%} of resamples: too few fails to read it")
        print(ci["note"])
        return 0

    fr = 1 - args.pass_rate
    o = overlap_for_fails(args.target_fails, fr, args.catch, args.false_fail, args.enriched_share, args.enriched_fail_share)
    zero = agreement_from_counts(*population_cells(fr, fr, fr))
    print(f"pass rate {args.pass_rate:.3f}: two auditors with no skill still show raw agreement {zero['raw_agreement']:.4f} and AC1 {zero['ac1']:.3f}; size the overlap in fails, not items")
    print(f"target {args.target_fails} fails per auditor (catch {args.catch}, false fail {args.false_fail}):")
    print(f"  random stratum   {o['random_items_needed']} double-audited items")
    if "enriched_items_needed" in o:
        print(f"  enriched stratum {o['enriched_items_needed']} items  (selector flags {args.enriched_share:.0%} of items holding {args.enriched_fail_share:.0%} of fails: fail rate inside {o['enriched_fail_rate']:.1%})")
        print("  report p_pos across strata; reweight any other figure by inverse sampling probability")
    return 0


if __name__ == "__main__":
    sys.exit(main())
