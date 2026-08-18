"""
Experiment 027 group-blind calibration — freezing β / α / τ
===========================================================

Run:  python novel_calibrate027.py --seeds 300

★★ group-blindness here is structural ★★
The worker returns only `novelty_style` (a scalar in [0,1]) and the seed,
**with no developmental-world label**. What `evaluate()` receives is one mixed pool,
and it **physically cannot compute a rich/poor difference**. `_assert_blind()` enforces this.

> ### Iron rule ###
> "β=0.1 gives no significant rich/poor difference, β=0.3 does → use 0.3" must never happen.
> This script cannot even compute that quantity.

★ Efficiency ★ The 60 days of development are independent of (α, β) → run them once, extract each ball's
`novelty_style`, and the whole grid becomes pure arithmetic, finishing in seconds.

★ Pass conditions (frozen before the run) ★
  ① both options are chosen during the learning phase (★within-individual★ share of the rarer option ≥ 5%)
  ② accuracy on trials 31–40 ∈ [65%, 90%]        the rule is learnable but not saturated
  ③ share already switched within 10 trials of the reversal ∈ [20%, 80%]  neither instant nor impossible
  ④ accuracy on trials 71–80 ∈ [65%, 90%]        the reversal is learnable

★ Selection order (lexicographic, frozen before the run) ★ **β ascending → α ascending → τ ascending**, taking the first passing cell.
  β comes first because it is the **only knob through which history enters**,
  and **taking the smallest = the least likely to manufacture an effect** (the most conservative direction).

Seeds: `20000+` (a burned block). **Do not touch `60000–61499`.**
"""

import argparse
import multiprocessing as mp
import os
import statistics
from collections import Counter

import novel_task as NT

WA, WB = "rich world", "barren world"
ALPHA_GRID = (0.05, 0.10, 0.20, 0.40)
BETA_GRID = (0.05, 0.10, 0.20, 0.30, 0.50)
TAU_GRID = (0.02, 0.05, 0.10, 0.20)
CHUNK = 25

C_MIN_SHARE = 0.05                 # ① lower bound on the ★within-individual★ share of the rarer option (not pooled)
C_LEARN_LO, C_LEARN_HI = 0.65, 0.90   # ② trial 31–40
C_SWITCH_LO, C_SWITCH_HI = 0.20, 0.80  # ③ share switching within 10 trials of the reversal
C_RELEARN_LO, C_RELEARN_HI = 0.65, 0.90  # ④ trial 71–80


def task(job):
    """Run the 60-day v3 core and return only the **unlabelled** novelty_style + seed"""
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
        NS.level_state(life.agent)          # level the body state before entering the task
        # ★ Only these two are returned — no world label ★
        out.append({"seed": s, "ns": NT.novelty_style(life.agent)})
    return out


def _dispatch(j):
    return task(j[1])


def _assert_blind(pool):
    banned = {"world", "label", "dev", "development", "history", "rich", "poor"}
    for r in pool[:50]:
        bad = banned & set(r)
        if bad:
            raise AssertionError(f"✗ group-blindness broken: {sorted(bad)}")


class _Stub:
    """A minimal agent carrying traits only — the calibration stage needs no real agent object"""
    def __init__(self, ns):
        # Solve back for a (curiosity, caution) pair making novelty_style exactly ns
        self.traits = {"curiosity": 50.0 + (ns - 0.5) * 100.0,
                       "caution": 50.0 - (ns - 0.5) * 100.0,
                       "industry": 50.0}


