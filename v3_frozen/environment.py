"""
Environment experiment — same seed, two worlds
==============================================

Run:  python environment.py

This is the experiment note ⑥ asked for, and a direct test of the product philosophy:

    the user does not control the NPC; they change the world it lives in, like a god,
    and life grows by itself according to the environment.

So we stop comparing "doting vs hands-off" and instead do:

    same seed, same initial personality, same Agent, same feeding frequency,
    and the only thing changed is the **world**.

Then after 30 days ask: have they become different lives?

★ Noise floor (rule 9)
----------------------
As in behavior.py, the ratio is the conclusion:

    difference caused by environment  = same seed, different world
    baseline                          = same world, different seed   ← what the balls differ by anyway

**The environment ratio must exceed 1**, otherwise "put it in another world and it grows
into something else" does not hold. The old feeding axis is listed alongside, so the two
channels can be compared directly for strength.
"""

import statistics
import sys

import sim
import scenarios
from behavior import GLANCE, hourly_tv, profile, tv
from paired import pad

SEEDS = 250
DAYS = 30

# World pairs to compare. The first two are Experiment A / B from the notes
PAIRS = [
    ("rich world", "barren world"),
    ("has books",  "baseline"),
    ("has music",  "baseline"),
    ("food-rich",  "food-poor"),
    ("material-rich", "material-scarce"),
    ("rainy",      "stable weather"),
]

# The old control axis: user feeding frequency. Only in the same table can we see which channel is stronger
FEED_PAIR = ("doting", "hands-off")

GOAL_TYPES = list(sim.GOAL_ACTIONS)


def goal_profile(agent):
    """How many days of a lifetime went to each kind of goal — the new carrier the goal layer brings"""
    days = [g for g in agent.goal_by_day if g]
    n = len(days) or 1
    return {g: days.count(g) / n for g in GOAL_TYPES}


def goal_tv(a, b):
    pa, pb = goal_profile(a), goal_profile(b)
    return 0.5 * sum(abs(pa[g] - pb[g]) for g in GOAL_TYPES)


def cohort(name):
    return [scenarios.run(s, name, days=DAYS) for s in range(SEEDS)]


def compare(name_a, name_b, cache):
    for n in (name_a, name_b):
        if n not in cache:
            cache[n] = cohort(n)
    A, B = cache[name_a], cache[name_b]

    live = [i for i in range(SEEDS) if A[i].alive and B[i].alive]
    pairs = [(A[i], B[i]) for i in live]
    if not pairs:
        return None

    # Baseline: within the same world, how far apart are two balls with different seeds
    # ★Use only the seeds that survived on both sides★
    # The old version paired survivors within each cohort. Problem: the survivors of the barren
    # world are a filtered batch (the weak all died) → within-group variance too small → baseline
    # too small → ratio inflated. The treatment group uses the intersection of "alive on both
    # sides", so the baseline must use the same batch of seeds, otherwise the selection pressure
    # differs between the two and they are no longer measuring the same thing.
    base = []
    for coh in (A, B):
        al = [coh[i] for i in live]
        base += [(al[i], al[i + 1]) for i in range(0, len(al) - 1, 2)]

    def mean(fn, ps):
        return statistics.mean(fn(x, y) for x, y in ps)

    hu, hb = mean(hourly_tv, pairs), mean(hourly_tv, base)
    gu, gb = mean(goal_tv, pairs), mean(goal_tv, base)
    eye = sum(1 for a, b in pairs
              if any(t(a) != t(b) for _, t in GLANCE)) / len(pairs)
    dead = 1 - len(live) / SEEDS
    dtr = {t: statistics.mean(b.traits[t] - a.traits[t] for a, b in pairs)
           for t in sim.TRAITS}
    return {"hu": hu, "hb": hb, "hr": hu / hb if hb else 0,
            "gu": gu, "gb": gb, "gr": gu / gb if gb else 0,
            "eye": eye, "dead": dead, "traits": dtr, "n": len(pairs)}


