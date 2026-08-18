"""
⚠ RETIRED — experiment 026 Probe A2; the multiplicative bonus came to nothing (rule 68). Kept as evidence of a negative result.
Probe A2 "pathfinding" feasibility calibration — ★ group-blind ★
================================================================

Run:  python novel_calibrate2.py --seeds 300

Mechanism (`novel_situation.discovery_gather`):
    `gather_material` must actually be executed to obtain material;
    **the yield of that gather depends on the share of explore within the last τ ticks** (bonus strength α).
    Pure explore gets no material; pure gather gets it only inefficiently; what benefits is the **temporal combination**.

Rule 65: hunger / condition / food supply are untouched — survival is only a safety check.
Rule 66: built on `explore ↔ gather_material`, the one axis with enough individual variance.
Rule 67: `material` is legal in both developmental worlds (only the rate differs, 2.0 vs 0.5) → equally novel to both.

★ Manipulation check (new this round) ★
If these two quantities do not move once the new rule is on, then **the new rule exists in the code but there is
no new strategy landscape in behaviour**, and the probe is too weak:

    hit rate     share of all gathers that had a preceding explore
    per-gather yield   how much material each gather_material actually returns

★ group-blind ★ Only pooled quantities and between-individual variance are printed, never grouped by developmental world.
Seeds `20000+`. **Do not touch `60000–61499`.**
"""

import argparse
import multiprocessing as mp
import os
import statistics
import time
from collections import Counter, deque

WA, WB, COMMON = "rich world", "barren world", "baseline"
DEV_DAYS, W_CON = 30, 30
TAU_GRID = (6, 12, 24, 48)              # sliding-window length (ticks), ascending
ALPHA_GRID = (0.5, 1.0, 2.0, 4.0)       # bonus strength, ascending
CHUNK = 25

# Pass conditions (frozen before the run). ⚠ The values are my proposal and need a decision.
C_SURV = 0.99            # ① survival in the novel world
C_SURV_DELTA = 0.02      # ① difference from the survival rate with the rule off
C_TERCILE_MIN = 0.25     # ② mean material obtained per tercile ≥ this fraction of the top tercile (nobody gets nothing)
C_TERCILE_RATIO = 4.0    # ② highest/lowest ≤ this (no monopoly)
C_HIT_LO, C_HIT_HI = 0.20, 0.80   # ③ pooled range of the hit rate
C_HIT_SD = 0.10          # ④ between-individual SD of the hit rate (not every ball follows the same sequence)
C_TRAJ_TV = 0.02         # ⑤ pooled action-distribution TV of ON vs OFF
C_YIELD_GAIN = 0.10      # ⑥ minimum improvement of ON's per-gather yield over OFF


def _run(NS, life, tau, alpha):
    """Run the novel window, recording the action each tick — ★with no world label whatsoever★"""
    sim = NS.sim
    ag = life.agent
    infl = list(life.influences)
    if alpha > 0:
        infl.append(NS.discovery_gather(tau, alpha))
    seq, yields = [], []
    alive = True
    for day in range(DEV_DAYS, DEV_DAYS + W_CON):
        for t in range(sim.TICKS_PER_DAY):
            life.world.tick(day, t)
            for inf in infl:
                inf(life.world, ag, day, t, life.inf_rng)
            before = ag.action_log["gather_material"]
            mat_before = ag.inventory["material"]
            yield_now = life.world.p["material_yield"]
            ag._last_act = None
            ag.tick(day, t)
            seq.append(ag._last_act)          # recorded by the act() probe (see the patch inside task)
            if ag.action_log["gather_material"] > before:
                yields.append(ag.inventory["material"] - mat_before)
            if not ag.alive:
                alive = False
                break
        if not alive:
            break
        ag.daily(day)
    return {"seq": seq, "yields": yields, "alive": alive,
            "end_material": ag.inventory["material"]}


def task(job):
    world, seed0, n = job
    import novel_situation as NS
    sim = NS.sim
    sim.COND_RECOVER_AT = 65.0
    sim.COND_DEADZONE_RECOVER = sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02

    # Attach an "action this tick" probe to Agent (read-only recording, no v3 file is modified)
    if not hasattr(sim.Agent, "_probe_patched"):
        _orig_act = sim.Agent.act

        def act(self, action, day, hour=0):
            self._last_act = action
            return _orig_act(self, action, day, hour)
        sim.Agent.act = act
        sim.Agent._probe_patched = True
        sim.Agent._last_act = None

    grid = [(0, 0.0)] + [(t, al) for t in TAU_GRID for al in ALPHA_GRID]
    out = []
    for s in range(seed0, seed0 + n):
        life = NS.scenarios.make(s, world)
        ok, _ = NS.run_window(life, 0, DEV_DAYS)
        if not ok:
            continue
        NS.level_state(life.agent)
        for tau, al in grid:
            c = NS.fork(life, False)
            w = sim.World(s, **NS.scenarios.WORLDS[COMMON])
            c.world = w
            c.agent.world = w
            r = _run(NS, c, tau or 1, al)
            r["param"] = (tau, al)
            out.append(r)
    return out


def _dispatch(j):
    return task(j[1])


def hit_rate(seq, tau):
    """Share of all gather_material actions that had a preceding explore"""
    hist = deque(maxlen=tau)
    hit = tot = 0
    for a in seq:
        if a == "gather_material":
            tot += 1
            hit += 1 if sum(hist) > 0 else 0
        hist.append(1 if a == "explore" else 0)
    return (hit / tot if tot else None), tot


def dist_of(rs):
    acc = Counter()
    for r in rs:
        acc.update(r["seq"])
    tot = sum(acc.values()) or 1
    return {a: acc[a] / tot for a in acc}


