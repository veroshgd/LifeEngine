"""
Transplant experiment — remove the cause; is the difference still there?
========================================================================

Experiment 018 proved that the same seed placed in two worlds shows a behavioural difference above
baseline after 30 days (ratio 1.56). But at that point the two balls were **still in different worlds**,
so that number cannot distinguish:

    (A) experience shaped it       → the difference is written into personality/memory and survives a return to the same world
    (B) only the current conditions differ → the difference is an instant projection of the environment and vanishes once the environment matches

The product line "there was a heavy rain once… ever since then I have not liked being unprepared"
requires (A). This script tests it directly.

Method:
    days 0–29    rich world  /  barren world       ← creates the difference
    days 30–59   both switched to the "baseline" world  ← removes the cause
    the behavioural difference is measured only on the days 30–59 window

Control arm "stay": days 30–59 remain in the original world (the cause is still present).

    stay ratio high, move ratio collapsed → it is (B), a thermometer rather than a personality
    both high                             → it is (A), experience really did leave a mark
"""

import statistics
from collections import Counter

import sim
import scenarios
from behavior import ACTIONS, GLANCE

SEEDS = 250
SPLIT = 30
TOTAL = 60
WA, WB = "rich world", "barren world"
COMMON = "baseline"


def run_phased(seed, first, second, split=SPLIT, total=TOTAL):
    """First half of life in the `first` world, second half in `second`. Returns (agent, per-hour counts inside the window)"""
    life = scenarios.make(seed, first)
    agent = life.agent

    def phase(d0, d1):
        for day in range(d0, d1):
            for t in range(sim.TICKS_PER_DAY):
                life.world.tick(day, t)
                for inf in life.influences:
                    inf(life.world, agent, day, t, life.inf_rng)
                agent.tick(day, t)
                if not agent.alive:
                    return False
            agent.daily(day)
        return True

    if not phase(0, split):
        return None, None
    snap = [Counter(c) for c in agent.action_by_hour]   # snapshot at day 30

    if second != first:                                 # change world
        w = sim.World(seed, **scenarios.WORLDS[second])
        life.world = w
        agent.world = w

    if not phase(split, total):
        return None, None

    window = [Counter(c) - snap[h] for h, c in enumerate(agent.action_by_hour)]
    return agent, window


def window_tv(wa, wb):
    """Only the per-hour action-distribution difference inside the window"""
    tot = 0.0
    for ha, hb in zip(wa, wb):
        na, nb = sum(ha.values()) or 1, sum(hb.values()) or 1
        tot += 0.5 * sum(abs(ha[x] / na - hb[x] / nb) for x in ACTIONS)
    return tot / len(wa)


def cohort(first, second):
    out = []
    for s in range(SEEDS):
        a, w = run_phased(s, first, second)
        out.append((s, a, w))
    return out


def analyse(label, cohA, cohB):
    pairs = [(a, wa, b, wb) for (s, a, wa), (_, b, wb) in zip(cohA, cohB)
             if a is not None and b is not None]
    if not pairs:
        print(f"  {label}: wiped out")
        return None
    live_seeds = {s for (s, a, _), (_, b, _) in zip(cohA, cohB)
                  if a is not None and b is not None}

    tv_user = statistics.mean(window_tv(wa, wb) for _, wa, _, wb in pairs)

    # Baseline: same path, different seed. ★Use only the seeds that survived on both sides★
    # (environment.py paired survivors within each cohort, and the survivors of the barren world
    #  are filtered → within-group variance too small → baseline too small → ratio inflated. Closed off here.)
    base = []
    for coh in (cohA, cohB):
        al = [w for (s, a, w) in coh if a is not None and s in live_seeds]
        base += [(al[i], al[i + 1]) for i in range(0, len(al) - 1, 2)]
    tv_base = statistics.mean(window_tv(x, y) for x, y in base)

    eye = sum(1 for a, _, b, _ in pairs
              if any(t(a) != t(b) for _, t in GLANCE)) / len(pairs)
    dtr = {t: statistics.mean(b.traits[t] - a.traits[t] for a, _, b, _ in pairs)
           for t in sim.TRAITS}
    dead = 1 - len(pairs) / SEEDS

    print(f"  {label:<10} {tv_user:>8.3f} {tv_base:>8.3f} {tv_user / tv_base:>7.2f}"
          f" {eye:>10.1%} {dead:>8.1%}   "
          + " ".join(f"{t[:2]}{dtr[t]:+6.1f}" for t in sim.TRAITS))
    return tv_user / tv_base


def main():
    print("=" * 96)
    print(f" Transplant experiment   {SEEDS} seeds   days 0–{SPLIT-1} diverge, days {SPLIT}–{TOTAL-1} measured")
    print(f" {WA} ↔ {WB}, the measurement window takes only the last {TOTAL-SPLIT} days")
    print("=" * 96)
    print(f"  {'condition':<10} {'window TV':>11} {'baseline':>10} {'ratio':>7} {'visibly distinct':>18} {'dead':>8}"
          "   personality diff (second−first)")
    print("  " + "-" * 92)

    stayA, stayB = cohort(WA, WA), cohort(WB, WB)
    r_stay = analyse("stay", stayA, stayB)

    movA, movB = cohort(WA, COMMON), cohort(WB, COMMON)
    r_move = analyse("move", movA, movB)

    print()
    if r_stay and r_move:
        keep = r_move / r_stay
        print(f"  stay {r_stay:.2f} → move {r_move:.2f}   retained {keep:.0%}")
        print()
        if r_move >= 1.0:
            print("  ★ the ratio is still > 1 after the transplant: the difference persists independently of the environment → experience really did shape it")
        elif keep >= 0.6:
            print("  ~ ratio < 1 after the transplant but most of it retained: there is a genuine persistent component, but not enough to stand on its own")
        else:
            print("  ✗ collapsed after the transplant: the difference is mainly an instant projection of the environment, not a personality")


if __name__ == "__main__":
    main()
