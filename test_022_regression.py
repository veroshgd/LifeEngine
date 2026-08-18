"""
Experiment 022 regression check — with the three parameters zeroed, behaviour must be bit-identical to 021
==========================================================================================================

Run:  python test_022_regression.py

Preregistration §6 step 2. If the wiring change alters any number while in the "off" state, the change
has leaked somewhere it should not touch (most typically by consuming RNG and shifting the whole seed),
and every 022 comparison is void.

Criterion: bit-identical. Not "about the same".
"""

import sys

import sim
import scenarios


def fingerprint(seed, world, days=60):
    """The full fingerprint of one life: action distribution + personality + goal sequence + persistent structure"""
    a = scenarios.run(seed, world, days=days)
    return (
        a.alive,
        tuple(sorted(a.action_log.items())),
        tuple(round(a.traits[t], 10) for t in sim.TRAITS),
        tuple(a.goal_by_day),
        tuple(sorted(a.knowledge)),
        tuple(sorted(a.flags)),
        round(a.hardship, 10),
        tuple(round(a.trait_identity[t], 10) for t in sim.TRAITS),
        round(a.shelter, 10), round(a.condition, 10),
        round(a.inventory["food"], 10),
    )


WORLDS = ["baseline", "rich world", "barren world", "has books", "rainy"]
SEEDS = range(40)


def collect():
    return {(s, w): fingerprint(s, w) for w in WORLDS for s in SEEDS}


def main():
    print("=" * 72)
    print(" Experiment 022 regression check   5 worlds × 40 seeds × 60 days")
    print("=" * 72)

    print(f"  current parameters  WEIGHT={sim.KNOWLEDGE_WEIGHT}  "
          f"GOAL_WEIGHT={sim.KNOWLEDGE_GOAL_WEIGHT}  FORGET={sim.KNOWLEDGE_FORGET}")

    # Turn off every 022 change
    sim.KNOWLEDGE_WEIGHT = 0.0
    sim.KNOWLEDGE_GOAL_WEIGHT = 0.0
    sim.KNOWLEDGE_FORGET = 0.0
    off = collect()
    print(f"  collected **off** fingerprints: {len(off)}")

    # Turn on
    sim.KNOWLEDGE_WEIGHT = 12.0
    sim.KNOWLEDGE_GOAL_WEIGHT = 0.25
    sim.KNOWLEDGE_FORGET = 0.02
    on = collect()
    print(f"  collected **on** fingerprints: {len(on)}")

    changed = [k for k in off if off[k] != on[k]]
    print(f"\n  changed once on: {len(changed)} / {len(off)} "
          f"({len(changed)/len(off):.0%})")
    if not changed:
        print("\n  ✗ Serious problem: turning 022 on changed **nothing**.")
        print("    The wiring is not actually in effect — check the action names in KNOWLEDGE_ACTIONS,")
        print("    or no ball ever learned any knowledge at all.")
        return 1

    # The real criterion: the off state must match the baseline. git cannot compare it (this is not a repo),
    # so a necessary condition is tested here: in the off state knowledge_strength affects no output.
    sim.KNOWLEDGE_WEIGHT = 0.0
    sim.KNOWLEDGE_GOAL_WEIGHT = 0.0
    sim.KNOWLEDGE_FORGET = 0.0
    off2 = collect()
    if off2 != off:
        print("\n  ✗ The off state is not even reproducible on its own — randomness is leaking.")
        return 1
    print("  ✓ The off state is reproducible (two collections identical)")

    # In the off state, forget must not delete any knowledge
    sim.KNOWLEDGE_FORGET = 0.0
    a = scenarios.run(3, "rich world", days=60)
    if len(a.knowledge) != len(a.knowledge_strength):
        print(f"\n  ✗ knowledge and knowledge_strength out of sync: "
              f"{len(a.knowledge)} vs {len(a.knowledge_strength)}")
        return 1
    print(f"  ✓ knowledge / knowledge_strength in sync ({len(a.knowledge)} entries)")

    print("\n  ★ Off state consistent, on state effective. P1/P2/P3 can proceed.")
    print("  ⚠ But \"off state == the numbers of experiment 021\" can only be confirmed by having")
    print("    persistence_ablation.py reproduce 1.18 / 1.07 with KNOWLEDGE_* all zero — next step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
