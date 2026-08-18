"""
⚠ RETIRED — experiment 026 Probe C, intervention saturates at 75–85% (rule 70). Kept as evidence of a negative result; --test is still the regression test for rule 72.
Probe C "home falls into disrepair" group-blind κ calibration
=============================================================

Run:  python novel_calibrate3.py --seeds 300

Mechanism: each explore causes an "unmaintained" shelter loss of κ (hard floor 40);
`build` still repairs under the original v3 rule. **The background worlds of the ON and OFF arms
are fully isomorphic** (both use `storm_chance = 0`), and the only difference is κ.

Theory chain:
    explore → shelter loss → improve_home priority/progress → goal persistence/switching → actions

★ So **two layers** of response must be visible ★ (the lesson of A2: a mechanism working mathematically ≠ the behaviour landscape changing)
    the goal layer changed  AND  the action trajectory changed
If shelter really drops but the goal distribution/switching does not move at all → **G1 must not be reached**.

★ group-blind ★ Only pooled quantities and between-individual variance are printed. Seeds `20000+`.
**Do not touch `60000–61499`.**
"""

import argparse
import multiprocessing as mp
import os
import statistics
import time
from collections import Counter

WA, WB, COMMON = "rich world", "barren world", "baseline"
DEV_DAYS, W_CON = 30, 30
W_DEC_GRID = (5, 7, 10, 14)                    # sorted by this first
KAPPA_GRID = (0.05, 0.10, 0.20, 0.40, 0.80)    # then by this
PAIR = ("see_the_world", "improve_home")
CHUNK = 25

# Pass conditions (frozen before the run)
C_DSURV = 0.02        # ① |survival ON−OFF|
C_DPHYS = 2.0         # ① |ON−OFF of hunger / condition| (0–100 scale)
C_SAT = 0.20          # ② Probe-C intervention saturation rate
C_PAIR_BOTH = 0.50    # ③ share that experienced both goals (the already frozen guardrail)
C_PAIR_DAYS = 0.30    # ③ share of goal-days taken by this pair
C_TV_ACT = 0.02       # ④ TV(ON, OFF) of the action distribution
C_TV_GOAL = 0.02      # ⑤ TV(ON, OFF) of the goal distribution — the goal-layer manipulation check
C_SPREAD_REL = 0.70   # ⑥ spread_ON ≥ this fraction × spread_OFF (guards against a collapse of individual variance)


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
        for kap in (0.0,) + KAPPA_GRID:
            c = NS.fork(life, False)
            NS.enter_novel(c)                       # ★clears the intention only★
            w = NS.novel_world(s)                   # ★isomorphic ON/OFF background★
            inf = NS.home_neglect(kap) if kap else None
            # Run day by day and account day by day (run_window only gives a whole-window total, which cannot be cut into a decision window)
            c.world = w
            c.agent.world = w
            day_acts, alive = [], True
            for dd in range(W_CON):
                before = Counter(c.agent.action_log)
                alive, _ = NS.run_window(c, DEV_DAYS + dd, 1,
                                         extra_inf=(inf,) if inf else ())
                day_acts.append(Counter(c.agent.action_log) - before)
                if not alive:
                    break
            ag = c.agent
            # ★Rule 72 fix★ Previously only the whole-window per_hour total was stored, so the
            #   action-side manipulation check used the entire consequence window while the goal side
            #   used the decision window — quantities on two time scales cannot be compared.
            #   Now **per-day** action counts are stored, so any window can be cut.
            per_day = [dict(d) for d in day_acts]
            ctr = dict(inf.counters) if inf else {}
            out.append({
                "kappa": kap, "alive": alive, "per_day": per_day,
                "goals": list(ag.goal_by_day[DEV_DAYS:DEV_DAYS + W_CON]),
                "hunger": ag.hunger, "condition": ag.condition,
                "shelter": ag.shelter, "ctr": ctr,
            })
    return out


def _dispatch(j):
    return task(j[1])


def act_share(r, w_dec):
    """★Rule 72★ must be cut by the decision window — the same convention as G1 / the goal side."""
    acc = Counter()
    for d in r["per_day"][:w_dec]:
        acc.update(d)
    tot = sum(acc.values()) or 1
    return {a: v / tot for a, v in acc.items()}, tot


def tv(d0, d1):
    keys = set(d0) | set(d1)
    return 0.5 * sum(abs(d0.get(k, 0) - d1.get(k, 0)) for k in keys)


