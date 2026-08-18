"""
Experiment configuration — this is where a "user" is defined
============================================================

`sim.py` is the Life Engine; it does not know users exist.
Everything about "who is caring for it, how diligently, whether the world has books"
is defined here.

The dividing line is deliberate:
leaving USER_ARCHETYPES inside the model would keep dragging experiments back to the
single dimension of "feeding frequency".

Two sets of experiments:

  FEEDING  — the old control arm (feeding frequency). Kept, because it already carries
             the history of 011–017.
  WORLDS   — the new main line (environment). Same seed, same initial personality, only
             the world changes.
"""

import statistics
from collections import Counter

import sim
from sim import Life, World

# ============================================================
# 1. Feeding frequency (old control arm)
# ============================================================
# ⚠ These three are not properties of the Agent, they are **definitions of experiment arms**.
#    All the Agent ever sees is "there is more food in the world today".

FEEDING = {
    "doting":     1.0,   # fed the moment it is hungry
    "balanced":   3.0,
    "hands-off":  8.0,   # often away for days
}

# ============================================================
# 2. Environment (new main line)
# ============================================================
# Note ⑥: stop comparing doting vs hands-off. Put the same Agent into different worlds instead.
#
#   rich vs barren environment / books vs no books / music vs silence /
#   frequent rain vs stable weather / material-rich vs material-scarce
#
# Every world gets the same medium feeding, so "how diligent the user is" is held fixed
# and only the environment itself varies.

_BASE_FEED = 3.0

WORLDS = {
    # --- control ---
    "baseline":         dict(),
    # --- resources ---
    "food-rich":        dict(food_regen=3.2),
    "food-poor":        dict(food_regen=1.8),
    "material-rich":    dict(material_yield=2.0),
    "material-scarce":  dict(material_yield=0.5),
    # --- weather ---
    "rainy":            dict(storm_chance=0.16),
    "stable weather":   dict(storm_chance=0.0),
    # --- objects ---
    "has books":        dict(objects=("book",)),
    "has music":        dict(objects=("music",)),
    # --- combinations: Experiment A / B from the notes ---
    "rich world":       dict(food_regen=3.2, material_yield=2.0,
                        objects=("book", "music"), storm_chance=0.02),
    "barren world":     dict(food_regen=1.8, material_yield=0.5,
                        objects=(), storm_chance=0.10),
}


# ============================================================
# Construction
# ============================================================

def make(seed, name, *, world_seed=None, days=None):
    """Make one life by name. The name may be a FEEDING key or a WORLDS key."""
    if name in FEEDING:
        world = World(seed if world_seed is None else world_seed)
        infl = [sim.give_food(2.0, FEEDING[name])]
    elif name in WORLDS:
        world = World(seed if world_seed is None else world_seed, **WORLDS[name])
        infl = [sim.give_food(2.0, _BASE_FEED)]
    else:
        raise KeyError(f"unknown experiment arm: {name}")
    return Life(seed, world=world, influences=infl)


def run(seed, name, **kw):
    """Make + run, return the agent. Analysis scripts use this.

    The returned agent carries a `.scenario` label — that is the **experiment ledger**,
    used by analysis scripts for grouping; the model never reads it while running.
    (Contrast v1: back then `archetype` was a constructor argument of the Agent and
    directly determined its behaviour.)
    """
    days = kw.pop("days", None)
    agent = make(seed, name, **kw).run(days)
    agent.scenario = name
    return agent


# ============================================================
# Population report (used to live in sim.py's main)
# ============================================================

def histogram(values, lo=0, hi=100, bins=20, width=46):
    counts = [0] * bins
    for v in values:
        counts[min(bins - 1, int((v - lo) / (hi - lo) * bins))] += 1
    peak = max(counts) or 1
    for b in range(bins):
        print(f"  {lo + (hi - lo) * b / bins:5.0f} | "
              f"{'█' * int(counts[b] / peak * width)} {counts[b]}")


def main(population=999):
    names = list(FEEDING)
    print("=" * 62)
    print(f" Population report   {population} balls × {sim.SIM_DAYS} days")
    print(f" PERSONALITY_WEIGHT={sim.PERSONALITY_WEIGHT}  "
          f"TRAIT_DRIFT={sim.TRAIT_DRIFT}")
    print("=" * 62)

    agents = [run(n, names[n % len(names)]) for n in range(population)]
    alive = [a for a in agents if a.alive]
    dead = len(agents) - len(alive)
    print(f"\nalive {len(alive)}/{len(agents)}   dead {dead} "
          f"({dead / len(agents):.1%})")
    for i, name in enumerate(names):
        grp = [a for n, a in enumerate(agents) if n % len(names) == i]
        d = sum(1 for a in grp if not a.alive) / len(grp)
        print(f"    {name}: mortality {d:5.1%}")

    print("\n[by experiment arm] mean personality")
    print(f"  {'arm':<8} {'caution':>14} {'curiosity':>14} {'industry':>14}")
    for i, name in enumerate(names):
        grp = [a for n, a in enumerate(agents)
               if n % len(names) == i and a.alive]
        cells = "".join(
            f"{statistics.mean([a.traits[t] for a in grp]):9.1f}"
            f"±{statistics.pstdev([a.traits[t] for a in grp]):4.1f}"
            for t in sim.TRAITS)
        print(f"  {name:<8}{cells}")

    print("\n[distribution of caution]")
    histogram([a.traits["caution"] for a in alive])
    print(f"  σ = {statistics.pstdev([a.traits['caution'] for a in alive]):.1f}")

    print("\n[personality types that emerged on their own]")
    for style, n in Counter(a.dominant_style() for a in alive).most_common():
        print(f"  {style:<8} {n:4d}  {'▇' * int(n / len(alive) * 44)}")

    print("\n[trigger rate of landmark experiences]")
    for flag, label in [("fears_hunger", "got through hunger"),
                        ("fears_storm", "had the roof torn off by a storm"),
                        ("loves_exploring", "found a rich place far away"),
                        ("reads", "read something new")]:
        n = sum(1 for a in alive if flag in a.flags)
        print(f"  {label:<16} {n:4d}  ({n / len(alive):5.1%})")


if __name__ == "__main__":
    main()