def evaluate3(pool, alpha, beta, tau):
    recs = [NT.run_task(_Stub(r["ns"]), r["seed"], alpha=alpha, beta=beta,
                        tau=tau) for r in pool]
    n = len(recs)

    # ★Correction★ criterion ① must be computed **within individuals**. Pooled is an illusion:
    #   half the seeds have A good and half B, so mixed together it is always near 50/50,
    #   making the criterion impossible either to pass or to fail (measured at a constant 48.7%).
    per = [min(r["choices"][:NT.REVERSAL_AT].count(0),
               r["choices"][:NT.REVERSAL_AT].count(1)) / NT.REVERSAL_AT
           for r in recs]
    min_share = statistics.mean(per)

    learn = statistics.mean(NT.correct_rate(r, 30, 40) for r in recs)
    relearn = statistics.mean(NT.correct_rate(r, 70, 80) for r in recs)
    lat = [NT.switch_latency(r) for r in recs]
    switched10 = sum(1 for x in lat if x is not None and x <= 10) / n
    never = sum(1 for x in lat if x is None) / n

    m = {"n": n, "min_share": min_share, "learn": learn, "relearn": relearn,
         "switched10": switched10, "never": never,
         "explore_early": statistics.mean(NT.explore_rate(r, 0, 10) for r in recs),
         "lat_med": statistics.median([x for x in lat if x is not None] or [0])}
    m["checks"] = {
        "① both options chosen": min_share >= C_MIN_SHARE,
        "② 31-40 accuracy 65-90%": C_LEARN_LO <= learn <= C_LEARN_HI,
        "③ switch within 10 trials of reversal 20-80%": C_SWITCH_LO <= switched10 <= C_SWITCH_HI,
        "④ 71-80 accuracy 65-90%": C_RELEARN_LO <= relearn <= C_RELEARN_HI,
    }
    return all(m["checks"].values()), m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=300)
    ap.add_argument("--seed0", type=int, default=20000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    jobs = [(task, (w, s0, min(CHUNK, a.seed0 + a.seeds - s0)))
            for w in (WA, WB) for s0 in range(a.seed0, a.seed0 + a.seeds, CHUNK)]
    print(f"★ group-blind ★ 027 calibration   seeds {a.seed0}–{a.seed0+a.seeds-1}"
          f"   processes {a.workers}")
    print(f"α {ALPHA_GRID}   β {BETA_GRID}   lexicographic: β ascending → α ascending → τ ascending\n",
          flush=True)

    pool = []
    with mp.Pool(a.workers) as p:
        for recs in p.imap_unordered(_dispatch, jobs):
            pool.extend(recs)
    if not pool:
        raise SystemExit("✗ pool is empty — failure")
    _assert_blind(pool)
    ns = sorted(r["ns"] for r in pool)
    print(f"Mixed pool of {len(pool)} balls (group-blind check passed)")
    print(f"novelty_style distribution: p10 {ns[len(ns)//10]:.3f}  median {ns[len(ns)//2]:.3f}"
          f"  p90 {ns[9*len(ns)//10]:.3f}\n")

    print("=" * 110)
    print(f"  {'β':>6}{'α':>6}{'τ':>6}{'within-indiv rarer share':>26}{'31-40 correct':>15}"
          f"{'switch within 10':>18}{'71-80 correct':>15}{'never switched':>16}{'median latency':>16}")
    print("  " + "-" * 106)
    winner, rows = None, []
    for be in BETA_GRID:                     # ★β first: weakest history channel first★
        for al in ALPHA_GRID:
            for ta in TAU_GRID:
                ok, m = evaluate3(pool, al, be, ta)
                rows.append((be, al, ta, ok, m))
                if ok or m["checks"]["② 31-40 accuracy 65-90%"]:
                    print(f"  {be:>6.2f}{al:>6.2f}{ta:>6.2f}{m['min_share']:>15.1%}"
                          f"{m['learn']:>11.1%}{m['switched10']:>13.1%}"
                          f"{m['relearn']:>11.1%}{m['never']:>10.1%}"
                          f"{m['lat_med']:>16.0f}" + ("   ★pass" if ok else ""))
                if ok and winner is None:
                    winner = (be, al, ta, m)
    print(f"  (only cells that already passed ② are listed; {len(rows)} cells scanned in total)")

    print(chr(10) + "=" * 110)
    if winner is None:
        fail = Counter()
        for be, al, ta, ok, m in rows:
            for k, v in m["checks"].items():
                if not v:
                    fail[k] += 1
        print(" ✗ No (β, α, τ) satisfies every condition → the task parameterisation fails; no parameters are produced.")
        print("   ⚠ No standard is relaxed. Any change must be to the task **design** itself, followed by a fresh calibration.")
        print(chr(10) + " Failure counts:")
        for k, v in fail.most_common():
            print(f"   {k:<44} {v}/{len(rows)} cells")
    else:
        be, al, ta, m = winner
        print(f" ★ Frozen ★  β = {be}   α = {al}   τ = {ta}")
        print(f"   within-individual rarer share {m['min_share']:.1%} · 31–40 accuracy {m['learn']:.1%}")
        print(f"   switched within 10 trials of the reversal {m['switched10']:.1%} · "
              f"71–80 accuracy {m['relearn']:.1%}")
        print(f"   median switch latency {m['lat_med']:.0f} trials · never switched {m['never']:.1%}")
        print(" → Once written into NOVEL_TASK_PREREGISTRATION.md they are not changed again.")
    print("=" * 110)


if __name__ == "__main__":
    mp.freeze_support()
    main()
