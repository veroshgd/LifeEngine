"""
Mortality split — decomposing cond_compare's "paired mortality" back into single worlds
=======================================================================================

Run:  python death_split.py            (default N=300, 12 processes, about 5 minutes)
        python death_split.py --seeds 100 --workers 6

★ Why split it ★
In `fix_compare.ratio_and_death`, `live` requires **both the rich and the barren arm to survive**,
so what it reports is a **paired** mortality ≈ 1−(1−p_rich)(1−p_barren) — one number smearing two worlds together.

`cliff_probe.py` (N=60, barren only) matched the "status quo" cell:
    single barren ball 23.3% → 1−(1−0.233)² = 41.2%   vs   cond_compare measured 40.7% ✓
But ① threshold 55 does not match:
    single barren ball 11.7% → should be ≈22%          vs   cond_compare measured 43.3% ✗

Two possibilities, and they must be told apart or the choice of v3's threshold is a guess:
  (a) the rich arm dies unusually often at the 55 setting — then ①55 really is unusable;
  (b) noise from cliff_probe's N=60 (SE≈±5pp) — then ①55 is in fact fine.

Here both worlds are run, N is raised to 300, single-world mortality is reported per variant, and
the **paired mortality is recomputed from the single-world numbers** and reconciled with
cond_compare's measurement. A mismatch means the "the two arms are independent" assumption is
itself wrong (the two arms of one seed share an initial personality and are correlated by construction).
"""

import argparse
import multiprocessing as mp
import os
import time

WA, WB, COMMON = "rich world", "barren world", "baseline"
SPLIT, TOTAL = 30, 120

# (label, recovery threshold, dead-zone recovery, shelter recovery)
VARIANTS = [
    ("status quo",      30.0, 0.00, 0.00),
    ("① threshold 55",  55.0, 0.00, 0.00),
    ("① threshold 60",  60.0, 0.00, 0.00),
    ("① threshold 65",  65.0, 0.00, 0.00),
    ("③ shelter +0.10", 30.0, 0.00, 0.10),
]
CHUNK = 25          # seeds per task, to amortise process startup cost


def evaluate(task):
    """One task = (variant, world, floors off, first seed, count) → how many died"""
    vi, world, floor_off, seed0, n = task

    import sim
    import scenarios
    import persistence_ablation as PA
    import transplant as T
    from transplant import run_phased

    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    _, rec_at, dz, sh = VARIANTS[vi]
    sim.COND_RECOVER_AT, sim.COND_DEADZONE_RECOVER, sim.COND_SHELTER_RECOVER = rec_at, dz, sh
    sim.SIM_DAYS, T.TOTAL = TOTAL, TOTAL

    scenarios.make = PA.patched_make(False, floor_off)
    try:
        dead = sum(run_phased(s, world, COMMON, split=SPLIT, total=TOTAL)[0] is None
                   for s in range(seed0, seed0 + n))
    finally:
        scenarios.make = PA._orig_make
    return (vi, world, floor_off), dead, n


# The paired mortalities measured in cond_compare §3g, used for reconciliation
COND_COMPARE = {          # label: (full, no floor)
    "status quo":      (0.187, 0.407),
    "① threshold 55":  (0.137, 0.433),
    "① threshold 65":  (0.050, 0.073),
    "③ shelter +0.10": (0.067, 0.340),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=300)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    tasks = [(vi, w, fo, s0, min(CHUNK, a.seeds - s0))
             for vi in range(len(VARIANTS))
             for w in (WA, WB)
             for fo in (False, True)
             for s0 in range(0, a.seeds, CHUNK)]

    print(f"Mortality split  {len(VARIANTS)} variants × 2 worlds × 2 architectures × {a.seeds} seeds "
          f"× {TOTAL} days   processes {a.workers}")
    acc, t0 = {}, time.time()
    with mp.Pool(a.workers) as pool:
        for k, (key, dead, n) in enumerate(pool.imap_unordered(evaluate, tasks), 1):
            d, t = acc.get(key, (0, 0))
            acc[key] = (d + dead, t + n)
            if k % 20 == 0 or k == len(tasks):
                el = time.time() - t0
                print(f"  {k}/{len(tasks)}  elapsed {el/60:.1f}min  "
                      f"remaining ~{el/k*(len(tasks)-k)/60:.1f}min", flush=True)

    for floor_off in (False, True):
        arch = "all floors off" if floor_off else "full architecture"
        print("\n" + "=" * 92)
        print(f" Single-world mortality · {arch} · N={a.seeds} · 120 days · transplanted to baseline on day 30")
        print("=" * 92)
        print(f"  {'fix':<20}{'rich world':>12}{'barren world':>14}"
              f"{'independent paired':>20}{'cond_compare':>14}{'diff':>8}")
        print("  " + "-" * 88)
        for vi, (label, *_) in enumerate(VARIANTS):
            da, na = acc[(vi, WA, floor_off)]
            db, nb = acc[(vi, WB, floor_off)]
            pa, pb = da / na, db / nb
            pred = 1 - (1 - pa) * (1 - pb)
            obs = COND_COMPARE.get(label, (None, None))[1 if floor_off else 0]
            o = f"{obs:>13.1%}" if obs is not None else f"{'—':>14}"
            df = f"{pred-obs:>+7.1%}" if obs is not None else f"{'—':>8}"
            print(f"  {label:<14}{pa:>9.1%}{pb:>9.1%}{pred:>13.1%}{o}{df}")
        print(f"\n  \"independent paired\" = 1−(1−p_rich)(1−p_barren), assuming the arms are independent.")
        print(f"  The gap to cond_compare is exactly **the correlation between the two arms of one seed** (shared initial personality):")
        print(f"  predicted > measured → the arms live and die together (positive correlation); predicted < measured → anomalous, investigate.")
        se = (0.25 / a.seeds) ** 0.5
        print(f"  Largest standard error of a single-world mortality ≈ ±{se:.1%} (N={a.seeds})")


if __name__ == "__main__":
    mp.freeze_support()
    main()
