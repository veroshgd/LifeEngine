"""
Deletion test — which layer does the difference actually live in?
=================================================================

Run:  python deletion.py

The transplant experiment proved the difference does not depend on the environment. But it did
not say **where** the difference lives. This script deletes each layer in a ladder at the moment
of transplant and sees when the difference collapses.

    ① full
    ② − episodic memory        memories = []
    ③ − episodic + semantic    also clear knowledge
    ④ traits only              also clear flags / goal / goal_history / hardship

★ Why step ③ is mandatory ★
`knowledge` is derived from episodic memory (`mark()` calls `learn()` along the way).
Deleting only the episodic layer leaves the semantic one, so **external scaffolding** is still
holding it up, and the "memory-independent" result is fake.

★ Why step ④ is the real diagnosis ★
Keep only the personality numbers and wipe out every experiential structure. If the difference
is still there at that point, then it really has settled into the personality vector itself
rather than being regenerated daily from memory.

    collapses at ②     → the difference is sustained by concrete events
    collapses at ③     → sustained by semantic knowledge
    collapses at ④     → sustained by experiential switches: flags / goal / hardship
    survives ④         → already written into the personality vector; it really has "grown this way"
"""

import statistics

import sim
import scenarios
from behavior import GLANCE
from transplant import window_tv
from paired import pad

SEEDS = 200
SPLIT = 30
CHECKS = (30, 60, 90)
WA, WB = "rich world", "barren world"
COMMON = "baseline"

LADDER = [
    ("① full",                set()),
    ("② −episodic",           {"episodic"}),
    ("③ −episodic+semantic",  {"episodic", "semantic"}),
    ("④ traits only",         {"episodic", "semantic", "experiential"}),
]


def wipe(agent, what):
    if "episodic" in what:
        agent.memories = []
    if "semantic" in what:
        agent.knowledge = {}
        # ★022★ The strength dict must be cleared too — `know()` reads it, not knowledge.
        # Clearing only knowledge leaves the behavioural effect intact and the deletion test reports a fake no-op.
        agent.knowledge_strength = {}
    if "experiential" in what:
        # Experiential switches: they all enter score() directly, so without deleting them it is not "traits only"
        agent.flags = set()
        agent.hardship = 0.0
        agent._hardship_anchor = None
        agent.goal = None
        agent.goal_history = []
        agent.goal_satiation = {}
    # Note: trait_floor / trait_identity are kept — they are part of the personality structure,
    # not memory. To ablate them separately use persistence_ablation.py


def run_tracked(seed, first, what):
    life = scenarios.make(seed, first)
    agent = life.agent
    snaps, base_hour = {}, None
    for day in range(max(CHECKS)):
        if day == SPLIT:
            w = sim.World(seed, **scenarios.WORLDS[COMMON])
            life.world = w
            agent.world = w
            wipe(agent, what)
            base_hour = [c.copy() for c in agent.action_by_hour]
        for t in range(sim.TICKS_PER_DAY):
            life.world.tick(day, t)
            for inf in life.influences:
                inf(life.world, agent, day, t, life.inf_rng)
            agent.tick(day, t)
            if not agent.alive:
                return snaps
        agent.daily(day)
        if day + 1 in CHECKS:
            win = None
            if base_hour is not None:
                win = [c - base_hour[h] for h, c in enumerate(agent.action_by_hour)]
            snaps[day + 1] = {"agent": agent, "win": win,
                              **{t: agent.traits[t] for t in sim.TRAITS}}
    return snaps


def measure(what):
    A = [run_tracked(s, WA, what) for s in range(SEEDS)]
    B = [run_tracked(s, WB, what) for s in range(SEEDS)]
    out = {}
    for d in CHECKS:
        live = [i for i in range(SEEDS) if d in A[i] and d in B[i]]
        if len(live) < 20:
            continue
        row = {"n": len(live), "loss": 1 - len(live) / SEEDS,
               **{t: statistics.mean(B[i][d][t] - A[i][d][t] for i in live)
                  for t in sim.TRAITS}}
        if d > SPLIT:
            num = statistics.mean(window_tv(A[i][d]["win"], B[i][d]["win"])
                                  for i in live)
            base = []
            for coh in (A, B):
                al = [coh[i][d]["win"] for i in live]
                base += [(al[j], al[j + 1]) for j in range(0, len(al) - 1, 2)]
            den = statistics.mean(window_tv(x, y) for x, y in base)
            row["r"] = num / den if den else 0.0
            row["eye"] = sum(
                1 for i in live
                if any(f(A[i][d]["agent"]) != f(B[i][d]["agent"])
                       for _, f in GLANCE)) / len(live)
        out[d] = row
    return out


def main():
    print("=" * 100)
    print(f" Deletion test   {SEEDS} seeds   {WA} ↔ {WB}, both enter **{COMMON}** on day {SPLIT}"
          f" with the deletion ladder applied")
    print("=" * 100)
    print(f"  {pad('condition', 24)}{pad('caut at transplant', 20, True)}"
          f"{pad('+30 caut', 11, True)}{pad('+60 caut', 11, True)}"
          f"{pad('+30 ratio', 12, True)}{pad('+60 ratio', 12, True)}"
          f"{pad('+60 visible', 14, True)}{pad('+60 loss', 12, True)}")
    print("  " + "-" * 96)

    rows = []
    for label, what in LADDER:
        m = measure(what)
        if 60 not in m:
            print(f"  {pad(label, 24)}  — not enough samples")
            continue
        rows.append((label, m))
        print(f"  {pad(label, 16)}{pad(f'{m[30]["caution"]:+.1f}', 13, True)}"
              f"{pad(f'{m[60]["caution"]:+.1f}', 11, True)}"
              f"{pad(f'{m[90]["caution"]:+.1f}' if 90 in m else '—', 11, True)}"
              f"{pad(f'{m[60]["r"]:.2f}', 11, True)}"
              f"{pad(f'{m[90]["r"]:.2f}' if 90 in m else '—', 11, True)}"
              f"{pad(f'{m[60]["eye"]:.1%}', 11, True)}"
              f"{pad(f'{m[60]["loss"]:.1%}', 11, True)}")

    print("\n" + "=" * 100)
    print(" Verdict")
    print("=" * 100)
    if rows:
        full = rows[0][1]
        for label, m in rows[1:]:
            keep_r = m[60]["r"] / full[60]["r"] if full[60]["r"] else 0
            keep_c = (m[60]["caution"] / full[60]["caution"]
                      if full[60]["caution"] else 0)
            print(f"  {pad(label, 24)}  behaviour ratio retained {keep_r:>5.0%}   "
                  f"caution retained {keep_c:>5.0%}")
        last = rows[-1][1]
        print()
        if last[60]["r"] >= 1.0:
            print("  ★ after deleting all memory the behaviour ratio is still ≥ 1 — the difference has settled into the personality vector itself")
        elif last[60]["r"] >= 0.7 * full[60]["r"]:
            print("  ~ most of it survives deleting all memory, but no longer enough to clear the baseline on its own")
        else:
            print("  ✗ collapses once all memory is deleted — the difference was regenerated daily from memory")
    print("\n  ⚠ Rows with loss >15% carry survivor contamination. trait_floor / trait_identity were not deleted,")
    print("     they belong to the personality structure; to ablate them separately run persistence_ablation.py")


if __name__ == "__main__":
    main()
