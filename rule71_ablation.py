"""
Rule 71 causal ablation — is it one and the same positive feedback that creates persistence and destroys plasticity?
====================================================================================================================

Run:  python rule71_ablation.py --seeds 300

★ The proposition to test (rule 71) ★

> v3's positive feedback (trait drift + goal persistence) pushes the agent towards specialisation,
> every resource axis collapses into "all in / all out", and a graded intervention therefore has no middle ground to act on.
> **The very mechanism that produces persistent individual differences also destroys future plasticity.**

026 only **observed** this correlation (bimodal material, bimodal shelter, near-0/1 knowledge).
This experiment **asks about causality directly**: turn the strength of the positive feedback down and see whether all three move **together**.

★ Why an ablation rather than going straight to v4 ★
v4 would change the model, whereas the ablation asks **inside v3** whether this mechanism really is the cause.
**Scientifically harder, and it does not require revalidating the whole persistence architecture.**

--------------------------------------------------------------------------
★ Prior directional predictions (written before the run, copied verbatim for comparison afterwards) ★

Along `TRAIT_DRIFT` from 0 up to 2.4 (default 1.20), the prediction is:

    (a) persistence      transplant ratio                ↑ monotonically increasing
    (b) specialisation   degree of bimodality in resource state  ↑ monotonically increasing
    (c) plasticity       share of decisions flippable at Δ=3.0   ↓ monotonically decreasing

**All three moving the same way = rule 71 has causal support.**
If (a) rises while (b)(c) do not move → the positive feedback only creates persistence, and
**the half of rule 71 about the "cost" does not hold and must be withdrawn.**

⚠ This is a **mechanistic / exploratory** analysis, not confirmatory:
   it uses the already burned seeds `20000+`, has no preregistration, and its conclusions are phrased as exploratory.
⚠ The Δ=3.0 susceptibility is only a **mechanism probe** (fixed when 026 was closed),
   and **carries no conclusion whatsoever about generalization.**
-----------------------------------------------------------------
"""

import argparse
import multiprocessing as mp
import os
import statistics
from collections import Counter

WA, WB, COMMON = "rich world", "barren world", "baseline"
DEV_DAYS, OBS_DAYS = 30, 30
DRIFT_GRID = (0.0, 0.3, 0.6, 1.2, 2.4)     # 1.20 = the v3 default
DELTA = 3.0                                 # standardised decision perturbation size (frozen when 026 was closed)
CHUNK = 25
BASE_K = 5


def task(job):
    world, drift, seed0, n = job
    import novel_situation as NS
    sim = NS.sim
    # ★Rule 55★ set explicitly
    sim.COND_RECOVER_AT = 65.0
    sim.COND_DEADZONE_RECOVER = sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    sim.TRAIT_DRIFT = drift                 # ★ the positive-feedback gain being ablated ★

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
            out.append(None)
            continue
        snap = [Counter(c) for c in life.agent.action_by_hour]
        w = sim.World(s, **NS.scenarios.WORLDS[COMMON])
        life.world = w
        life.agent.world = w
        ag = life.agent

        margins = []
        alive = True
        for day in range(DEV_DAYS, DEV_DAYS + OBS_DAYS):
            for t in range(sim.TICKS_PER_DAY):
                w.tick(day, t)
                for inf in life.influences:
                    inf(w, ag, day, t, life.inf_rng)
                ag._scores = []
                ag.tick(day, t)
                sc = sorted(ag._scores, reverse=True)
                if len(sc) >= 2:
                    margins.append(sc[0] - sc[1])
                if not ag.alive:
                    alive = False
                    break
            if not alive:
                break
            ag.daily(day)
        if not alive:
            out.append(None)
            continue

        win = [Counter(c) - snap[h] for h, c in enumerate(ag.action_by_hour)]
        mat = []
        for h in win:
            tot = sum(h.values()) or 1
            mat.append(tuple(h[a] / tot for a in sim.ACTIONS))
        tot_w = sum(sum(h.values()) for h in win) or 1
        out.append({
            "mat": tuple(mat),
            "explore": sum(h["explore"] for h in win) / tot_w,
            "shelter": ag.shelter, "material": ag.inventory["material"],
            "flip": sum(1 for m in margins if m < DELTA) / max(len(margins), 1),
            "margin_med": statistics.median(margins) if margins else 0.0,
        })
    return world, drift, seed0, out


def _dispatch(j):
    return task(j[1])


def mat_tv(a, b):
    return sum(0.5 * sum(abs(x - y) for x, y in zip(ha, hb))
               for ha, hb in zip(a, b)) / len(a)


def extremity(vals, lo, hi):
    """Degree of polarisation: the share falling in the outer 5% at each end. ★Only usable for variables with a **fixed range**★"""
    span = hi - lo
    return sum(1 for v in vals
               if v <= lo + 0.05 * span or v >= hi - 0.05 * span) / len(vals)