def main():
    print("=" * 88)
    print(f" Environment experiment   same seed, different worlds   {SEEDS} seeds × {DAYS} days")
    print("=" * 88)
    print("  Same Agent, same initial personality, same feeding frequency; only the world differs.\n")

    print(f"  {pad('comparison', 30)}{pad('routine TV', 12, True)}{pad('baseline', 10, True)}"
          f"{pad('ratio', 8, True)}{pad('goal TV', 10, True)}{pad('baseline', 10, True)}"
          f"{pad('ratio', 8, True)}{pad('visibly distinct', 18, True)}{pad('dead', 8, True)}")
    print("  " + "-" * 84)

    cache = {}
    rows = []
    for a, b in PAIRS + [FEED_PAIR]:
        r = compare(a, b, cache)
        if r is None:
            print(f"  {pad(a + '↔' + b, 30)}  — wiped out")
            continue
        rows.append(((a, b), r))
        tag = "  ← old axis (feeding)" if (a, b) == FEED_PAIR else ""
        mark = "" if r["hr"] <= 1.0 else "  ★"
        print(f"  {pad(a + '↔' + b, 22)}{pad(f'{r['hu']:.3f}', 10, True)}"
              f"{pad(f'{r['hb']:.3f}', 8, True)}{pad(f'{r['hr']:.2f}', 8, True)}"
              f"{pad(f'{r['gu']:.3f}', 10, True)}{pad(f'{r['gb']:.3f}', 8, True)}"
              f"{pad(f'{r['gr']:.2f}', 8, True)}"
              f"{pad(f'{r['eye']:.1%}', 11, True)}{pad(f'{r['dead']:.1%}', 8, True)}"
              f"{mark}{tag}")

    print("\n  How to read:")
    print("    routine TV  per-hour difference in the action distribution. Only ratio > 1 shows the environment beats the seed")
    print("    goal TV     difference in days of a lifetime per goal — the new carrier the goal layer brings")
    print("    ★           rows with ratio > 1")

    # --- personality level: which environment pushes it where ---
    print("\n" + "=" * 88)
    print(" Personality difference (second − first)")
    print("=" * 88)
    print(f"  {pad('comparison', 30)}" + "".join(pad(t, 13, True) for t in sim.TRAITS))
    for (a, b), r in rows:
        print(f"  {pad(a + '↔' + b, 22)}"
              + "".join(pad(f"{r['traits'][t]:+.1f}", 13, True) for t in sim.TRAITS))

    # --- demo material: the most different pair ---
    print("\n" + "=" * 88)
    print(" demo material: same seed, two worlds, what each life turned into")
    print("=" * 88)
    best = max(rows, key=lambda r: r[1]["hr"])
    (na, nb), _ = best
    A, B = cache[na], cache[nb]
    cand = [(hourly_tv(a, b), a, b) for a, b in zip(A, B) if a.alive and b.alive]
    _, a, b = max(cand, key=lambda x: x[0])
    for agent, name in ((a, na), (b, nb)):
        gp = goal_profile(agent)
        top = sorted(gp.items(), key=lambda x: -x[1])[:2]
        print(f"\n▸ World: {name}")
        print(f"    personality   caution {agent.traits['caution']:.0f} | "
              f"curiosity {agent.traits['curiosity']:.0f} | "
              f"industry {agent.traits['industry']:.0f}   ({agent.dominant_style()})")
        print(f"    state   shelter {agent.shelter:.0f}  condition {agent.condition:.0f}  "
              f"food store {agent.inventory['food']:.0f}")
        print(f"    spent its life pursuing  " +
              ", ".join(f"{sim.GOAL_LABEL[g]}({p:.0%})" for g, p in top if p))
        print(f"    finished {sum(1 for g in agent.goal_history if g['outcome'] == 'done')} things, "
              f"abandoned {sum(1 for g in agent.goal_history if g['outcome'] == 'stalled')} halfway")
        if agent.knowledge:
            print("    what it learned: " + "; ".join(agent.knowledge.values()))
        big = [m for m in agent.memories if m["importance"] >= 0.7][:3]
        for m in big:
            print(f"      · day {m['day'] + 1}, {m['text']}")


if __name__ == "__main__":
    main()
