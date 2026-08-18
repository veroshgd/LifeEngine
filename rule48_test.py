"""
Rule 48 discriminative test — did the ratio really rise, or is it a selection effect?
================================================

Run:  python rule48_test.py              (default N=800, 12 processes)
        python rule48_test.py --seeds 200 --workers 6

★ The open question ★
In §3g all nine variants had a ratio **≥ status quo**, and rule 48 (survival pressure compresses
behavioural variance) was written on that basis. But that table has a structural flaw: `live` in
`fix_compare.ratio_and_death` requires **both worlds to survive**, so **each variant's ratio is
computed on a different surviving subset**. As soon as mortality drops, a different batch of balls
enters the statistic — the cross-variant comparison is mixed with a selection effect. And what rule
48 wants to say is precisely that "who gets filtered out" changes the ratio; the two are entangled.

★ Three improvements ★
① **Common seed set**: recompute every variant using only the seeds that are "alive in all
   variants × both worlds". Same balls, same window, and the only difference is the condition rule itself.
② **Per-seed pairing**: Δ_i = δ_i(variant) − δ_i(status quo), with sign permutation (the δ
   construction of rule 021 §5). §3g compared whether CIs overlapped — with N_BOOT=400 the CIs
   are wide enough to cover each other by half, so significance was never decidable. A paired
   test cancels between-seed variance and has an order of magnitude more power.
③ **Fixed opponent indices**: the baseline b_i of δ_i draws BASE_K same-world opponents. Every
   variant draws **the same set** of indices, otherwise sampling noise masquerades as a between-variant difference.

★ One piece of reverse circumstantial evidence (not tested by this script) ★
Rule 34: the ratio estimator is inflated at small N. The status quo has the smallest effective N
and yet the lowest ratio — the direction of the bias cannot explain what §3g saw. So rule 48 is
plausible, but it only stands up with ①②③.
"""

import argparse
import multiprocessing as mp
import os
import random
import statistics
import time

WA, WB, COMMON = "rich world", "barren world", "baseline"
SPLIT, TOTAL = 30, 60          # ratio convention: 60-day window (same as §3g)
BASE_K = 5
N_PERM = 10000

VARIANTS = [
    ("status quo",      30.0, 0.00, 0.00),
    ("① threshold 55",  55.0, 0.00, 0.00),
    ("① threshold 60",  60.0, 0.00, 0.00),
    ("① threshold 65",  65.0, 0.00, 0.00),
    ("③ shelter +0.10", 30.0, 0.00, 0.10),
]
CHUNK = 40


def evaluate(task):
    """One task = (variant, world, floors off, first seed, count)
    Returns the **normalised window matrix** for each seed (None if it died) — far cheaper than shipping back a Counter"""
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

    def to_mat(w):
        """[24 × Counter] → [24 × normalised frequencies], the compact equivalent of window_tv"""
        out = []
        for h in w:
            tot = sum(h.values()) or 1
            out.append(tuple(h[x] / tot for x in sim.ACTIONS))
        return tuple(out)

    scenarios.make = PA.patched_make(False, floor_off)
    try:
        res = []
        for s in range(seed0, seed0 + n):
            _, w = run_phased(s, world, COMMON, split=SPLIT, total=TOTAL)
            res.append(None if w is None else to_mat(w))
    finally:
        scenarios.make = PA._orig_make
    return (vi, world, floor_off), seed0, res


def mat_tv(a, b):
    """Bit-for-bit equivalent to transplant.window_tv, but taking normalised matrices"""
    return sum(0.5 * sum(abs(x - y) for x, y in zip(ha, hb))
               for ha, hb in zip(a, b)) / len(a)


def deltas_on(idx, wa, wb, opp):
    """Given a seed-index set idx and a fixed opponent sample opp, compute the per-seed δ_i, numerator and denominator"""
    ds, bs = [], []
    for k, i in enumerate(idx):
        d = mat_tv(wa[i], wb[i])
        o = [mat_tv(wa[i], wa[idx[j]]) for j in opp[k][0]] + \
            [mat_tv(wb[i], wb[idx[j]]) for j in opp[k][1]]
        ds.append(d)
        bs.append(statistics.mean(o))
    return [d - b for d, b in zip(ds, bs)], statistics.mean(ds), statistics.mean(bs)


