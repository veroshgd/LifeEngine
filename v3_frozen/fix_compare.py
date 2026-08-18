"""
Comparison of the three fixes — they cure mortality, but do they flatten the difference too?
============================================================================================

Run:  python fix_compare.py

Rule 43 offers three candidate fixes. Looking at mortality alone picks the wrong one: **any change
that makes every ball forage desperately also compresses the behavioural difference between the
worlds** — mortality down to 0 while the ratio collapses to 1 is a failure.

So every variant reports four numbers at once:

    mortality(120d, full)   mortality(120d, all floors off)   ← should fall
    headline ratio(60d, full)  ratio(60d, all floors off)     ← must not collapse

★ Criterion ★
  A good fix = both mortalities <15%, and neither ratio significantly below the status quo.
  Rule 44: the all-floors-off column matters most — its current 53.9% mortality is the contamination source.
"""

import random
import statistics
import sys

import sim
import scenarios
import persistence_ablation as PA
from transplant import run_phased, window_tv
from p1_test import shuffled_base, BASE_K

WA, WB, COMMON = "rich world", "barren world", "baseline"
N_RATIO = 500      # for the ratio (60 days)
N_DEATH = 300      # for mortality (120 days, more expensive)
# 400 iterations are enough to position this comparison table; shuffled_base recomputes ~2500 TVs
# each time, so going up to 1500 would take nearly an hour for eight variants — not worth it.
N_BOOT = 400


def ratio_and_death(floor_off, days=60, n=N_RATIO):
    """Return (ratio, CI, mortality). At days=120 only the mortality is meaningful."""
    sim.SIM_DAYS = days
    import transplant as T
    old_total = T.TOTAL
    T.TOTAL = days
    scenarios.make = PA.patched_make(False, floor_off)
    try:
        ca = [run_phased(s, WA, COMMON, split=30, total=days) for s in range(n)]
        cb = [run_phased(s, WB, COMMON, split=30, total=days) for s in range(n)]
    finally:
        scenarios.make = PA._orig_make
        T.TOTAL = old_total

    live = [i for i in range(n) if ca[i][0] is not None and cb[i][0] is not None]
    dead = 1 - len(live) / n
    if len(live) < 50:
        return None, (0, 0), dead
    wa = [ca[i][1] for i in live]
    wb = [cb[i][1] for i in live]
    rng = random.Random(777)
    treat = [window_tv(wa[k], wb[k]) for k in range(len(live))]
    base = shuffled_base(wa, BASE_K, rng) + shuffled_base(wb, BASE_K, rng)
    ratio = statistics.mean(treat) / statistics.mean(base)
    boots = []
    for _ in range(N_BOOT):
        pick = [rng.randrange(len(live)) for _ in range(len(live))]
        boots.append(statistics.mean(treat[i] for i in pick) /
                     statistics.mean(shuffled_base([wa[i] for i in pick], BASE_K, rng) +
                                     shuffled_base([wb[i] for i in pick], BASE_K, rng)))
    boots.sort()
    return ratio, (boots[int(.025*N_BOOT)], boots[int(.975*N_BOOT)]), dead


def setfix(a, b, c):
    sim.SLEEP_SUPPRESS, sim.HUNGER_URGENCY, sim.SLEEP_EFF_FLOOR = a, b, c


FIXES = [
    ("status quo (no fix)",     0.0,  0.0, 0.35),
    ("A suppress sleep 0.5",    0.5,  0.0, 0.35),
    ("A suppress sleep 1.0",    1.0,  0.0, 0.35),
    ("B raise urgency 25",      0.0, 25.0, 0.35),
    ("B raise urgency 50",      0.0, 50.0, 0.35),
    ("C sleep floor 0.60",      0.0,  0.0, 0.60),
    ("C sleep floor 0.80",      0.0,  0.0, 0.80),
    ("A0.5 + C0.6 combined",    0.5,  0.0, 0.60),
]


def main():
    k_on = "--k-off" not in sys.argv
    sim.KNOWLEDGE_WEIGHT = 12.0 if k_on else 0.0
    sim.KNOWLEDGE_GOAL_WEIGHT = 0.25 if k_on else 0.0
    sim.KNOWLEDGE_FORGET = 0.02 if k_on else 0.0

    print("=" * 104)
    print(f" Comparison of the three fixes   022 {'on' if k_on else 'off'}   "
          f"ratio N={N_RATIO}(60d)   mortality N={N_DEATH}(120d)")
    print("=" * 104)
    print(f"  {'fix':<24}{'dead% full':>12}{'dead% no floor':>16}"
          f"{'ratio full':>22}{'ratio no floor':>22}")
    print("  " + "-" * 100)

    for label, a, b, c in FIXES:
        setfix(a, b, c)
        r_full, ci_full, _ = ratio_and_death(False, 60)
        r_abl,  ci_abl,  _ = ratio_and_death(True, 60)
        _, _, d_full = ratio_and_death(False, 120, N_DEATH)
        _, _, d_abl = ratio_and_death(True, 120, N_DEATH)
        f_ok = "" if d_full < 0.15 else "⚠"
        a_ok = "" if d_abl < 0.15 else "⚠"
        print(f"  {label:<18}{d_full:>10.1%}{f_ok:<1}{d_abl:>11.1%}{a_ok:<1}"
              f"{r_full:>10.3f} [{ci_full[0]:.3f},{ci_full[1]:.3f}]"
              f"{r_abl:>10.3f} [{ci_abl[0]:.3f},{ci_abl[1]:.3f}]")

    print("\n  Criterion: both mortalities <15% (no ⚠), and neither ratio significantly below the \"status quo\" row")
    print("  ⚠ Curing mortality often costs the difference — a collapsed ratio is a failure even if mortality drops to 0")


if __name__ == "__main__":
    main()