def evaluate(pool, w_dec, kap, base):
    rs = [r for r in pool if r["kappa"] == kap]
    if not rs:
        return False, {}
    n = len(rs)

    # Action layer
    da = Counter()
    for r in rs:
        for d in r["per_day"][:w_dec]:      # ★rule 72★ same window as the goal side
            da.update(d)
    db = Counter()
    for r in base:
        for d in r["per_day"][:w_dec]:
            db.update(d)
    na, nb = sum(da.values()) or 1, sum(db.values()) or 1
    tv_act = tv({k: v / na for k, v in da.items()}, {k: v / nb for k, v in db.items()})

    # Goal layer (inside the decision window)
    ga, gb = Counter(), Counter()
    for r in rs:
        ga.update(g for g in r["goals"][:w_dec] if g)
    for r in base:
        gb.update(g for g in r["goals"][:w_dec] if g)
    nga, ngb = sum(ga.values()) or 1, sum(gb.values()) or 1
    tv_goal = tv({k: v / nga for k, v in ga.items()},
                 {k: v / ngb for k, v in gb.items()})

    both = sum(1 for r in rs
               if all(g in r["goals"][:w_dec] for g in PAIR)) / n
    pair_days = sum(ga[g] for g in PAIR) / nga

    # Individual variance (explore share)
    def spread(xs):
        v = sorted(xs)
        return v[int(.90 * len(v))] - v[int(.10 * len(v))]
    ex_on = [act_share(r, w_dec)[0].get("explore", 0.0) for r in rs]
    ex_off = [act_share(r, w_dec)[0].get("explore", 0.0) for r in base]
    sp_on, sp_off = spread(ex_on), spread(ex_off)

    # Saturation: ★not the "share of time at the edge" but the "share of explores at which no further loss can be applied"★
    tot_ex = sum(r["ctr"].get("explore", 0) for r in rs)
    sat = sum(r["ctr"].get("saturated", 0) for r in rs) / max(tot_ex, 1)
    clip = sum(r["ctr"].get("clipped", 0) for r in rs) / max(tot_ex, 1)

    surv = sum(r["alive"] for r in rs) / n
    surv0 = sum(r["alive"] for r in base) / len(base)
    m = {
        "n": n, "surv": surv, "dsurv": abs(surv - surv0),
        "dhunger": abs(statistics.mean(r["hunger"] for r in rs)
                       - statistics.mean(r["hunger"] for r in base)),
        "dcond": abs(statistics.mean(r["condition"] for r in rs)
                     - statistics.mean(r["condition"] for r in base)),
        "sat": sat, "clip": clip, "tv_act": tv_act, "tv_goal": tv_goal,
        "both": both, "pair_days": pair_days,
        "sp_on": sp_on, "sp_off": sp_off,
        "sp_rel": (sp_on / sp_off) if sp_off else 0.0,
        "shelter": statistics.mean(r["shelter"] for r in rs),
    }
    m["checks"] = {
        "① physiology≈OFF": m["dsurv"] <= C_DSURV and m["dhunger"] <= C_DPHYS
                     and m["dcond"] <= C_DPHYS,
        "② unsaturated<20%": sat < C_SAT,
        "③ both goals active": both >= C_PAIR_BOTH and pair_days >= C_PAIR_DAYS,
        "④ action landscape moved": tv_act >= C_TV_ACT,
        "⑤ goal layer moved too": tv_goal >= C_TV_GOAL,
        "⑥ variance not collapsed": m["sp_rel"] >= C_SPREAD_REL,
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
    print(f"★ group-blind ★ Probe C \"home falls into disrepair\" κ calibration   seeds {a.seed0}–"
          f"{a.seed0+a.seeds-1}   processes {a.workers}")
    print(f"κ {KAPPA_GRID}   W_dec {W_DEC_GRID}   lexicographic: shortest W_dec first, then smallest κ\n",
          flush=True)

    pool, t0 = [], time.time()
    with mp.Pool(a.workers) as p:
        for k, recs in enumerate(p.imap_unordered(_dispatch, jobs), 1):
            pool.extend(recs)
            if k % 6 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  elapsed {el/60:.1f}min  "
                      f"remaining ~{el/k*(len(jobs)-k)/60:.1f}min", flush=True)
    if not pool:
        raise SystemExit("✗ pool is empty — failure")
    base = [r for r in pool if r["kappa"] == 0.0]

    print("\n" + "=" * 112)
    print(" Saturation curve (★ definition = share of explores at which shelter ≤ 40 already prevents any loss ★)")
    print(" Note: this is **not** 'the share of time shelter sits at 40' — natural decay of 0.35/tick carries")
    print("       shelter below 40, after which Probe C silently expires, and the edge share badly underestimates it.")
    print("=" * 112)
    print(f"  {'κ':>6}{'saturation':>13}{'clipped':>10}{'mean final shelter':>21}")
    for kap in KAPPA_GRID:
        _, m = evaluate(pool, W_DEC_GRID[0], kap, base)
        print(f"  {kap:>6.2f}{m['sat']:>10.1%}{m['clip']:>10.1%}{m['shelter']:>16.1f}")

    print("\n" + "=" * 112)
    print(" Results per cell")
    print("=" * 112)
    print(f"  {'W_dec':>6}{'κ':>6}{'n':>6}{'alive':>8}{'Δphys':>8}{'sat':>8}"
          f"{'both goals':>12}{'pair share':>12}{'action TV':>11}{'goal TV':>9}"
          f"{'var ON/OFF':>12}")
    print("  " + "-" * 108)
    winner = None
    for w_dec in W_DEC_GRID:
        for kap in KAPPA_GRID:
            ok, m = evaluate(pool, w_dec, kap, base)
            print(f"  {w_dec:>6}{kap:>6.2f}{m['n']:>6}{m['surv']:>7.1%}"
                  f"{max(m['dhunger'], m['dcond']):>8.2f}{m['sat']:>8.1%}"
                  f"{m['both']:>8.1%}{m['pair_days']:>8.1%}{m['tv_act']:>8.3f}"
                  f"{m['tv_goal']:>8.3f}{m['sp_rel']:>11.2f}"
                  + ("   ★pass" if ok else ""))
            if ok and winner is None:
                winner = (w_dec, kap, m)

    print("\n" + "=" * 112)
    if winner is None:
        fail = Counter()
        for w_dec in W_DEC_GRID:
            for kap in KAPPA_GRID:
                _, m = evaluate(pool, w_dec, kap, base)
                for k2, v in m["checks"].items():
                    if not v:
                        fail[k2] += 1
        print(" ✗ No (W_dec, κ) satisfies every condition → Probe C is retired; the standards are not relaxed.")
        print("\n Failure counts (diagnostic only, not grounds for relaxing anything):")
        for k2, v in fail.most_common():
            print(f"   {k2:<28} {v}/{len(W_DEC_GRID)*len(KAPPA_GRID)} cells")
        print("\n Reading:")
        print("   goal moved but action TV did not → the goal conflict exists but never reached the policy layer")
        print("   large action TV but saturation/variance/physiology fail → the manipulation is too strong and forces behaviour")
    else:
        w_dec, kap, m = winner
        print(f" ★ Probe C passes ★  W_dec = {w_dec} days   κ = {kap}")
        print(f"   alive {m['surv']:.1%} (Δ{m['dsurv']:.1%})  saturation {m['sat']:.1%}  "
              f"action TV {m['tv_act']:.3f}  goal TV {m['tv_goal']:.3f}  "
              f"variance ratio {m['sp_rel']:.2f}")
        print("   → the first novel environment since four rounds ago that satisfies all of **a new causal")
        print("     structure exists + the agent really responds + no reliance on death + individual differences not flattened**.")
        print("   Next: M0 = familiar actions + goals → a 20000+ decidability rehearsal")
        print("         → NOVEL_PREREGISTRATION → and only at the very end touch 60000–61499.")
    print("=" * 112)


