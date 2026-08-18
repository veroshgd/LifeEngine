"""
knowledge effective-support audit — ★ group-blind ★ the go/no-go precondition for Probe D
=========================================================================================

Run:  python knowledge_support_audit.py --seeds 300

★ Following the idea of rule 70 ★
Do not ask "does the variable look continuous"; ask **"can a fixed-size external contingency still change a
decision"**. The knowledge distribution is graded (99.7% hold ≥1 entry, 87.8% hold fewer than 4) —
but that is only "looking continuous". What must actually be measured is the **effective support**:

    score(action) += KNOWLEDGE_WEIGHT(12.0) × know(key) × slack     sim.py:835
    propose_goals: pri += KNOWLEDGE_GOAL_WEIGHT(0.25) × know(key)   sim.py:656

So the maximum score amplitude available to an intervention acting on knowledge is **12.0 × strength**.
Whether it can change behaviour depends on **the score gap between top1 and top2 at the moment of decision (the margin)**:

    margin < Δ  →  this decision can be flipped by an intervention of size Δ
    margin ≥ Δ  →  it cannot be moved, and the intervention silently expires (= the saturation of rule 70)

★ Go condition (frozen before the run) ★
There exists a feasible Δ (≤ KNOWLEDGE_WEIGHT = 12.0) such that
**responsive population ∈ [20%, 80%]**
(responsive = at least 10% of that agent's decision ticks can be flipped by Δ)
None found → **Probe D is simply not done and 026 is closed.**

★ Books excluded ★ (rule 67) books exist only in the rich world → count only far_places / shelter / food.
★ group-blind ★ Only pooled quantities are printed. Seeds `20000+`. **Do not touch `60000–61499`.**
"""

import argparse
import multiprocessing as mp
import os
import statistics
from collections import Counter

WA, WB, COMMON = "rich world", "barren world", "baseline"
DEV_DAYS, OBS_DAYS = 30, 30
CHUNK = 25
KEYS = ("far_places", "shelter", "food")      # ★ books excluded ★
DELTAS = (1.0, 3.0, 6.0, 12.0)                # candidate intervention sizes, capped at KNOWLEDGE_WEIGHT
RESP_MIN_FRAC = 0.10                          # an agent counts as responsive only if at least this share of its decisions can be flipped
GATE_LO, GATE_HI = 0.20, 0.80                 # go range for the responsive population


