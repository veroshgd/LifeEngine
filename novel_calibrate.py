"""
⚠ RETIRED — experiment 026 Probes A/B; group-blind calibration failed in every cell (rule 64). Kept as evidence of a negative result.
NOVEL-SITUATION difficulty calibration — ★ group-blind ★
========================================================

Run:  python novel_calibrate.py --probe A --seeds 300
        python novel_calibrate.py --probe B --seeds 300
      python novel_calibrate.py --probe A --seeds 60 --workers 5   (rule 55 self-check)

★★ group-blind here is **structural**, not a matter of discipline ★★
The records returned by a worker **contain no developmental-world field at all** (see `_record()`).
The aggregation function `evaluate()` receives one mixed pool and **physically cannot obtain the labels**;
it is not "we could look but agreed not to". `_assert_blind()` enforces this.

> ### Iron rule (design §6) ###
> When choosing `W_dec` / `S` / `λ`, **it is forbidden to look at which value maximises the rich/poor
> difference** — that is tuning the effect size. This script cannot even compute that quantity.

★ What if no passing parameters are found ★
**Declare the probe's design unclean and produce no parameters.**
**Never lower the 95% / 80% / 10pp standards to rescue it.**
026 measures strategy transfer, not a fresh study of survival selection.

Seeds: `20000+` (the already burned 022 block). **Do not touch `60000–61499`.**
"""

import argparse
import multiprocessing as mp
import os
import time
from collections import Counter

WA, WB, COMMON = "rich world", "barren world", "baseline"
DEV_DAYS = 30           # development period
W_CON = 30              # consequence window (total days spent in the novel world)
W_DEC_GRID = (5, 7, 10, 14)             # decision-window candidates (ascending)
S_GRID = (55.0, 60.0, 65.0, 70.0, 75.0, 80.0)      # Probe A gate (ascending, must be > the levelled shelter=50)
LAM_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0)    # Probe B coupling strength (ascending)
M_MARGIN = 0.05         # margin for strategy classification
CHUNK = 25

# Pass conditions (design §6, frozen before the run)
C_STRAT_LO, C_STRAT_HI = 0.20, 0.80     # ① share of each of the two main strategies
C_SURV_DEC = 0.95                       # ② pooled survival within the decision window
C_SURV_CON = 0.80                       # ③ overall survival within the consequence window
C_EARLY_MAX = 0.50                      # ④ upper bound on those meeting the gate within 5 days (Probe A)
C_GATE_LO, C_GATE_HI = 0.20, 0.80       # ⑤ share meeting the gate before the window ends (Probe A)
C_STRAT_SURV = 0.80                     # ⑥ survival rate of each strategy individually
C_STRAT_SURV_GAP = 0.10                 # ⑥ upper bound on the survival gap between the two strategies
C_MIN_ACTIONS = 120                     # ⑦ total actions per ball
C_BITE_MIN = 0.02                       # ⑧ Probe B only: minimum behavioural change of the coupling relative to λ=0
#     ⚠ ⑧ is my addition for Probe B (④⑤ are gate-specific and Probe B has no gate). **Needs a decision.**


# ---------------------------------------------------------------- worker
def _setup():
    """★Rule 55★ every task sets all globals explicitly, never inheriting them"""
    import novel_situation as NS
    sim = NS.sim
    sim.COND_RECOVER_AT = 65.0
    sim.COND_DEADZONE_RECOVER = 0.0
    sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    return NS


