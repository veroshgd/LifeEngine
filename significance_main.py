"""
Permutation test of the main result — is the post-transplant difference significant?
====================================================================================

Run:  python significance_main.py

`significance.py` tests the old **feeding spread axis** (400 permutations), and the 2000 sign
permutations in `behavior.py` also test the feeding axis.
**The two core numbers, transplant ratios 1.13 / 1.04, had no p value at all until now.** (experiment 021 §5)

★ How to get around "TV is always positive, so sign permutation is unusable" (notes line 804) ★
-----------------------------------------------------------------------------------------------
TV distance is always positive, so flipping its sign directly is meaningless. But **the difference
between the numerator and the denominator of the ratio** can go either way. So push the statistic
down to **each seed**:

    d_i = TV(A_i, B_i)                       same seed, two worlds     ← world effect
    b_i = mean_j TV(A_i, A_j), TV(B_i, B_j)  same world, different seed ← seed effect
    δ_i = d_i − b_i                          how much more the world explains than the seed, on this seed

H0: the world is no stronger than the seed → E[δ] = 0, and the signs of δ_i are symmetric.
That makes **sign permutation legitimate**: flip the signs of δ_i at random N times to obtain the null distribution.

This is also the correct form of the effect size — the mean of δ carries units (TV) and has one
less layer of Jensen bias than a "ratio".

⚠ Known limitation: b_i reuses balls from other seeds, so the δ_i are weakly correlated.
   The rigorous approach is a cluster bootstrap; sign permutation is slightly optimistic here,
   but when the p value is of order 1e-4 the correction is irrelevant.
"""

import math
import random
import statistics
import sys

import sim
import scenarios
import persistence_ablation as PA
from transplant import run_phased, window_tv

WA, WB, COMMON = "rich world", "barren world", "baseline"
N_PERM = 10000
BASE_K = 5          # how many random opponents are averaged for each seed's b_i


def per_seed_delta(cohA, cohB, n_seeds, rng):
    """Return the per-seed δ_i, plus the means of numerator/denominator (to line up with the old ratio convention)"""
    live = [i for i in range(n_seeds)
            if cohA[i][0] is not None and cohB[i][0] is not None]
    wa = [cohA[i][1] for i in live]
    wb = [cohB[i][1] for i in live]
    n = len(live)
    if n < 30:
        return None

    deltas, ds, bs = [], [], []
    for k in range(n):
        d = window_tv(wa[k], wb[k])
        opp = []
        for _ in range(BASE_K):
            j = rng.randrange(n - 1)
            j = j if j < k else j + 1          # exclude itself
            opp.append(window_tv(wa[k], wa[j]))
            j = rng.randrange(n - 1)
            j = j if j < k else j + 1
            opp.append(window_tv(wb[k], wb[j]))
        b = statistics.mean(opp)
        deltas.append(d - b)
        ds.append(d)
        bs.append(b)
    return deltas, statistics.mean(ds), statistics.mean(bs)


def sign_perm_p(deltas, n_perm, rng):
    """Sign permutation: under H0 the signs of δ_i are symmetric"""
    obs = statistics.mean(deltas)
    hits = 0
    for _ in range(n_perm):
        m = statistics.mean(d if rng.random() < 0.5 else -d for d in deltas)
        if abs(m) >= abs(obs):
            hits += 1
    return obs, (hits + 1) / (n_perm + 1)      # +1 correction, so p is never reported as 0


def cohen_dz(deltas):
    sd = statistics.stdev(deltas)
    return statistics.mean(deltas) / sd if sd else 0.0


def run(label, cfg, n_seeds, seed0):
    sat_backup = sim.TRAIT_SATURATION
    if "sat" in cfg:
        sim.TRAIT_SATURATION = cfg["sat"]
    scenarios.make = PA.patched_make(cfg.get("ident", False), cfg.get("floor", False))
    try:
        seeds = range(seed0, seed0 + n_seeds)
        ca = [run_phased(s, WA, COMMON) for s in seeds]
        cb = [run_phased(s, WB, COMMON) for s in seeds]
    finally:
        sim.TRAIT_SATURATION = sat_backup
        scenarios.make = PA._orig_make

    rng = random.Random(12345)
    got = per_seed_delta(ca, cb, n_seeds, rng)
    if got is None:
        print(f"  {label:<20} not enough samples")
        return
    deltas, md, mb = got
    obs, p = sign_perm_p(deltas, N_PERM, rng)
    dz = cohen_dz(deltas)
    frac = sum(1 for d in deltas if d > 0) / len(deltas)
    star = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."
    print(f"  {label:<16}{len(deltas):>6}{md:>9.4f}{mb:>9.4f}{md/mb:>8.3f}"
          f"{obs:>+10.4f}{dz:>8.2f}{frac:>8.1%}{p:>10.4f}  {star}")


def main():
    n_seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    print("=" * 104)
    print(f" Main-result permutation test   per-seed δ = TV(same seed across worlds) − TV(same world across seeds)"
          f"   {N_PERM} sign permutations")
    print("=" * 104)
    print(f"  {'condition':<20}{'n':>6}{'numerator TV':>14}{'baseline TV':>13}{'ratio':>8}"
          f"{'mean δ':>10}{'dz':>8}{'δ>0':>8}{'p':>10}")
    print("  " + "-" * 100)

    for seed0, tag in ((0, "development set seeds 0+"), (10000, "holdout set seeds 10000+")):
        print(f"\n  ── {tag}, N={n_seeds} ──")
        run("full architecture", dict(), n_seeds, seed0)
        run("−all floors ①②", dict(floor=True), n_seeds, seed0)

    print("\n  mean δ = the extra TV the world effect has over the seed effect (with units, no Jensen bias)")
    print("  dz     = Cohen's dz (paired effect size)    δ>0 = on how many seeds the world won")


if __name__ == "__main__":
    main()
