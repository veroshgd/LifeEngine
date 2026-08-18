"""
Relaxation test — is the 1.04 left after the transplant persistence, or "has it just not drifted back yet"?
===========================================================================================================

Run:  python relaxation_test.py

The question left open by P2 ([[Experiment 022 preregistration — memory wired into decisions]]):
with semantic + episodic + flags all wiped at the moment of transplant, the ratio is still **1.040 (p=0.0707 n.s.)**.
Two readings:

    persistent   the trait vector really has set, and no amount of time brings it back
    relaxing     the floors are off and the traits are drifting back slowly; 30 days is simply not enough

Method: after the transplant run not 30 but 90 days, and measure once in **each of three independent windows**:

    [30,60)   [60,90)   [90,120)

relaxing  → each window falls, and the last returns to 1.0.
persistent → the three windows stay level.

★ Rule 32: settle the surviving set per point ★
The whole table must not be computed on "those alive at day 120" — the survivors are precisely
"the balls that did not run off", which is the very property being measured. Each window computes
its own valid pairs and reports its loss rate.
Experiment 020 measured a 24.5% loss at 120 days, so the last window will most likely carry a question mark.
"""

import random
import statistics
from collections import Counter

import sim
import scenarios
import persistence_ablation as PA
from transplant import window_tv
from p1_test import shuffled_base, BASE_K
from p2_test import wipe_at_transplant

WA, WB, COMMON = "rich world", "barren world", "baseline"
N_SEEDS = 1500
SEED0 = 20000
SPLIT = 30
CHECKS = (60, 90, 120)          # right edge of each window; a window = the preceding 30 days
N_BOOT = 2000
LOSS_WARN = 0.15


def run_long(seed, first, wipe_what):
    """Run to 120 days, returning the per-hour counts of each of the three windows (None for windows after death)"""
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

    if not phase(0, SPLIT):
        return [None] * len(CHECKS)

    w = sim.World(seed, **scenarios.WORLDS[COMMON])
    life.world = w
    agent.world = w
    wipe_at_transplant(agent, wipe_what)

    out = []
    prev = [Counter(c) for c in agent.action_by_hour]
    start = SPLIT
    for end in CHECKS:
        if not phase(start, end):
            out += [None] * (len(CHECKS) - len(out))
            return out
        cur = [Counter(c) for c in agent.action_by_hour]
        out.append([cur[h] - prev[h] for h in range(len(cur))])
        prev = cur
        start = end
    return out


def analyse(label, wipe_what):
    scenarios.make = PA.patched_make(False, True)      # all floors off
    try:
        seeds = range(SEED0, SEED0 + N_SEEDS)
        ca = [run_long(s, WA, wipe_what) for s in seeds]
        cb = [run_long(s, WB, wipe_what) for s in seeds]
    finally:
        scenarios.make = PA._orig_make

    print(f"\n  ── {label} ──")
    for wi, end in enumerate(CHECKS):
        live = [i for i in range(N_SEEDS)
                if ca[i][wi] is not None and cb[i][wi] is not None]
        n = len(live)
        loss = 1 - n / N_SEEDS
        if n < 50:
            print(f"    days {end-30}–{end}   not enough samples")
            continue
        wa = [ca[i][wi] for i in live]
        wb = [cb[i][wi] for i in live]
        rng = random.Random(777)
        treat = [window_tv(wa[k], wb[k]) for k in range(n)]
        base = shuffled_base(wa, BASE_K, rng) + shuffled_base(wb, BASE_K, rng)
        ratio = statistics.mean(treat) / statistics.mean(base)
        boots = []
        for _ in range(N_BOOT):
            pick = [rng.randrange(n) for _ in range(n)]
            boots.append(statistics.mean(treat[i] for i in pick) /
                         statistics.mean(
                             shuffled_base([wa[i] for i in pick], BASE_K, rng) +
                             shuffled_base([wb[i] for i in pick], BASE_K, rng)))
        boots.sort()
        lo, hi = boots[int(.025 * N_BOOT)], boots[int(.975 * N_BOOT)]
        flag = " ⚠loss>15%" if loss > LOSS_WARN else ""
        sig = "≠1" if lo > 1.0 else "contains 1.0"
        print(f"    days {end-30:>3}–{end:>3}   n={n:>5}  loss {loss:>6.1%}  "
              f"ratio {ratio:.3f}  [{lo:.3f}, {hi:.3f}]  {sig}{flag}")


def main():
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    print("=" * 92)
    print(f" Relaxation test   seeds {SEED0}–{SEED0+N_SEEDS-1}   N={N_SEEDS}"
          f"   022 on + all floors off   three independent 30-day windows")
    print("=" * 92)
    analyse("① delete nothing", set())
    analyse("⑤ wipe semantic+episodic+flags at transplant", {"semantic", "episodic", "flags"})
    print("\n  Falling window by window and returning to 1.0 → relaxation; that 1.040 is a residual artefact and must not go in the paper")
    print("  Three level windows                          → real persistence, the trait vector has set")


if __name__ == "__main__":
    main()