def _record(NS, life, param, gate_S):
    """Run the consequence window of the novel world, recording day by day — ★with no world label whatsoever★"""
    sim = NS.sim
    ag = life.agent
    per_day = []            # per day: (action Counter, gate met?, alive?)
    reached = False
    alive = True
    for day in range(DEV_DAYS, DEV_DAYS + W_CON):
        before = Counter(ag.action_log)
        for t in range(sim.TICKS_PER_DAY):
            life.world.tick(day, t)
            for inf in life.influences:
                inf(life.world, ag, day, t, life.inf_rng)
            ag.tick(day, t)
            if gate_S is not None and ag.shelter >= gate_S:
                reached = True
            if not ag.alive:
                alive = False
                break
        per_day.append((Counter(ag.action_log) - before, reached, alive))
        if not alive:
            break
        ag.daily(day)
    return {
        "param": param,
        "per_day": per_day,
        "alive_con": alive,
        "reached_any": reached,
        "reached_by5": any(r for _, r, _ in per_day[:5]),
        "end_food": ag.inventory["food"], "end_shelter": ag.shelter,
        "end_condition": ag.condition,
    }
    # ★ Note: there is no world / label / developmental-world field here — the structural guarantee of group-blindness


def task(job):
    probe, world, seed0, n = job
    NS = _setup()
    sim = NS.sim
    out = []
    grid = (0.0,) + S_GRID if probe == "A" else (0.0,) + LAM_GRID  # both run one extra "rule off" baseline
    for s in range(seed0, seed0 + n):
        life = NS.scenarios.make(s, world)
        ok, _ = NS.run_window(life, 0, DEV_DAYS)
        if not ok:
            continue                       # balls that died during development do not enter the novel phase
        NS.level_state(life.agent)
        for p in grid:
            c = NS.fork(life, False)
            if probe == "A":
                w = NS.GatedWorld(s, gate_S=p, **NS.scenarios.WORLDS[COMMON])
                c.world = w
                c.agent.world = w
                w.agent = c.agent
                out.append(_record(NS, c, p, p))
            else:
                w = sim.World(s, **NS.scenarios.WORLDS[COMMON])
                c.world = w
                c.agent.world = w
                if p > 0:
                    c.influences = list(c.influences) + [NS.salt_flat(p)]
                out.append(_record(NS, c, p, None))
    return probe, seed0, out


# ---------------------------------------------------------------- aggregation
def _assert_blind(pool):
    """Structural guarantee: the pool must contain no label usable for grouping"""
    banned = {"world", "label", "dev", "development", "history", "rich", "poor",
              "seed", "origin"}
    for r in pool[:50]:
        bad = banned & set(r)
        if bad:
            raise AssertionError(f"✗ group-blindness broken: the records contain {sorted(bad)}")


def _profile(per_day, w_dec):
    """Action shares within the decision window + whether it survived that window"""
    days = per_day[:w_dec]
    alive = len(days) == w_dec and days[-1][2]
    acc = Counter()
    for c, _, _ in days:
        acc.update(c)
    tot = sum(acc.values())
    return acc, tot, alive


def classify(acc, tot, actions):
    if tot == 0:
        return "mixed"
    b = (acc["gather_material"] + acc["build"]) / tot
    e = acc["explore"] / tot
    if b - e >= M_MARGIN:
        return "builder"
    if e - b >= M_MARGIN:
        return "explorer"
    return "mixed"


