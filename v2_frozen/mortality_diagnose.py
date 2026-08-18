"""
Mortality diagnosis — over 120 days, who dies, when, and why
============================================================

Run:  python mortality_diagnose.py

The direct to-do of rule 42. The relaxation test (experiment 022) loses 44.5% at 120 days, so any
long-horizon conclusion becomes a function of selection effects. **Find the cause of death before fixing it.**

Experiment 019 had the same class of problem once: the balls that died spent 46% of their time
exploring and 2% gathering — what killed them was "raising the ambition to go and see distant
places while there is nothing to eat", and the slack gate (rule 27) pushed it down to 7.0%.
Now, with all floors off over 120 days, it is back.

Four questions:
  1. When they die (the time distribution of death)
  2. What they were doing before dying (action profile vs survivors)
  3. What the proximate cause was (starvation / condition collapse / both)
  4. Whether it is specific to all-floors-off, or the full architecture does it too
"""

import statistics
from collections import Counter

import sim
import scenarios
import persistence_ablation as PA

WA, WB, COMMON = "rich world", "barren world", "baseline"
N = 400
SPLIT, TOTAL = 30, 120


def run_probe(seed, first):
    """Run to 120 days. Returns day of death (alive = None), action profile of the last 10 days, final state"""
    life = scenarios.make(seed, first)
    agent = life.agent
    trace = []          # snapshot at the end of each day

    def phase(d0, d1):
        for day in range(d0, d1):
            before = Counter(agent.action_log)
            for t in range(sim.TICKS_PER_DAY):
                life.world.tick(day, t)
                for inf in life.influences:
                    inf(life.world, agent, day, t, life.inf_rng)
                agent.tick(day, t)
                if not agent.alive:
                    trace.append((day, dict(Counter(agent.action_log) - before),
                                  agent.hunger, agent.condition,
                                  agent.inventory["food"], agent.goal))
                    return False
            agent.daily(day)
            trace.append((day, dict(Counter(agent.action_log) - before),
                          agent.hunger, agent.condition,
                          agent.inventory["food"], agent.goal))
        return True

    if not phase(0, SPLIT):
        return None, trace, agent
    w = sim.World(seed, **scenarios.WORLDS[COMMON])
    life.world = w
    agent.world = w
    alive = phase(SPLIT, TOTAL)
    return (None if alive else trace[-1][0]), trace, agent


def profile_last(trace, days=10):
    acc = Counter()
    for _, acts, _, _, _, _ in trace[-days:]:
        acc.update(acts)
    tot = sum(acc.values()) or 1
    return {a: acc[a] / tot for a in sim.ACTIONS}


def study(label, floor_off, k_on):
    sim.KNOWLEDGE_WEIGHT = 12.0 if k_on else 0.0
    sim.KNOWLEDGE_GOAL_WEIGHT = 0.25 if k_on else 0.0
    sim.KNOWLEDGE_FORGET = 0.02 if k_on else 0.0
    scenarios.make = PA.patched_make(False, floor_off)
    try:
        res = [run_probe(s, w) for w in (WA, WB) for s in range(N)]
    finally:
        scenarios.make = PA._orig_make

    dead = [(d, t, a) for d, t, a in res if d is not None]
    alive = [(d, t, a) for d, t, a in res if d is None]
    rate = len(dead) / len(res)
    print(f"\n  ── {label} ──   dead {rate:.1%}  ({len(dead)}/{len(res)})")
    if not dead:
        return

    # 1. When they die
    days = sorted(d for d, _, _ in dead)
    buckets = Counter((d // 15) * 15 for d in days)
    print("    time distribution of death: " + "  ".join(
        f"{b}-{b+14}d:{buckets[b]}" for b in sorted(buckets)))

    # 2/3. State before death
    print(f"    median at death: hunger {statistics.median(t[-1][2] for _, t, _ in dead):.0f}"
          f"  condition {statistics.median(t[-1][3] for _, t, _ in dead):.0f}"
          f"  food store {statistics.median(t[-1][4] for _, t, _ in dead):.1f}")

    dp = [profile_last(t) for _, t, _ in dead]
    ap = [profile_last(t) for _, t, _ in alive] if alive else []
    print(f"    {'action':<20}{'dead':>8}{'alive':>8}   share of the last 10 days")
    for act in sim.ACTIONS:
        d_ = statistics.mean(p[act] for p in dp)
        a_ = statistics.mean(p[act] for p in ap) if ap else 0.0
        mark = "  ←" if d_ - a_ > 0.05 else ""
        print(f"    {act:<18}{d_:>7.1%}{a_:>8.1%}{mark}")

    goals = Counter(t[-1][5]["type"] if t[-1][5] else "none" for _, t, _ in dead)
    print("    pursuing at death: " + "  ".join(
        f"{g}:{c/len(dead):.0%}" for g, c in goals.most_common(4)))


def main():
    print("=" * 84)
    print(f" Mortality diagnosis   {N} seeds × 2 worlds × {TOTAL} days   transplanted to baseline")
    print("=" * 84)
    study("full architecture + 022 on", floor_off=False, k_on=True)
    study("all floors off + 022 on (= the relaxation-test variant)", floor_off=True, k_on=True)
    study("all floors off + 022 off", floor_off=True, k_on=False)
    study("full architecture + 022 off (= the experiment 020 baseline)", floor_off=False, k_on=False)


if __name__ == "__main__":
    main()