def task(job):
    world, seed0, n = job
    import novel_situation as NS
    sim = NS.sim
    sim.COND_RECOVER_AT = 65.0
    sim.COND_DEADZONE_RECOVER = sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02

    # ★ Read-only probe: wrap score() and record the scores actually computed at each decision ★
    #   score() is never called separately (that could perturb the random stream); the real decision's scores are simply copied out.
    if not hasattr(sim.Agent, "_score_patched"):
        _orig = sim.Agent.score

        def score(self, action, day):
            v = _orig(self, action, day)
            if v is not None:
                self._scores.append(v)
            return v
        sim.Agent.score = score
        sim.Agent._score_patched = True
        sim.Agent._scores = []

    out = []
    for s in range(seed0, seed0 + n):
        life = NS.scenarios.make(s, world)
        ok, _ = NS.run_window(life, 0, DEV_DAYS)
        if not ok:
            continue
        NS.level_state(life.agent)
        c = NS.fork(life, False)
        NS.enter_novel(c)
        w = NS.novel_world(s)
        c.world = w
        c.agent.world = w
        ag = c.agent

        margins, ks_trace = [], []
        for day in range(DEV_DAYS, DEV_DAYS + OBS_DAYS):
            for t in range(sim.TICKS_PER_DAY):
                w.tick(day, t)
                for inf in c.influences:
                    inf(w, ag, day, t, c.inf_rng)
                ag._scores = []
                ag.tick(day, t)
                sc = sorted(ag._scores, reverse=True)
                if len(sc) >= 2:
                    margins.append(sc[0] - sc[1])
                if not ag.alive:
                    break
            if not ag.alive:
                break
            ag.daily(day)
            ks_trace.append({k: ag.knowledge_strength.get(k, 0.0) for k in KEYS})

        out.append({
            "margins": margins,
            "ks_end": {k: ag.knowledge_strength.get(k, 0.0) for k in KEYS},
            "ks_mean": {k: statistics.mean([d[k] for d in ks_trace]) if ks_trace else 0.0
                        for k in KEYS},
            "alive": ag.alive,
        })
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
    n = len(pool)

    print("=" * 100)
    print(f" knowledge effective-support audit (group-blind, books excluded)"
          f"  n={n}  alive {sum(r['alive'] for r in pool)/n:.1%}")
    print("=" * 100)

    print("\n  [1] knowledge_strength distribution (not the count — strength is what enters score())")
    print(f"  {'key':<14}{'share holding it':>18}{'mean strength':>15}{'p10':>8}"
          f"{'p50':>8}{'p90':>8}{'p90−p10':>10}")
    print("  " + "-" * 74)
    for k in KEYS:
        v = sorted(r["ks_mean"][k] for r in pool)
        held = sum(1 for x in v if x > 0) / n
        print(f"  {k:<14}{held:>13.1%}{statistics.mean(v):>10.3f}"
              f"{v[n//10]:>8.3f}{v[n//2]:>8.3f}{v[9*n//10]:>8.3f}"
              f"{v[9*n//10]-v[n//10]:>10.3f}")

    print("\n  [2] decision margin = top1 − top2 (decides whether an intervention can move it)")
    allm = sorted(m for r in pool for m in r["margins"])
    q = lambda p: allm[int(p * len(allm))]
    print(f"    all decision ticks n={len(allm)}   "
          f"p10 {q(.10):.2f}  p25 {q(.25):.2f}  median {q(.50):.2f}  "
          f"p75 {q(.75):.2f}  p90 {q(.90):.2f}")

    print("\n  [3] ★ effective support ★ how many decisions an intervention of size Δ can flip / how many agents it reaches")
    print(f"  {'Δ':>6}{'share of decisions flippable':>30}{'share of responsive agents':>30}{'verdict':>10}")
    print("  " + "-" * 60)
    ok_any = None
    for d in DELTAS:
        flip_all = sum(1 for m in allm if m < d) / len(allm)
        per = [sum(1 for m in r["margins"] if m < d) / len(r["margins"])
               for r in pool if r["margins"]]
        resp = sum(1 for x in per if x >= RESP_MIN_FRAC) / len(per)
        good = GATE_LO <= resp <= GATE_HI
        print(f"  {d:>6.1f}{flip_all:>15.1%}{resp:>21.1%}"
              f"{'  ★pass' if good else '':>10}")
        if good and ok_any is None:
            ok_any = (d, resp)

    print("\n" + "=" * 100)
    if ok_any:
        d, resp = ok_any
        print(f" ★ Go ★ a feasible Δ = {d} exists (≤ KNOWLEDGE_WEIGHT=12.0), "
              f"responsive population = {resp:.1%} ∈ [20%, 80%]")
        print(" → **exactly one** Probe D design family may be designed (the closure rule is in the log).")
    else:
        print(" ✗ No Δ ≤ 12.0 yields a responsive population of 20–80%.")
        print("")
        print(" → **Probe D is not done, and 026 is formally closed.**")
        print(" The conclusion is not 'we failed to think of a good probe' but: **on the usable channels of the")
        print("   current architecture, there is no effective intermediate state able to carry a clean graded novel contingency.**")
        print(" This agrees closely with rule 71 (positive feedback collapses every axis into a bimodal/extreme shape) —")
        print(" the **count** of knowledge entries looks graded, but its **effective support** once it enters the decision is not.")
    print("=" * 100)


if __name__ == "__main__":
    mp.freeze_support()
    main()