def evaluate(pool, w_dec, param, actions, probe, base_dist=None):
    """★ Eats only the mixed pool and receives no labels ★ Returns (passed?, metrics dict)"""
    rs = [r for r in pool if r["param"] == param]
    if not rs:
        return False, {"note": "no samples"}

    n = len(rs)
    surv_dec = strat = 0
    cls, acc_all = [], Counter()
    for r in rs:
        acc, tot, alive = _profile(r["per_day"], w_dec)
        surv_dec += alive
        acc_all.update(acc)
        cls.append(classify(acc, tot, actions) if alive else None)

    live_cls = [c for c in cls if c is not None]
    nb = sum(1 for c in live_cls if c == "builder")
    ne = sum(1 for c in live_cls if c == "explorer")
    denom = len(live_cls) or 1
    p_b, p_e = nb / denom, ne / denom

    surv_con = sum(r["alive_con"] for r in rs) / n
    sb = [r["alive_con"] for r, c in zip(rs, cls) if c == "builder"]
    se = [r["alive_con"] for r, c in zip(rs, cls) if c == "explorer"]
    sv_b = sum(sb) / len(sb) if sb else 0.0
    sv_e = sum(se) / len(se) if se else 0.0

    tot_all = sum(acc_all.values()) or 1
    dist = {a: acc_all[a] / tot_all for a in sorted(acc_all)}

    m = {
        "n": n, "surv_dec": surv_dec / n, "surv_con": surv_con,
        "p_build": p_b, "p_explore": p_e,
        "sv_build": sv_b, "sv_explore": sv_e, "sv_gap": abs(sv_b - sv_e),
        "reach5": sum(r["reached_by5"] for r in rs) / n,
        "reach_end": sum(r["reached_any"] for r in rs) / n,
        "actions": actions,
    }
    if base_dist is not None:
        keys = set(dist) | set(base_dist)
        m["bite"] = 0.5 * sum(abs(dist.get(k, 0) - base_dist.get(k, 0)) for k in keys)

    checks = {
        "① both strategies 20-80%": C_STRAT_LO <= p_b <= C_STRAT_HI and C_STRAT_LO <= p_e <= C_STRAT_HI,
        "② decision-window survival ≥95%": m["surv_dec"] >= C_SURV_DEC,
        "③ consequence-window survival ≥80%": surv_con >= C_SURV_CON,
        "⑥ strategy survival ≥80%/gap ≤10pp": sv_b >= C_STRAT_SURV and sv_e >= C_STRAT_SURV
                                  and m["sv_gap"] <= C_STRAT_SURV_GAP,
        "⑦ actions ≥120": actions >= C_MIN_ACTIONS,
    }
    if probe == "A":
        checks["④ gate met within 5 days ≤50%"] = m["reach5"] <= C_EARLY_MAX
        checks["⑤ gate met by window end 20-80%"] = C_GATE_LO <= m["reach_end"] <= C_GATE_HI
    else:
        checks["⑧ coupling bites"] = m.get("bite", 0.0) >= C_BITE_MIN
    m["checks"] = checks
    return all(checks.values()), m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", choices=["A", "B"], required=True)
    ap.add_argument("--seeds", type=int, default=300)
    ap.add_argument("--seed0", type=int, default=20000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    grid = S_GRID if a.probe == "A" else LAM_GRID
    name = "S (frozen-ground gate)" if a.probe == "A" else "λ (saline-soil coupling)"
    jobs = [(task, (a.probe, w, s0, min(CHUNK, a.seed0 + a.seeds - s0)))
            for w in (WA, WB)
            for s0 in range(a.seed0, a.seed0 + a.seeds, CHUNK)]
    planned = sum(j[1][3] for j in jobs)
    assert planned == 2 * a.seeds, f"✗ incomplete chunk coverage {planned} ≠ {2*a.seeds}"

    print(f"★ group-blind calibration ★  Probe {a.probe}   {name}")
    print(f"seeds {a.seed0}–{a.seed0+a.seeds-1} (burned block)  two worlds mixed  processes {a.workers}")
    print(f"development {DEV_DAYS} days → levelling → novel {W_CON} days; "
          f"W_dec candidates {W_DEC_GRID}\n", flush=True)

    pool, t0 = [], time.time()
    with mp.Pool(a.workers) as pool_:
        for k, (_, _, recs) in enumerate(pool_.imap_unordered(_dispatch, jobs), 1):
            pool.extend(recs)
            if k % 6 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  elapsed {el/60:.1f}min  "
                      f"remaining ~{el/k*(len(jobs)-k)/60:.1f}min", flush=True)
    if not pool:
        raise SystemExit("✗ pool is empty — this is a failure, not a result")
    _assert_blind(pool)
    print(f"\nMixed pool of {len(pool)} records, group-blind structural check passed\n")

    base = {}
    if a.probe == "B":                       # λ=0 baseline (used only for ⑧)
        rs = [r for r in pool if r["param"] == 0.0]
        acc = Counter()
        for r in rs:
            for c, _, _ in r["per_day"]:
                acc.update(c)
        tot = sum(acc.values()) or 1
        base = {k: v / tot for k, v in acc.items()}

    print("=" * 108)
    print(f" Results per cell (lexicographic: W_dec ascending first, then {name} ascending)")
    print("=" * 108)
    hdr = (f"  {'W_dec':>6}{name[:1]:>7}{'n':>6}{'dec-win alive':>15}{'con-win alive':>15}"
           f"{'builder':>9}{'explorer':>10}{'build alive':>13}{'expl alive':>12}{'gap':>7}")
    hdr += f"{'gate by 5d':>12}{'gate at end':>13}" if a.probe == "A" else f"{'coupling change':>17}"
    print(hdr)
    print("  " + "-" * 110)

    print("  ── baseline: novel rule off (negative control, should reproduce the persistence-phase numbers) ──")
    for w_dec in W_DEC_GRID:
        _, m = evaluate(pool, w_dec, 0.0, w_dec * 24, a.probe, base or None)
        print(f"  {w_dec:>6}{0.0:>7.2f}{m['n']:>6}{m['surv_dec']:>10.1%}"
              f"{m['surv_con']:>10.1%}{m['p_build']:>8.1%}{m['p_explore']:>8.1%}"
              f"{m['sv_build']:>9.1%}{m['sv_explore']:>9.1%}{m['sv_gap']:>7.1%}")
    print("  ── candidate cells ──")

    winner = None
    for w_dec in W_DEC_GRID:
        actions = w_dec * 24
        for p in grid:
            ok, m = evaluate(pool, w_dec, p, actions, a.probe, base or None)
            row = (f"  {w_dec:>6}{p:>7.2f}{m['n']:>6}{m['surv_dec']:>10.1%}"
                   f"{m['surv_con']:>10.1%}{m['p_build']:>8.1%}{m['p_explore']:>8.1%}"
                   f"{m['sv_build']:>9.1%}{m['sv_explore']:>9.1%}{m['sv_gap']:>7.1%}")
            row += (f"{m['reach5']:>9.1%}{m['reach_end']:>9.1%}" if a.probe == "A"
                    else f"{m.get('bite',0):>10.3f}")
            print(row + ("   ★pass" if ok else ""))
            if ok and winner is None:
                winner = (w_dec, p, m)      # first in lexicographic order = the unique solution

    print("\n" + "=" * 108)
    if winner is None:
        print(f" ✗ Probe {a.probe}: no (W_dec, {name[:1]}) combination satisfies every condition.")
        print(" Per design §6: **declare the probe's design unclean and produce no parameters.**")
        print(" ⚠ Never lower the 95% / 80% / 10pp standards to rescue it —")
        print("   026 measures strategy transfer, not a fresh study of survival selection.")
        print("\n Failure counts per condition (diagnostic only, not grounds for relaxing anything):")
        fail = Counter()
        for w_dec in W_DEC_GRID:
            for p in grid:
                _, m = evaluate(pool, w_dec, p, w_dec * 24, a.probe, base or None)
                for k, v in m.get("checks", {}).items():
                    if not v:
                        fail[k] += 1
        for k, v in fail.most_common():
            print(f"   {k:<38} failed {v}/{len(W_DEC_GRID)*len(grid)} cells")
    else:
        w_dec, p, m = winner
        print(f" ★ Frozen parameters (the first passing cell in lexicographic order) ★")
        print(f"   W_dec = {w_dec} days   {name[:1]} = {p}")
        print(f"   decision-window survival {m['surv_dec']:.1%} · consequence-window survival {m['surv_con']:.1%} · "
              f"builder {m['p_build']:.1%} / explorer {m['p_explore']:.1%}")
        print(" Once written into NOVEL_PREREGISTRATION.md they are not changed again.")
    print("=" * 108)


def _dispatch(job):
    fn, args = job
    return fn(args)


if __name__ == "__main__":
    mp.freeze_support()
    main()
