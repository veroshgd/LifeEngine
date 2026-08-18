"""
Behavioural-economy audit — ★ group-blind ★ measure the rates before choosing a new track
=========================================================================================

Run:  python novel_econ_audit.py --seeds 300

★ Why do this first ★
The root cause of Probe A's failure (rule 64) was that I read off the code structure that "explore bypasses
world.food → a second food route exists" **without verifying the rate**. Measured, explore yields 0.14/tick in
expectation while holding hunger steady needs 0.11/tick — a 27% margin, and once sleeping time is deducted the
net balance is negative → the explorers all died.

**The cliff before rule 49 and the frozen ground of rule 64 are the same class of mistake:
inferring "possibility" from structure without measuring "magnitude".**

So before choosing the next track, measure the **actual rates and the spread of individual differences** in each
behavioural economy: which actions in the common garden have both a large enough share and enough
**between-individual variance** to carry a "strategy fork". An action with no variance cannot project individual
differences however novel it is made.

★ group-blind ★ Only pooled quantities and between-individual variance are printed, **never grouped by developmental world**.
Seeds `20000+`. **Do not touch `60000–61499`.**
"""

import argparse
import multiprocessing as mp
import os
import statistics
from collections import Counter

WA, WB, COMMON = "rich world", "barren world", "baseline"
DEV_DAYS, OBS_DAYS = 30, 30
CHUNK = 25


def task(job):
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
        ok, _ = NS.run_window(life, 0, DEV_DAYS)
        if not ok:
            continue
        NS.level_state(life.agent)
        c = NS.fork(life, False)
        w = sim.World(s, **NS.scenarios.WORLDS[COMMON])
        alive, win = NS.run_window(c, DEV_DAYS, OBS_DAYS, world=w)
        acc = Counter()
        for h in win:
            acc.update(h)
        tot = sum(acc.values()) or 1
        # ★ No world label of any kind ★
        out.append({a: acc[a] / tot for a in sim.ACTIONS} | {"_alive": alive})
    return out


def _dispatch(j):
    return task(j[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=300)
    ap.add_argument("--seed0", type=int, default=20000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    jobs = [(task, (w, s0, min(CHUNK, a.seed0 + a.seeds - s0)))
            for w in (WA, WB) for s0 in range(a.seed0, a.seed0 + a.seeds, CHUNK)]
    pool = []
    with mp.Pool(a.workers) as p:
        for recs in p.imap_unordered(_dispatch, jobs):
            pool.extend(recs)
    if not pool:
        raise SystemExit("✗ pool is empty — failure")

    import novel_situation as NS
    acts = NS.sim.ACTIONS
    n = len(pool)
    print("=" * 92)
    print(f" Behavioural-economy audit (group-blind)  common garden {OBS_DAYS} days  "
          f"n={n} (two worlds mixed)  alive {sum(r['_alive'] for r in pool)/n:.1%}")
    print("=" * 92)
    print(f"  {'action':<20}{'mean share':>12}{'between-indiv SD':>18}{'CV':>8}"
          f"{'p10':>8}{'p90':>8}{'p90−p10':>10}{'balls >0':>10}")
    print("  " + "-" * 88)
    rows = []
    for act in acts:
        v = sorted(r[act] for r in pool)
        mu = statistics.mean(v)
        sd = statistics.stdev(v) if len(v) > 1 else 0.0
        p10, p90 = v[int(.10 * len(v))], v[int(.90 * len(v))]
        nz = sum(1 for x in v if x > 0) / len(v)
        cv = sd / mu if mu > 1e-9 else float("nan")
        rows.append((act, mu, sd, cv, p90 - p10, nz))
        print(f"  {act:<18}{mu:>10.3f}{sd:>11.4f}{cv:>10.2f}"
              f"{p10:>8.3f}{p90:>8.3f}{p90-p10:>10.3f}{nz:>9.1%}")

    print("\n  [Reading] An action able to carry a strategy fork must satisfy all of:")
    print("    · a large enough mean share (room to operate)   · a wide enough p90−p10 (real individual differences)")
    print("    · enough balls above 0 (not the preserve of a few)")
    ok = [r for r in rows if r[1] >= 0.05 and r[4] >= 0.05 and r[5] >= 0.5]
    print(f"\n  Actions satisfying all three: {[r[0] for r in ok] or '(none)'}")

    print("\n  ⚠ read's share should be 0 — the baseline world has no books"
          f" (measured {statistics.mean(r['read'] for r in pool):.4f})")
    print("  ⚠ This means: putting books into the novel world is **old experience** for balls raised in the rich world,")
    print("     and **something new** only for balls raised in the barren world — it is not novel to both.")


if __name__ == "__main__":
    mp.freeze_support()
    main()