def _regression_rule72():
    """★Regression test for rule 72★ proving the action side really is cut by the decision window.

    Before the fix: `act_share(r, w_dec)` accepted w_dec without using it, and `tv_act` aggregated the
    whole consequence window — so the goal side used the decision window while the action side used the
    whole window, and quantities on two time scales were compared (breaking the window separation of rule 62).
    """
    # Build a 30-day record: the first 5 days all explore, the last 25 all build
    r = {"per_day": [Counter({"explore": 24}) for _ in range(5)]
                    + [Counter({"build": 24}) for _ in range(25)],
         "goals": ["see_the_world"] * 5 + ["improve_home"] * 25,
         "ctr": {}, "alive": True, "hunger": 0, "condition": 0, "shelter": 0,
         "kappa": 1.0}
    d5, _ = act_share(r, 5)
    d30, _ = act_share(r, 30)
    assert abs(d5.get("explore", 0) - 1.0) < 1e-9,         f"✗ w_dec=5 did not take only the first 5 days: {d5}"
    assert d30.get("explore", 0) < 0.2, f"✗ w_dec=30 should be dominated by build: {d30}"
    assert d5 != d30, "✗ act_share is insensitive to w_dec — the rule 72 bug is still there"

    # tv_act must vary with the window too
    base = [{**r, "kappa": 0.0,
             "per_day": [Counter({"build": 24}) for _ in range(30)]}]
    pool = [r] + base
    _, m5 = evaluate(pool, 5, 1.0, base)
    _, m30 = evaluate(pool, 30, 1.0, base)
    assert m5["tv_act"] > m30["tv_act"] + 0.1,         f"✗ tv_act does not vary with the window: w5={m5['tv_act']:.3f} w30={m30['tv_act']:.3f}"
    print("✓ rule 72 regression test passed: the action side and the goal side now use the same decision window")
    print(f"    w_dec=5  explore share {d5.get('explore',0):.3f}  tv_act {m5['tv_act']:.3f}")
    print(f"    w_dec=30 explore share {d30.get('explore',0):.3f}  tv_act {m30['tv_act']:.3f}")


if __name__ == "__main__":
    mp.freeze_support()
    import sys
    if "--test" in sys.argv:
        _regression_rule72()
    else:
        main()
