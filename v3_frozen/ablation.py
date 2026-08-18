"""
Ablation experiment — how much does each mechanism actually contribute?
=======================================================================

Run:  python ablation.py

The method comes from Generative Agents (UIST '23) §6: switch off each component of the
architecture in turn and see how far the metric drops. What they proved was "every component
is necessary"; what is proved here is the same thing —
**differentiation is not the doing of one knob, and it is not random**.

Two differences from that paper:
  1. Their dependent variable is "believability" (human ratings); here it is "user attribution" (paired effect size)
  2. They ran the simulation once, with no null baseline; here the last row *is* the null hypothesis

★ The last row is the negative control: set the feeding interval of all three users equal.
  Then two runs of the same seed are deterministically identical → the difference must be exactly 0.
  If it is not 0, something else is leaking in the measurement pipeline and every number above is untrustworthy.
"""

import statistics

import sim
import scenarios

SEEDS = 300
DAYS = 30
A_NAME, B_NAME = "doting", "hands-off"
VISIBLE_DELTA = 5.0

# Each condition switches off one mechanism. The key is a module-level parameter name in sim
# The "world:" prefix = a world parameter (since v2 the season belongs to World, no longer a module global)
CONDITIONS = [
    ("full architecture",              {}),
    ("− personality weight",           {"PERSONALITY_WEIGHT": 0.0}),
    ("− positive feedback loop",       {"TRAIT_DRIFT": 0.0}),
    ("− ratchet (no mark left)",       {"HARDSHIP_MAX_BOOST": 0.0, "LANDMARK_BONUS": 0.0}),
    ("− seasonal fluctuation",         {"world:season_amplitude": 0.0}),
    ("− food deficit",                 {"EXPLORE_FOOD_YIELD": 2.0}),   # the state before experiment 013
    ("− user difference (null)",       {"__same_user__": True}),
]

TUNABLE = ["PERSONALITY_WEIGHT", "TRAIT_DRIFT", "LANDMARK_BONUS",
           "HARDSHIP_MAX_BOOST", "EXPLORE_FOOD_YIELD"]


def apply_override(key, value):
    if key.startswith("world:"):
        sim.WORLD_DEFAULTS[key.split(":", 1)[1]] = value
    else:
        setattr(sim, key, value)


def evaluate():
    """Run one paired experiment and return the key metrics under this parameter set"""
    sim.SIM_DAYS = DAYS
    world = {(s, a): scenarios.run(s, a)
             for s in range(SEEDS) for a in (A_NAME, B_NAME)}

    pairs = [(world[(s, A_NAME)], world[(s, B_NAME)]) for s in range(SEEDS)
             if world[(s, A_NAME)].alive and world[(s, B_NAME)].alive]
    dead = 1 - sum(1 for s in range(SEEDS) if world[(s, B_NAME)].alive) / SEEDS
    if not pairs:
        return None

    def stat(get):
        d = [get(b) - get(a) for a, b in pairs]
        sd = statistics.pstdev(d)
        return statistics.median(d), (statistics.mean(d) / sd if sd else 0.0)

    ind_med, ind_dz = stat(lambda a: a.traits["industry"])
    con_med, con_dz = stat(lambda a: a.condition)
    carriers = [lambda a: a.traits["industry"], lambda a: a.condition,
                lambda a: a.traits["caution"], lambda a: a.traits["curiosity"],
                lambda a: a.shelter]
    untouched = sum(1 for a, b in pairs
                    if all(abs(g(b) - g(a)) < VISIBLE_DELTA for g in carriers)
                    and a.flags == b.flags) / len(pairs)
    return {"ind_dz": ind_dz, "ind_med": ind_med, "con_dz": con_dz,
            "untouched": untouched, "dead": dead, "n": len(pairs)}


def main():
    print("=" * 84)
    print(f" Ablation experiment   {SEEDS} seeds × {DAYS} days   pairing: {A_NAME} → {B_NAME}")
    print("=" * 84)
    print(f"{'condition':<30}{'ind dz':>9}{'ind median':>12}{'cond dz':>10}"
          f"{'no change at all':>18}{'hands-off dead':>16}{'vs full':>10}")
    print("-" * 84)

    base = {k: getattr(sim, k) for k in TUNABLE}
    base_world = dict(sim.WORLD_DEFAULTS)
    base_feeding = dict(scenarios.FEEDING)
    full_dz = None

    for label, overrides in CONDITIONS:
        # Restore the full architecture, then apply this condition's overrides
        for k, v in base.items():
            setattr(sim, k, v)
        sim.WORLD_DEFAULTS.update(base_world)
        scenarios.FEEDING.update(base_feeding)

        overrides = dict(overrides)
        if overrides.pop("__same_user__", False):
            for k in scenarios.FEEDING:
                scenarios.FEEDING[k] = 3.0
        for k, v in overrides.items():
            apply_override(k, v)

        r = evaluate()
        if r is None:
            print(f"{label:<30}   — wiped out")
            continue
        if full_dz is None:
            full_dz = r["ind_dz"]
            drop = "baseline"
        else:
            drop = f"{(r['ind_dz'] - full_dz) / full_dz:+.0%}" if full_dz else "—"

        print(f"{label:<30}{r['ind_dz']:>9.3f}{r['ind_med']:>12.2f}"
              f"{r['con_dz']:>10.3f}{r['untouched']:>18.1%}"
              f"{r['dead']:>16.1%}{drop:>10}")

    for k, v in base.items():
        setattr(sim, k, v)
    sim.WORLD_DEFAULTS.update(base_world)
    scenarios.FEEDING.update(base_feeding)

    print("\n How to read:")
    print("   ind dz            effect size of user attribution. The more it drops, the more critical the mechanism")
    print("   no change at all  share of pairs where the user changed but no carrier moved (lower is better)")
    print("   the last row must be all zeros — that is the null hypothesis; non-zero means the measurement pipeline leaks")


if __name__ == "__main__":
    main()
