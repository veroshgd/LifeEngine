"""
028 frozen-transform transport rehearsal — ★purely a group-blind engineering check★
===================================================================================

Run:  python transport028.py            (seeds 10000–11499)

★★ Strict boundaries (this script does **none** of the following) ★★
    ✗ read the rich/poor label       ✗ compute the task effect of A/B/C
    ✗ run H1 / H2 / G / RB           ✗ refit the OLS
    ✗ recompute the empirical CDF    ✗ re-rank-normalise on this batch of agents

**It only treats `interface028_frozen.json` as a fixed function and applies it to an independent population.**

--------------------------------------------------------------------------
★ Convention: out-of-support must be checked on the **input** side, not on the beta output ★
--------------------------------------------------------------------------------------------
The mapped beta is already pinned inside A's support by the frozen empirical mapping,
**so it cannot tell you anything about how much extrapolation occurred**.
What must be checked is the **out-of-range share of the raw readout relative to the frozen calibration quantiles**.

Plus **boundary mass**: how many mapped betas are exactly equal to the frozen `beta_min` / `beta_max`.
Even with few raw values out of range, a large pile-up of new observations at the boundary still makes
quantile mapping produce noticeable **distribution compression**.

--------------------------------------------------------------------------
★ This script does not set the validity rule ★
----------------------------------------------
First observe the actual drift when the frozen transform is transported naturally to an independent population,
**then** (before seeing any 028 outcome) freeze the two gates:

    support gate            bounds the share outside the frozen domain / the boundary pile-up
    budget-transport gate   bounds |μ_j − μ_A| and |SD_j − SD_A|

The two cannot be merged into one number: an arm may have almost full support coverage yet still drift in SD
after mapping because the new population's rank density changed, and vice versa.

⚠ If a gate fails in the final run, **the mapping must not be re-estimated**; the only options are:
  *frozen coupling normalization did not transport adequately to the
  confirmatory population; breadth contrast is not cleanly interpretable
  under the preregistered equal-budget assumption.*
"""

import multiprocessing as mp
import os
import statistics as st
import sys

import interface028 as IF
import novel_task as NT

WA, WB = "rich world", "barren world"
SEED0, N = 10000, 1500          # the 021 holdout set: burned, and **not used in 028 calibration**
CHUNK = 25


def task(job):
    """★Returns only the trait triple, with no world label whatsoever★"""
    world, seed0, n = job
    import novel_situation as NS
    sim = NS.sim
    sim.COND_RECOVER_AT = 65.0
    sim.COND_DEADZONE_RECOVER = sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    out = []
    for s in range(seed0, seed0 + n):
        life = NS.scenarios.make(s, world)
        ok, _ = NS.run_window(life, 0, 30)
        if not ok:
            continue
        w = sim.World(s, **NS.scenarios.WORLDS["baseline"])
        ok, _ = NS.run_window(life, 30, 30, world=w)
        if not ok:
            continue
        NS.level_state(life.agent)
        t = life.agent.traits
        out.append([t["curiosity"], t["caution"], t["industry"]])
    return out


def _dispatch(j):
    return task(j[1])


def main():
    workers = max(1, (os.cpu_count() or 2) - 2)
    jobs = [(task, (w, s0, min(CHUNK, SEED0 + N - s0)))
            for w in (WA, WB) for s0 in range(SEED0, SEED0 + N, CHUNK)]
    pool = []
    with mp.Pool(workers) as p:
        for recs in p.imap_unordered(_dispatch, jobs):
            pool.extend(recs)
    for r in pool[:100]:
        assert isinstance(r, list) and len(r) == 3, "✗ group-blindness broken"
    n = len(pool)

    print("=" * 104)
    print(f" 028 frozen-transform transport rehearsal (★group-blind★)")
    print(f" transport population: seeds {SEED0}–{SEED0+N-1}"
          f" (burned, not used in 028 calibration)  n={n}")
    print(f" frozen: sha256 {IF.F['sha256'][:16]}…  n_cal={IF.F['n_cal']}"
          f"  task fingerprint {IF.F['task_fingerprint']}")
    print("=" * 104)

    traits = [{"curiosity": p[0], "caution": p[1], "industry": p[2]}
              for p in pool]
    bmin, bmax = IF._BETA_A[0], IF._BETA_A[-1]

    # Arm A: the reference of the real transport population
    bA = [IF.beta_for("A", t) for t in traits]
    muA, sdA = st.mean(bA), st.stdev(bA)
    print(f"\n  [arm A reference] (the original 027 interface, not passing through 028's mapping)")
    print(f"    mean {muA:.6f}   SD {sdA:.6f}   min {min(bA):.6f}   max {max(bA):.6f}")
    print(f"    compared with A on calibration: mean {st.mean(IF._BETA_A):.6f}"
          f"   SD {st.stdev(IF._BETA_A):.6f}")

    print(f"\n  [transport diagnostics per arm] frozen support = "
          f"[{bmin:.6f}, {bmax:.6f}]")
    print(f"  {'arm':<5}{'raw<min':>9}{'raw>max':>9}{'out total':>11}"
          f"{'boundary mass':>15}{'mean':>10}{'SD':>10}{'Δmean':>10}{'ΔSD':>10}")
    print("  " + "-" * 92)

    rows = []
    for arm, key, rev in (("Bp", "B", False), ("Bm", "B", True),
                          ("Cp", "Cp", False), ("Cm", "Cm", False)):
        ref = IF.F["x_sorted"][key]
        raws = [IF.raw_readout(t)[key if key != "B" else "B"] for t in traits]
        below = sum(1 for x in raws if x < ref[0]) / n
        above = sum(1 for x in raws if x > ref[-1]) / n
        b = [IF.beta_for(arm, t) for t in traits]
        bound = sum(1 for v in b if v == bmin or v == bmax) / n
        mu, sd = st.mean(b), st.stdev(b)
        rows.append((arm, below, above, below + above, bound, mu, sd,
                     mu - muA, sd - sdA))
        print(f"  {arm:<5}{below:>9.2%}{above:>9.2%}{below+above:>10.2%}"
              f"{bound:>10.2%}{mu:>10.6f}{sd:>10.6f}"
              f"{mu-muA:>+10.6f}{sd-sdA:>+10.6f}")

    print(f"\n  Note: Bp / Bm share the same raw input (x_B⊥), so their out-of-range shares are equal;")
    print(f"        they differ in mapping direction, hence in boundary mass and distribution position.")

    print("\n" + "=" * 104)
    print(" Measurements for reference when freezing the gates (★this script sets no threshold★)")
    print("=" * 104)
    print(f"  largest out-of-range total  {max(r[3] for r in rows):.2%}")
    print(f"  largest boundary mass       {max(r[4] for r in rows):.2%}")
    print(f"  largest |Δmean|             {max(abs(r[7]) for r in rows):.6f}"
          f"   (relative to A's SD = {max(abs(r[7]) for r in rows)/sdA:.1%})")
    print(f"  largest |ΔSD|               {max(abs(r[8]) for r in rows):.6f}"
          f"   (relative to A's SD = {max(abs(r[8]) for r in rows)/sdA:.1%})")
    print("\n  → On this basis, **before seeing any 028 outcome**, freeze:")
    print("     ① support gate           upper bound on the out-of-range share / boundary pile-up")
    print("     ② budget-transport gate  upper bound on |μ_j − μ_A| and |SD_j − SD_A|")


if __name__ == "__main__":
    mp.freeze_support()
    sys.stdout.reconfigure(encoding="utf-8")
    main()