def poles(vals, lo_th, hi_th):
    """★Measure polarisation with fixed thresholds★ Returns (low extreme, high extreme, middle).

    ⚠ Found during smoke testing: using `extremity(v, 0, max(v))` for material is a **bad metric** —
      the range `max(v)` varies by condition, and material is heavily right-skewed (mostly 0, a few in the hundreds),
      so "within 5% of the range" counts almost everyone as a low extreme (measured 98%, near the ceiling),
      making different drift values incomparable. Switched to **condition-independent fixed thresholds**:
      material < 3 (cannot even afford one build) / > 50 (clearly in surplus).
    """
    n = len(vals) or 1
    lo = sum(1 for v in vals if v < lo_th) / n
    hi = sum(1 for v in vals if v > hi_th) / n
    return lo, hi, 1.0 - lo - hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=300)
    ap.add_argument("--seed0", type=int, default=20000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()
    N = a.seeds

    jobs = [(task, (w, d, s0, min(CHUNK, a.seed0 + N - s0)))
            for d in DRIFT_GRID for w in (WA, WB)
            for s0 in range(a.seed0, a.seed0 + N, CHUNK)]
    print(f"Rule 71 causal ablation   TRAIT_DRIFT {DRIFT_GRID} (default 1.20)"
          f"   seeds {a.seed0}–{a.seed0+N-1}   processes {a.workers}")
    print(f"Δ = {DELTA} (mechanism probe; carries no generalization conclusion)\n", flush=True)

    store = {(w, d): [None] * N for d in DRIFT_GRID for w in (WA, WB)}
    with mp.Pool(a.workers) as p:
        for world, drift, s0, recs in p.imap_unordered(_dispatch, jobs):
            store[(world, drift)][s0 - a.seed0:s0 - a.seed0 + len(recs)] = recs

    import random
    print("=" * 104)
    print(" Rule 71 causal ablation results")
    print("=" * 104)
    print(f"  {'TRAIT_DRIFT':>12}{'n':>6}{'(a) transplant ratio':>22}{'(b) shelter polar.':>20}"
          f"{'(b) material extremes':>23}{'(c) flippable decisions':>25}{'median margin':>15}"
          f"{'material middle':>17}")
    print("  " + "-" * 100)

    rows = []
    for d in DRIFT_GRID:
        ca, cb = store[(WA, d)], store[(WB, d)]
        live = [i for i in range(N) if ca[i] and cb[i]]
        if len(live) < max(20, min(50, N // 3)):   # relax proportionally for small debug samples
            print(f"  {d:>12.2f}{len(live):>6}   ⚠ insufficient effective n")
            continue
        wa = [ca[i]["mat"] for i in live]
        wb = [cb[i]["mat"] for i in live]
        rng = random.Random(777)
        treat = [mat_tv(wa[k], wb[k]) for k in range(len(live))]
        base = []
        for ws in (wa, wb):
            idx = list(range(len(ws)))
            for _ in range(BASE_K):
                rng.shuffle(idx)
                base += [mat_tv(ws[idx[j]], ws[idx[j + 1]])
                         for j in range(0, len(idx) - 1, 2)]
        ratio = statistics.mean(treat) / statistics.mean(base)

        allr = [ca[i] for i in live] + [cb[i] for i in live]
        ex_sh = extremity([r["shelter"] for r in allr], 0, 100)
        m_lo, m_hi, m_mid = poles([r["material"] for r in allr], 3.0, 50.0)
        ex_mt = m_lo + m_hi          # both extremes combined (fixed thresholds, comparable across conditions)
        flip = statistics.mean(r["flip"] for r in allr)
        mmed = statistics.mean(r["margin_med"] for r in allr)
        rows.append((d, ratio, ex_sh, ex_mt, flip, mmed, m_mid))
        print(f"  {d:>12.2f}{len(live):>6}{ratio:>13.3f}{ex_sh:>15.1%}"
              f"{ex_mt:>16.1%}{flip:>14.1%}{mmed:>12.2f}{m_mid:>12.1%}")

    print("\n" + "=" * 104)
    print(" Comparison with the prior predictions (written at the head of this script before the run)")
    print("=" * 104)
    if len(rows) >= 3:
        # ★ Report both the **full-grid endpoints** and the **realistic range 0→default 1.2** ★
        #   The prediction says "monotone along 0→2.4", so the verdict uses the full grid;
        #   the realistic range is reported separately but **may only be used descriptively, never to rescue the prediction**.
        r0, r1 = rows[0], rows[-1]
        rd = next((r for r in rows if r[0] == 1.2), None)
        if rd:
            print(f"  [realistic range drift 0.0 → 1.2 (the v3 default)] exploratory description, not the basis of the verdict")
            print(f"    (a) {r0[1]:.3f} → {rd[1]:.3f}   (b)shelter {r0[2]:.1%} → {rd[2]:.1%}"
                  f"   (c) {r0[4]:.1%} → {rd[4]:.1%}")
            print()
        def arrow(a_, b_):
            return "↑" if b_ > a_ else ("↓" if b_ < a_ else "→")
        print(f"  drift {r0[0]} → {r1[0]}")
        print(f"    (a) transplant ratio, persistence  {r0[1]:.3f} → {r1[1]:.3f}  "
              f"{arrow(r0[1], r1[1])}   predicted ↑")
        print(f"    (b) shelter polarisation           {r0[2]:.1%} → {r1[2]:.1%}  "
              f"{arrow(r0[2], r1[2])}   predicted ↑")
        print(f"    (b) material polarisation          {r0[3]:.1%} → {r1[3]:.1%}  "
              f"{arrow(r0[3], r1[3])}   predicted ↑")
        print(f"    (c) flippable decisions, plasticity {r0[4]:.1%} → {r1[4]:.1%}  "
              f"{arrow(r0[4], r1[4])}   predicted ↓")
        ok = (r1[1] > r0[1]) and (r1[2] > r0[2] or r1[3] > r0[3]) and (r1[4] < r0[4])
        print()
        if ok:
            print("  ★ All three move together → rule 71 has causal support:")
            print("    one and the same positive feedback creates persistence and destroys plasticity.")
        else:
            print("  ✗ The three do not move together → **the half of rule 71 about the 'cost' does not hold and should be withdrawn or rewritten.**")
            print("    (If (a) rises while (b)(c) stay put → the positive feedback only creates persistence.)")
    print("=" * 104)


if __name__ == "__main__":
    mp.freeze_support()
    main()
