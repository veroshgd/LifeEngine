"""
P1 — after wiring, can the no-floor variant still reach a ratio > 1?
====================================================================

Run:  python p1_test.py

Preregistration [[Experiment 022 preregistration — memory wired into decisions]] §4:

    P1: after wiring, the no-floor transplant ratio > 1, N=1500, bootstrap 95% CI lower bound > 1.00

Baseline (021, 022 off): −all floors ①② = 1.044 [0.996, 1.094], p≈0.07 n.s.

★ Seeds: 20000–21499 ★ reserved in §6 of the preregistration for the 022 confirmation, never used before.
★ Baseline: K=5 random pairing (rule 35), not adjacent pairing.
★ Both a bootstrap CI and a sign-permutation p are reported (rule 34 + the method of 021 §5).
"""

import random
import statistics

import sim
import scenarios
import persistence_ablation as PA
from transplant import run_phased, window_tv
from significance_main import per_seed_delta, sign_perm_p, cohen_dz

WA, WB, COMMON = "rich world", "barren world", "baseline"
N_SEEDS = 1500
SEED0 = 20000
BASE_K = 5
N_BOOT = 3000
N_PERM = 10000


def shuffled_base(windows, k, rng):
    out = []
    idx = list(range(len(windows)))
    for _ in range(k):
        rng.shuffle(idx)
        out += [window_tv(windows[idx[j]], windows[idx[j + 1]])
                for j in range(0, len(idx) - 1, 2)]
    return out


def cohorts(cfg):
    sat_backup = sim.TRAIT_SATURATION
    if "sat" in cfg:
        sim.TRAIT_SATURATION = cfg["sat"]
    scenarios.make = PA.patched_make(cfg.get("ident", False), cfg.get("floor", False))
    try:
        seeds = range(SEED0, SEED0 + N_SEEDS)
        ca = [run_phased(s, WA, COMMON) for s in seeds]
        cb = [run_phased(s, WB, COMMON) for s in seeds]
    finally:
        sim.TRAIT_SATURATION = sat_backup
        scenarios.make = PA._orig_make
    return ca, cb


def analyse(label, cfg):
    ca, cb = cohorts(cfg)
    live = [i for i in range(N_SEEDS)
            if ca[i][0] is not None and cb[i][0] is not None]
    n = len(live)
    wa = [ca[i][1] for i in live]
    wb = [cb[i][1] for i in live]
    rng = random.Random(777)

    treat = [window_tv(wa[k], wb[k]) for k in range(n)]
    base = shuffled_base(wa, BASE_K, rng) + shuffled_base(wb, BASE_K, rng)
    ratio = statistics.mean(treat) / statistics.mean(base)

    # cluster bootstrap: resample by agent
    boots = []
    for _ in range(N_BOOT):
        pick = [rng.randrange(n) for _ in range(n)]
        t = [treat[i] for i in pick]
        b = (shuffled_base([wa[i] for i in pick], BASE_K, rng) +
             shuffled_base([wb[i] for i in pick], BASE_K, rng))
        boots.append(statistics.mean(t) / statistics.mean(b))
    boots.sort()
    lo, hi = boots[int(.025 * N_BOOT)], boots[int(.975 * N_BOOT)]

    got = per_seed_delta(ca, cb, N_SEEDS, random.Random(12345))
    deltas = got[0]
    obs, p = sign_perm_p(deltas, N_PERM, random.Random(999))
    dz = cohen_dz(deltas)
    dead = 1 - n / N_SEEDS
    star = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."
    ok = "✓ pass" if lo > 1.0 else "✗ fail"
    print(f"  {label:<20}{n:>6}{dead:>8.1%}{ratio:>8.3f}  [{lo:.3f}, {hi:.3f}]"
          f"{obs:>+9.4f}{dz:>7.2f}{p:>9.4f} {star:<5}{ok}")
    return ratio, lo, hi


def main():
    print("=" * 108)
    print(f" P1 confirmation   seeds {SEED0}–{SEED0+N_SEEDS-1} (preregistered reserved block, first use)"
          f"   N={N_SEEDS}   baseline K={BASE_K} random pairing")
    print("=" * 108)
    print(f"  {'condition':<22}{'n':>6}{'dead':>8}{'ratio':>8}  {'95% CI':<18}"
          f"{'mean δ':>9}{'dz':>7}{'p':>9}      P1")
    print("  " + "-" * 104)

    for tag, (w, gw, f) in [("022 off", (0.0, 0.0, 0.0)),
                            ("022 on", (12.0, 0.25, 0.02))]:
        sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = w, gw, f
        print(f"\n  ── {tag}  (W={w} GW={gw} FORGET={f}) ──")
        analyse("full architecture", dict())
        analyse("−all floors ①②", dict(floor=True))

    print("\n  P1 criterion: on the **022 on + −all floors ①②** row, the CI lower bound > 1.00")
    print("  Baseline (022 off): 1.044 [0.996, 1.094], p≈0.07 n.s.")


if __name__ == "__main__":
    main()