def sign_perm_p(vals, rng, n_perm=N_PERM):
    obs = statistics.mean(vals)
    hits = sum(1 for _ in range(n_perm)
               if abs(statistics.mean(v if rng.random() < .5 else -v for v in vals)) >= abs(obs))
    return obs, (hits + 1) / (n_perm + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=800)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()
    N = a.seeds

    tasks = [(vi, w, fo, s0, min(CHUNK, N - s0))
             for vi in range(len(VARIANTS))
             for w in (WA, WB)
             for fo in (False, True)
             for s0 in range(0, N, CHUNK)]

    print(f"Rule 48 discriminative test  {len(VARIANTS)} variants × 2 worlds × 2 architectures × {N} seeds "
          f"× {TOTAL} days   processes {a.workers}")
    store, t0 = {}, time.time()
    for key in [(vi, w, fo) for vi in range(len(VARIANTS))
                for w in (WA, WB) for fo in (False, True)]:
        store[key] = [None] * N
    with mp.Pool(a.workers) as pool:
        for k, (key, s0, res) in enumerate(pool.imap_unordered(evaluate, tasks), 1):
            store[key][s0:s0 + len(res)] = res
            if k % 20 == 0 or k == len(tasks):
                el = time.time() - t0
                print(f"  {k}/{len(tasks)}  elapsed {el/60:.1f}min  "
                      f"remaining ~{el/k*(len(tasks)-k)/60:.1f}min", flush=True)

    for floor_off in (False, True):
        arch = "all floors off (the contamination source of rule 44)" if floor_off else "full architecture"
        print("\n" + "=" * 100)
        print(f" Rule 48 discriminative test · {arch} · N={N} · 60-day window")
        print("=" * 100)

        own = {vi: [i for i in range(N)
                    if store[(vi, WA, floor_off)][i] is not None
                    and store[(vi, WB, floor_off)][i] is not None]
               for vi in range(len(VARIANTS))}
        common = sorted(set.intersection(*(set(v) for v in own.values())))
        n_c = len(common)
        print(f"\n  Surviving seeds of each variant on its own: " +
              "  ".join(f"{VARIANTS[vi][0]}={len(own[vi])}" for vi in own))
        print(f"  Common seed set (all variants × both worlds alive): n={n_c}"
              f" ({n_c/N:.1%})")
        if n_c < 50:
            print("  ⚠ common set too small, skipping")
            continue

        # ③ Fixed opponent indices: every variant shares the same sample
        opp = build_opp(n_c, random.Random(20260815))

        rows = []
        for vi, (label, *_) in enumerate(VARIANTS):
            wa, wb = store[(vi, WA, floor_off)], store[(vi, WB, floor_off)]
            # The size of the "own set" differs per variant, so each must draw its own (one of the flaws of the §3g convention)
            d_own, num_o, den_o = deltas_on(
                own[vi], wa, wb, build_opp(len(own[vi]), random.Random(999)))
            d_com, num_c, den_c = deltas_on(common, wa, wb, opp)
            rows.append((label, len(own[vi]), num_o / den_o,
                         d_com, num_c / den_c))

        base_d = rows[0][3]
        print(f"\n  {'fix':<18}{'own set n':>11}{'ratio (own set)':>17}"
              f"{'ratio (common set)':>20}{'mean δ':>10}{'Δ vs status quo':>17}{'dz':>7}{'p':>9}")
        print("  " + "-" * 96)
        prng = random.Random(777)
        for label, n_own, r_own, d_com, r_com in rows:
            dm = statistics.mean(d_com)
            if label == "status quo":
                print(f"  {label:<14}{n_own:>8}{r_own:>14.3f}{r_com:>14.3f}"
                      f"{dm:>10.4f}{'—':>10}{'—':>7}{'—':>9}")
                continue
            diff = [x - y for x, y in zip(d_com, base_d)]
            obs, p = sign_perm_p(diff, prng)
            sd = statistics.stdev(diff)
            dz = obs / sd if sd else 0.0
            star = "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else "n.s."
            print(f"  {label:<14}{n_own:>8}{r_own:>14.3f}{r_com:>14.3f}"
                  f"{dm:>10.4f}{obs:>+10.4f}{dz:>7.2f}{p:>9.4f} {star}")

        print(f"\n  \"own set\" = the §3g convention (each variant's own survivors, mixed with the selection effect)")
        print(f"  \"common set\" = the same {n_c} seeds throughout, differing only in the condition rule itself")
        print(f"  Δ vs status quo = mean of the per-seed paired differences, {N_PERM} sign permutations")
        print(f"  ★ Reading ★ still significantly positive on the common set → rule 48 holds (a real effect)")
        print(f"            zeroed out on the common set → the \"surprise\" of §3g was a selection effect and rule 48 is withdrawn")


def build_opp(n, rng):
    out = []
    for k in range(n):
        pick = lambda: [(lambda j: j if j < k else j + 1)(rng.randrange(n - 1))
                        for _ in range(BASE_K)]
        out.append((pick(), pick()))
    return out


if __name__ == "__main__":
    mp.freeze_support()
    main()
