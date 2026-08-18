"""
v3 novel-probe capacity audit — scanning every existing channel against one set of eligibility standards
========================================================================================================

Run:  python novel_capacity_audit.py --seeds 300

★ Why do this ★
Three probes failed in a row, each for a different reason:
  Probe A frozen ground  → survival split (rule 64: touching food can only produce a life/death difference)
  Probe B saline soil    → survival split (same, opposite direction)
  Probe A2 pathfinding   → the multiplicative bonus came to nothing (rule 68: 77% of balls never gather, so it multiplies zero)

**Hunting for a fourth probe by intuition is pointless.** Instead: scan every existing behavioural channel of v3
against **one common set of eligibility standards** and see whether any channel qualifies.

★ Eligibility standards (six; all must pass) ★
  Q1 nearly everyone can take part   participation ≥ 70%                (rule 68)
  Q2 enough individual difference    between-individual p90−p10 ≥ 0.10   (rule 66)
  Q3 genuinely a binding constraint  ≥ 20% of individuals really limited by it  (the other half of rule 68)
  Q4 does not decide life or death   manipulating it does not change survival  (rule 65)
  Q5 has a read-back path            enters score() / goal, so behaviour can change (the reactive path)
  Q6 equally accessible in both worlds  the affordance exists in both during development  (rule 67)

Q1–Q3 are measured; Q4–Q6 are decided from the code structure (the basis is noted per entry in CHANNELS).

★ group-blind ★ Only pooled quantities and between-individual variance are printed. Seeds `20000+`.
**Do not touch `60000–61499`.**

★ How to use the conclusion ★
- Some channel passes everything → that is where the fourth probe should be built
- **None passes → 026 is closed with "v3 lacks an action economy in which generalization can be tested cleanly"**,
  and the design goal of v4 becomes very clear: not "make the model more complex" but
  close the gap these three rounds exposed — **at least one economy that does not decide life or death, that
  nearly everyone can take part in, that admits several effective strategies, and that lets the agent adapt behaviourally to a new contingency.**
"""

import argparse
import multiprocessing as mp
import os
import statistics
from collections import Counter

WA, WB, COMMON = "rich world", "barren world", "baseline"
DEV_DAYS, OBS_DAYS = 30, 30
CHUNK = 25

# (channel, Q4 does not decide life/death?, Q5 has a read-back path?, Q6 equally accessible in both worlds?, basis)
STRUCTURAL = {
    "sleep / energy": (
        False, True, True,
        "energy is tied to condition via SLEEP_EFF_FLOOR → touches the life/death path (Q4 doubtful, needs a decision)"),
    "explore / non-food output": (
        True, True, True,
        "flag/knowledge/trait feedback enters score(); explore is available in both worlds"),
    "material / build": (
        True, True, True,
        "inventory feeds goal progress; both worlds have material_yield (2.0 vs 0.5)"),
    "goal structure": (
        True, True, True,
        "goal enters score() directly; both worlds share the same GOAL_ACTIONS"),
    "knowledge": (
        True, True, True,
        "022 already wired into score(); but books exist only in the rich world → see the Q6 measurement below"),
    "shelter / storm": (
        False, True, True,
        "low shelter → the condition-damage path; storm_chance differs between the worlds (0.02/0.1)"),
    "objects / action legality": (
        True, True, False,
        "★Q6 fails★ read requires a book, and books exist only in the rich world → not equally novel to both groups"),
}


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
        lo_energy = [0]

        alive, win = NS.run_window(c, DEV_DAYS, OBS_DAYS, world=w)
        ag = c.agent
        acc = Counter()
        for h in win:
            acc.update(h)
        tot = sum(acc.values()) or 1
        goals = [g for g in ag.goal_by_day[DEV_DAYS:] if g]
        gc = Counter(goals)
        out.append({
            "sleep": acc["sleep"] / tot,
            "explore": acc["explore"] / tot,
            "gather_material": acc["gather_material"] / tot,
            "build": acc["build"] / tot,
            "read": acc["read"] / tot,
            "energy_end": ag.energy,
            "material_end": ag.inventory["material"],
            "shelter_end": ag.shelter,
            "n_flags": len(ag.flags),
            "has_explore_flag": int("loves_exploring" in ag.flags),
            "n_knowledge": len(ag.knowledge),
            "n_goal_kinds": len(gc),
            "top_goal_share": (max(gc.values()) / len(goals)) if goals else 0.0,
            "alive": alive,
        })
    return out


def _dispatch(j):
    return task(j[1])