def evaluate(pool, tau, alpha, base_rs):
    rs = [r for r in pool if r["param"] == (tau, alpha)]
    if not rs:
        return False, {}
    n = len(rs)
    surv = sum(r["alive"] for r in rs) / n
    surv0 = sum(r["alive"] for r in base_rs) / len(base_rs)

    hits = [h for h, t in (hit_rate(r["seq"], tau) for r in rs) if h is not None]
    hit_mu = statistics.mean(hits) if hits else 0.0
    hit_sd = statistics.stdev(hits) if len(hits) > 1 else 0.0

    y = [v for r in rs for v in r["yields"]]
    y0 = [v for r in base_rs for v in r["yields"]]
    ymu = statistics.mean(y) if y else 0.0
    ymu0 = statistics.mean(y0) if y0 else 0.0

    # Split into terciles by explore share and check whether material acquisition is monopolised by one extreme
    ex = []
    for r in rs:
        tot = len(r["seq"]) or 1
        ex.append((r["seq"].count("explore") / tot, r["end_material"]))
    ex.sort()
    k = max(1, len(ex) // 3)
    terc = [statistics.mean(m for _, m in ex[i * k:(i + 1) * k] or [(0, 0)])
            for i in range(3)]
    tmax, tmin = max(terc), min(terc)

    d, d0 = dist_of(rs), dist_of(base_rs)
    keys = set(d) | set(d0)
    tv = 0.5 * sum(abs(d.get(x, 0) - d0.get(x, 0)) for x in keys)

    m = {"n": n, "surv": surv, "dsurv": abs(surv - surv0), "hit": hit_mu,
         "hit_sd": hit_sd, "yield": ymu, "yield0": ymu0,
         "ygain": (ymu / ymu0 - 1) if ymu0 else 0.0,
         "terc": terc, "tv": tv}
    m["checks"] = {
        "① survival ≥99% and ≈OFF": surv >= C_SURV and m["dsurv"] <= C_SURV_DELTA,
        "② no route monopoly": tmax > 0 and tmin >= C_TERCILE_MIN * tmax
                       and tmax / max(tmin, 1e-9) <= C_TERCILE_RATIO,
        "③ hit rate 20-80%": C_HIT_LO <= hit_mu <= C_HIT_HI,
        "④ hit-rate between-individual SD ≥.10": hit_sd >= C_HIT_SD,
        "⑤ trajectory really changed": tv >= C_TRAJ_TV,
        "⑥ per-gather yield up ≥10%": m["ygain"] >= C_YIELD_GAIN,
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
    print(f"★ group-blind ★ Probe A2 \"pathfinding\" feasibility calibration   seeds {a.seed0}–"
          f"{a.seed0+a.seeds-1}   processes {a.workers}")
    print(f"τ candidates {TAU_GRID}   α candidates {ALPHA_GRID}\n", flush=True)

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
    base_rs = [r for r in pool if r["param"] == (0, 0.0)]

    print("\n" + "=" * 100)
    print(f" Results per cell (lexicographic: τ ascending first, then α)  baseline OFF: survival "
          f"{sum(r['alive'] for r in base_rs)/len(base_rs):.1%}  "
          f"per-gather yield {statistics.mean(v for r in base_rs for v in r['yields']):.3f}")
    print("=" * 100)
    print(f"  {'τ':>4}{'α':>6}{'n':>6}{'alive':>8}{'hit rate':>11}{'hit SD':>9}"
          f"{'yield':>9}{'yield gain':>12}{'traj TV':>9}{'material by explore tercile':>30}")
    print("  " + "-" * 96)

    winner = None
    for tau in TAU_GRID:
        for al in ALPHA_GRID:
            ok, m = evaluate(pool, tau, al, base_rs)
            print(f"  {tau:>4}{al:>6.1f}{m['n']:>6}{m['surv']:>8.1%}{m['hit']:>9.1%}"
                  f"{m['hit_sd']:>9.3f}{m['yield']:>10.3f}{m['ygain']:>+10.1%}"
                  f"{m['tv']:>9.3f}"
                  f"{m['terc'][0]:>9.1f}{m['terc'][1]:>8.1f}{m['terc'][2]:>8.1f}"
                  + ("   ★pass" if ok else ""))
            if ok and winner is None:
                winner = (tau, al, m)

    print("\n" + "=" * 100)
    if winner is None:
        print(" ✗ No (τ, α) combination satisfies every condition → Probe A2's design is unclean; no parameters are produced.")
        print(" ⚠ No standard is lowered to rescue it.")
        fail = Counter()
        for tau in TAU_GRID:
            for al in ALPHA_GRID:
                _, m = evaluate(pool, tau, al, base_rs)
                for k2, v in m["checks"].items():
                    if not v:
                        fail[k2] += 1
        print("\n Failure counts:")
        for k2, v in fail.most_common():
            print(f"   {k2:<38} {v}/{len(TAU_GRID)*len(ALPHA_GRID)} cells")
    else:
        tau, al, m = winner
        print(f" ★ Feasible ★  τ = {tau} ticks   α = {al}")
        print(f"   survival {m['surv']:.1%}  hit rate {m['hit']:.1%} (SD {m['hit_sd']:.3f})"
              f"  per-gather yield {m['yield']:.3f} ({m['ygain']:+.1%})  trajectory TV {m['tv']:.3f}")
        print(" Next: write NOVEL_PREREGISTRATION.md, and only then touch 60000–61499.")
    print("=" * 100)


if __name__ == "__main__":
    mp.freeze_support()
    main()
