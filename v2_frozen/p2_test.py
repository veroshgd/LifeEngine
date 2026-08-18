"""
P2 — delete knowledge alone at the moment of transplant (keeping flags): does the ratio collapse?
=================================================================================================

Run:  python p2_test.py

Preregistration §4:

    P2: the deletion variant is ≥ 0.05 below the P1 variant, and their 95% CIs do not overlap

★ Why it must be deleted **alone** ★ (preregistration §2)
`landmark()` writes flags and knowledge at the same time (`sim.py:458`), so the two are perfectly
correlated — that is why the "semantic memory diff" and "landmark diff" columns of the experiment
020 mechanism table hold identical numbers.
The original ladder in `deletion.py` was nested (②③④ stacking up), so it cannot attribute anything.
Here it is made **non-nested**: each variant deletes exactly one thing.

★ The logic of P2 ★
If P1 passes (no-floor variant > 1 after wiring), that persistence must **come from knowledge**.
Wipe knowledge at the moment of transplant and keep everything else — the ratio should collapse back to about 1.
If it does not collapse, the persistence comes from somewhere else and **the knowledge channel cannot be claimed**.
"""

import random
import statistics
from collections import Counter

import sim
import scenarios
import persistence_ablation as PA
from transplant import window_tv, SPLIT, TOTAL
from significance_main import per_seed_delta, sign_perm_p
from p1_test import shuffled_base, BASE_K, N_BOOT

WA, WB, COMMON = "rich world", "barren world", "baseline"
N_SEEDS = 1500
SEED0 = 20000          # same block as P1 (the preregistered reserved block)


def wipe_at_transplant(agent, what):
    """★Non-nested★ each variant deletes one thing. trait_floor / trait_identity are never deleted here
    — they are the business of the floor ablation, and mixing them in destroys attribution."""
    if "semantic" in what:
        agent.knowledge = {}
        agent.knowledge_strength = {}      # 022: the strength dict is what know() reads
    if "episodic" in what:
        agent.memories = []
    if "flags" in what:
        agent.flags = set()
    if "hardship" in what:
        agent.hardship = 0.0
        agent._hardship_anchor = None


def run_phased_wipe(seed, first, wipe_what):
    """First 30 days in the `first` world → wipe the given layer → last 30 days in the baseline world"""
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
        return None, None
    snap = [Counter(c) for c in agent.action_by_hour]

    w = sim.World(seed, **scenarios.WORLDS[COMMON])
    life.world = w
    agent.world = w
    wipe_at_transplant(agent, wipe_what)       # ★at exactly this moment★

    if not phase(SPLIT, TOTAL):
        return None, None
    window = [Counter(c) - snap[h] for h, c in enumerate(agent.action_by_hour)]
    return agent, window


def analyse(label, wipe_what, floor_off=True):
    scenarios.make = PA.patched_make(False, floor_off)
    try:
        seeds = range(SEED0, SEED0 + N_SEEDS)
        ca = [run_phased_wipe(s, WA, wipe_what) for s in seeds]
        cb = [run_phased_wipe(s, WB, wipe_what) for s in seeds]
    finally:
        scenarios.make = PA._orig_make

    live = [i for i in range(N_SEEDS)
            if ca[i][0] is not None and cb[i][0] is not None]
    n = len(live)
    wa = [ca[i][1] for i in live]
    wb = [cb[i][1] for i in live]
    rng = random.Random(777)

    treat = [window_tv(wa[k], wb[k]) for k in range(n)]
    base = shuffled_base(wa, BASE_K, rng) + shuffled_base(wb, BASE_K, rng)
    ratio = statistics.mean(treat) / statistics.mean(base)

    boots = []
    for _ in range(N_BOOT):
        pick = [rng.randrange(n) for _ in range(n)]
        boots.append(statistics.mean(treat[i] for i in pick) /
                     statistics.mean(shuffled_base([wa[i] for i in pick], BASE_K, rng) +
                                     shuffled_base([wb[i] for i in pick], BASE_K, rng)))
    boots.sort()
    lo, hi = boots[int(.025 * N_BOOT)], boots[int(.975 * N_BOOT)]

    deltas = per_seed_delta(ca, cb, N_SEEDS, random.Random(12345))[0]
    _, p = sign_perm_p(deltas, 10000, random.Random(999))
    star = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."
    print(f"  {label:<24}{n:>6}{1-n/N_SEEDS:>8.1%}{ratio:>8.3f}"
          f"  [{lo:.3f}, {hi:.3f}]{p:>9.4f} {star}")
    return ratio, lo, hi


def main():
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    print("=" * 96)
    print(f" P2 non-nested deletion   seeds {SEED0}–{SEED0+N_SEEDS-1}   N={N_SEEDS}"
          f"   022 on + all floors off")
    print("=" * 96)
    print(f"  {'what is deleted at transplant':<32}{'n':>6}{'dead':>8}{'ratio':>8}  {'95% CI':<18}{'p':>9}")
    print("  " + "-" * 92)

    base_r = analyse("① delete nothing (=P1)", set())
    sem = analyse("② delete semantic knowledge only", {"semantic"})
    epi = analyse("③ delete episodic memories only", {"episodic"})
    flg = analyse("④ delete flags only", {"flags"})
    allm = analyse("⑤ delete semantic+episodic+flags", {"semantic", "episodic", "flags"})

    print(f"\n  P2 criterion: ② is ≥ 0.05 below ① and the CIs do not overlap")
    drop = base_r[0] - sem[0]
    overlap = not (sem[2] < base_r[1] or base_r[2] < sem[1])
    print(f"    ①{base_r[0]:.3f} → ②{sem[0]:.3f}   drop {drop:+.3f}   "
          f"CI {'overlap' if overlap else 'no overlap'}   "
          f"{'✓ P2 pass' if drop >= 0.05 and not overlap else '✗ P2 fail'}")
    print("\n  ③④ are controls: if deleting episodic/flags drops it just as much, the effect is not specific to knowledge.")


if __name__ == "__main__":
    main()