def spread(vals):
    v = sorted(vals)
    return v[int(.90 * len(v))] - v[int(.10 * len(v))]


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

    def frac(f):
        return sum(1 for r in pool if f(r)) / n

    # ── Q1 participation / Q2 individual variance / Q3 binding constraint, per channel ──
    meas = {
        "sleep / energy": (
            frac(lambda r: r["sleep"] > 0),
            spread([r["sleep"] for r in pool]),
            frac(lambda r: r["energy_end"] < 30),          # limited by energy
            "share with energy<30"),
        "explore / non-food output": (
            frac(lambda r: r["explore"] > 0),
            spread([r["explore"] for r in pool]),
            1 - frac(lambda r: r["has_explore_flag"]),     # share whose information output is unsaturated
            "share that never got loves_exploring"),
        "material / build": (
            frac(lambda r: r["gather_material"] > 0),
            spread([r["gather_material"] for r in pool]),
            frac(lambda r: r["material_end"] < 3),         # cannot afford one build
            "share with material<3"),
        "goal structure": (
            frac(lambda r: r["n_goal_kinds"] >= 2),
            spread([r["top_goal_share"] for r in pool]),
            frac(lambda r: r["top_goal_share"] < 0.9),     # not monopolised by a single goal
            "share with a top-goal share <0.9"),
        "knowledge": (
            frac(lambda r: r["n_knowledge"] > 0),
            spread([r["n_knowledge"] / 6.0 for r in pool]),
            frac(lambda r: r["n_knowledge"] < 4),
            "share with fewer than 4 knowledge entries"),
        "shelter / storm": (
            1.0,
            spread([r["shelter_end"] / 100.0 for r in pool]),
            frac(lambda r: r["shelter_end"] < 50),
            "share with shelter<50"),
        "objects / action legality": (
            frac(lambda r: r["read"] > 0),
            spread([r["read"] for r in pool]),
            0.0,
            "the baseline world has no books → always 0"),
    }

    print("=" * 112)
    print(f" v3 novel-probe capacity audit (group-blind)  common garden {OBS_DAYS} days"
          f"  n={n}  alive {frac(lambda r: r['alive']):.1%}")
    print("=" * 112)
    print(f"  {'channel':<30}{'Q1 partic.':>12}{'Q2 var':>9}{'Q3 binding':>12}"
          f"{'Q4 non-fatal':>14}{'Q5 read-back':>14}{'Q6 equal':>10}{'eligible':>10}")
    print("  " + "-" * 108)

    passed = []
    for ch, (q1, q2, q3, q3name) in meas.items():
        q4, q5, q6, why = STRUCTURAL[ch]
        ok1, ok2, ok3 = q1 >= 0.70, q2 >= 0.10, q3 >= 0.20
        ok = all([ok1, ok2, ok3, q4, q5, q6])
        mark = lambda b: "✓" if b else "✗"
        print(f"  {ch:<22}{q1:>8.1%}{mark(ok1)}{q2:>8.3f}{mark(ok2)}"
              f"{q3:>9.1%}{mark(ok3)}{mark(q4):>9}{mark(q5):>8}{mark(q6):>8}"
              f"{'★eligible' if ok else 'not eligible':>13}")
        if ok:
            passed.append(ch)

    print("\n  The exact definition of Q3:")
    for ch, (_, _, _, q3name) in meas.items():
        print(f"    {ch:<22} {q3name}")
    print("\n  The structural basis of Q4/Q5/Q6:")
    for ch, (_, _, _, why) in STRUCTURAL.items():
        print(f"    {ch:<22} {why}")

    print("\n" + "=" * 112)
    if passed:
        print(f" ★ Eligible channels: {passed}")
        print(" → the fourth probe should be built here; continue with group-blind feasibility calibration.")
    else:
        print(" ✗ **No channel passes all six eligibility standards.**")
        print("")
        print(" → 026 is closed on this basis: **v3 lacks an action economy in which generalization can be tested cleanly.**")
        print("")
        print(" This is not 'we picked the wrong battlefield again' but a structural conclusion from three rounds")
        print(" of group-blind feasibility testing. The design goal of v4 becomes very clear —")
        print(" **not to make the model more complex, but to close the gap these three experiments exposed in v3:**")
        print("   at least one economy that **does not decide life or death**, that **nearly everyone can take part in**,")
        print("   that **admits several effective strategies**, and that **lets the agent adapt behaviourally to a new contingency**.")
        print("")
        print(" ★ The key methodological distinction ★")
        print("   Upgrading to v4 is not about 'tuning the paper's result into existence',")
        print("   but because group-blind feasibility testing has clearly shown that")
        print("   frozen v3 lacks the degrees of freedom needed to measure this question.")
    print("=" * 112)


if __name__ == "__main__":
    mp.freeze_support()
    main()
