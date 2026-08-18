"""
Decidability check of the R52 criterion — ask this before burning the final block
=================================================================================

Run:  python r52_precision.py [--n 1500] [--reps 8]

★ Why this script exists ★
In the rehearsal (development seeds, N=1500) R52 landed at
    1.037 [1.000, 1.084]
The criterion is "bootstrap 95% CI lower bound **> 1.00**". The printed lower bound is exactly 1.000 —
so "pass/fail" turns on the fourth decimal place of that bootstrap quantile.

And the bootstrap quantile itself carries Monte Carlo error: change the analysis-layer random seed and
the lower bound jitters. If the jitter exceeds |lower bound − 1.00|, then this preregistered criterion
**is simply not decidable at this effect size** — the "✓/✗" from the final run is a coin flip.

**This has to be known before the final run**, because the final block can only be burned once.

This script uses only the **development seeds that are already burned**; it does not touch the 50000 block.
It changes neither the criterion nor the model, and answers one question: **can this criterion decide anything?**
"""

import argparse
import multiprocessing as mp
import os
import random
import statistics

import final_confirm as FC

R52_CI = 4          # index of R52 within CONDITIONS


def boot_lo_hi(wa, wb, seed):
    """Exactly the algorithm of final_confirm, with only the analysis-layer random seed changed"""
    n = len(wa)
    rng = random.Random(seed)
    treat = [FC.mat_tv(wa[k], wb[k]) for k in range(n)]
    boots = []
    for _ in range(FC.N_BOOT):
        pick = [rng.randrange(n) for _ in range(n)]
        b = (FC.shuffled_base([wa[i] for i in pick], FC.BASE_K, rng) +
             FC.shuffled_base([wb[i] for i in pick], FC.BASE_K, rng))
        boots.append(statistics.mean(treat[i] for i in pick) / statistics.mean(b))
    boots.sort()
    return boots[int(.025 * FC.N_BOOT)], boots[int(.975 * FC.N_BOOT)]


def _job(args):
    wa, wb, seed = args
    return seed, boot_lo_hi(wa, wb, seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--reps", type=int, default=8)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    FC.verify_frozen()
    print(f"R52 decidability check   development seeds 0–{a.n-1}   bootstrap {FC.N_BOOT} × {a.reps} analysis seeds")

    sims = [(FC.task_sim, (R52_CI, w, s0, min(FC.CHUNK, a.n - s0)))
            for w in (FC.WA, FC.WB) for s0 in range(0, a.n, FC.CHUNK)]
    store = {FC.WA: [None] * a.n, FC.WB: [None] * a.n}
    with mp.Pool(a.workers) as pool:
        for ci, w, s0, res in pool.imap_unordered(FC._dispatch, sims):
            store[w][s0:s0 + len(res)] = res

    live = [i for i in range(a.n)
            if store[FC.WA][i] is not None and store[FC.WB][i] is not None]
    wa = [store[FC.WA][i] for i in live]
    wb = [store[FC.WB][i] for i in live]
    print(f"valid n = {len(wa)}\n")

    jobs = [(_job, (wa, wb, 777 + 1000 * r)) for r in range(a.reps)]
    los = []
    with mp.Pool(min(a.workers, a.reps)) as pool:
        for seed, (lo, hi) in pool.imap_unordered(_job, [j[1] for j in jobs]):
            los.append((seed, lo, hi))
    los.sort()

    print(f"  {'analysis seed':<16}{'CI lower':>12}{'CI upper':>12}{'criterion':>12}")
    print("  " + "-" * 44)
    for seed, lo, hi in los:
        print(f"  {seed:<16}{lo:>12.5f}{hi:>12.5f}{'✓ pass' if lo > 1.0 else '✗ fail':>12}")

    vals = [lo for _, lo, _ in los]
    spread = max(vals) - min(vals)
    n_pass = sum(1 for v in vals if v > 1.0)
    print(f"\n  lower-bound range [{min(vals):.5f}, {max(vals):.5f}]   jitter {spread:.5f}")
    print(f"  {n_pass}/{len(vals)} analysis seeds judge it a pass")
    print(f"  |median lower bound − 1.00| = {abs(statistics.median(vals) - 1.0):.5f}"
          f"   vs jitter {spread:.5f}")
    if n_pass not in (0, len(vals)):
        print("\n  ⚠⚠ Criterion undecidable: changing only the **analysis-layer** random seed flips the conclusion.")
        print("     At this effect size the bright line \"CI lower bound > 1.00\" is a coin flip.")
    else:
        print("\n  ✓ The criterion is stable at this effect size (every analysis seed gives the same conclusion).")


if __name__ == "__main__":
    mp.freeze_support()
    main()
