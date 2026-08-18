"""
Read the results of param_sweep.py and produce the sentences the paper can quote directly.

Run:  python sweep_report.py [sweep_results.csv]
"""

import csv
import statistics
import sys

DEAD_MAX = 0.40      # configurations above this mortality are dropped (a ratio is meaningless after a wipeout)
PARAMS = ["PERSONALITY_WEIGHT", "TRAIT_DRIFT", "TRAIT_SATURATION",
          "LANDMARK_BONUS", "HARDSHIP_MAX_BOOST", "FLOOR_DECAY_PER_DAY",
          "LANDMARK_PERMANENT", "GOAL_BONUS", "GOAL_OFF_TASK",
          "GOAL_SWITCH_MARGIN", "GOAL_MIN_DAYS", "GOAL_REFRACTORY",
          "GOAL_STALL_DAYS", "GOAL_SLACK_FOOD", "GOAL_SLACK_COND"]


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def pct(vals, p):
    s = sorted(vals)
    return s[min(len(s) - 1, int(p * len(s)))]


def main(path="sweep_results.csv"):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("empty file")
        return

    kept = [r for r in rows if float(r["dead_move"]) <= DEAD_MAX]
    rm = [float(r["ratio_move"]) for r in kept]
    gm = [float(r["goal_ratio_move"]) for r in kept]
    lr = [float(r["logratio_move"]) for r in kept]

    print("=" * 78)
    print(f" Parameter-randomisation set   {len(rows)} configurations, {len(kept)} after dropping wipeouts"
          f" (mortality > {DEAD_MAX:.0%})")
    print("=" * 78)

    for label, vals, thresh in [("transplant ratio (routine)", rm, 1.0),
                                ("transplant ratio (goal)", gm, 1.0),
                                ("log ratio (routine)", lr, 0.0)]:
        above = sum(1 for v in vals if v > thresh) / len(vals)
        print(f"\n  {label}")
        print(f"    median {statistics.median(vals):.3f}   "
              f"IQR [{pct(vals, .25):.3f}, {pct(vals, .75):.3f}]   "
              f"90% interval [{pct(vals, .05):.3f}, {pct(vals, .95):.3f}]")
        print(f"    share > {thresh:g}: {above:.1%}   ← report this number in the paper")

    print("\n" + "=" * 78)
    print(" Parameter sensitivity (Spearman; large |ρ| = the conclusion depends on this knob)")
    print("=" * 78)
    corr = sorted(((abs(spearman([float(r[p]) for r in kept], rm)), p,
                    spearman([float(r[p]) for r in kept], rm))
                   for p in PARAMS), reverse=True)
    for mag, name, rho in corr:
        bar = "#" * int(mag * 40)
        print(f"  {name:<22}{rho:+.3f}  {bar}")

    print("\n  How to read: |ρ| < 0.2 = the conclusion is insensitive to this parameter (good)")
    print("               |ρ| > 0.4 = the effect is mainly decided by this knob and must be discussed in the paper")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sweep_results.csv")
