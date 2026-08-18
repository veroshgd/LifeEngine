"""
State levelling — is that ever-widening caution curve a discovery or an artefact?
=================================================================================

Run:  python leveling.py

## The two things to tell apart

After being transplanted into the same neutral world, the caution gap **keeps widening**:

    day30   +30    +60    +90
     19.4   26.9   30.9   33.2      (growth +7.5 / +4.0 / +2.3, looks like convergence to 35)

Two readings, an order of magnitude apart in value:

    strong  differentiation is self-sustaining. The barren twin carries its knowledge / goals /
            personality and keeps generating caution-raising experiences in the neutral world → path dependence
    weak    state confound. It simply has not recovered yet — worse condition, less stored food,
            no house — so it keeps meeting things that make it more cautious → a recovery curve, not personality

## How to tell them apart

At the moment of transplant, force the **state** to be level (identical on both sides), leaving
only **personality / memory / goals** different. Then see whether caution still keeps widening.

    keeps widening  → strong reading. The difference is self-sustained by internal structure
    flattens at once → weak reading. The earlier curve was the shadow of state recovery

⚠ Levelling hands the "explorer" twin a set of possessions (house/food store) it never had.
   That is deliberate: the question we are asking is precisely "**apart from possessions**, what else still differs".
"""

import statistics

import sim
import scenarios
from paired import pad

SEEDS = 200
SPLIT = 30
CHECKS = (30, 60, 90, 120)
WA, WB = "rich world", "barren world"
COMMON = "baseline"

# Which state to level to. Take a moderately comfortable point, identical on both sides
LEVEL = {"hunger": 30.0, "energy": 80.0, "shelter": 50.0,
         "condition": 100.0, "food": 3.0, "material": 0.0}


def apply_level(agent):
    agent.hunger = LEVEL["hunger"]
    agent.energy = LEVEL["energy"]
    agent.shelter = LEVEL["shelter"]
    agent.condition = LEVEL["condition"]
    agent.inventory = {"food": LEVEL["food"], "material": LEVEL["material"]}
    # Accumulated hardship is an "experience", not a "state" — deliberately not cleared, it belongs on the memory side


def run_tracked(seed, first, second, level):
    """Run to max(CHECKS) days, recording personality and state at each checkpoint"""
    life = scenarios.make(seed, first)
    agent = life.agent
    snaps = {}
    for day in range(max(CHECKS)):
        if day == SPLIT:
            w = sim.World(seed, **scenarios.WORLDS[second])
            life.world = w
            agent.world = w
            if level:
                apply_level(agent)
        for t in range(sim.TICKS_PER_DAY):
            life.world.tick(day, t)
            for inf in life.influences:
                inf(life.world, agent, day, t, life.inf_rng)
            agent.tick(day, t)
            if not agent.alive:
                return snaps          # ★keep the checkpoints already recorded before death★
        agent.daily(day)
        if day + 1 in CHECKS:
            snaps[day + 1] = {
                **{t: agent.traits[t] for t in sim.TRAITS},
                "condition": agent.condition, "shelter": agent.shelter,
                "food": agent.inventory["food"], "hardship": agent.hardship,
            }
    return snaps


def curve(level):
    """★Compute the surviving set separately at each checkpoint★

    If a single "those alive at day 120" set were used, every row would be dominated by the same
    survivors — and the survivors are precisely "the balls that did not run off", which is exactly
    what the caution curve is about, i.e. selecting the sample by the conclusion. Changed to
    per-point settlement: the day-60 row uses every pair alive at day 60.
    """
    A = [run_tracked(s, WA, COMMON, level) for s in range(SEEDS)]
    B = [run_tracked(s, WB, COMMON, level) for s in range(SEEDS)]
    out = {}
    for d in CHECKS:
        live = [i for i in range(SEEDS) if d in A[i] and d in B[i]]
        if not live:
            continue
        out[d] = {k: statistics.mean(B[i][d][k] - A[i][d][k] for i in live)
                  for k in A[live[0]][d]}
        out[d]["loss"] = 1 - len(live) / SEEDS
        out[d]["n"] = len(live)
    return out, None


def show(title, data, n):
    print(f"\n{title}")
    keys = list(sim.TRAITS) + ["condition", "shelter", "food", "hardship"]
    print(f"  {pad('day', 8)}" + "".join(pad(k[:9], 12, True) for k in keys)
          + pad("valid pairs", 13, True) + pad("loss", 9, True))
    for d in CHECKS:
        if d not in data:
            continue
        tag = f"day {d}" + (" (transplant)" if d == SPLIT else "")
        flag = "  ⚠" if data[d]["loss"] > 0.15 else ""
        print(f"  {pad(tag, 8)}"
              + "".join(pad(f"{data[d][k]:+.1f}", 12, True) for k in keys)
              + pad(f"{data[d]['n']}", 11, True)
              + pad(f"{data[d]['loss']:.1%}", 9, True) + flag)
    caut = [data[d]["caution"] for d in CHECKS if d in data]
    gains = [caut[i + 1] - caut[i] for i in range(len(caut) - 1)]
    print(f"  caution increment: " + "  ".join(f"{g:+.1f}" for g in gains))
    return gains


def main():
    print("=" * 104)
    print(f" State-levelling experiment   {SEEDS} seeds   {WA} ↔ {WB}, "
          f"both enter **{COMMON}** on day {SPLIT}")
    print("=" * 104)
    print("  difference = barren twin − rich twin. After the transplant point, does caution keep widening?")

    raw, n_raw = curve(level=False)
    g_raw = show("[control] no levelling (= the earlier curve)", raw, n_raw)

    lev, n_lev = curve(level=True)
    g_lev = show("[treatment] state levelled at transplant (only personality/memory/goals differ)", lev, n_lev)

    print("\n" + "=" * 104)
    print(" Verdict  ★using only checkpoints with pair loss ≤15%★")
    print("=" * 104)
    # The survivors are precisely "the balls that did not run off", which is what this curve is about — contaminated points must be dropped
    clean = [d for d in CHECKS if d in raw and d in lev
             and raw[d]["loss"] <= 0.15 and lev[d]["loss"] <= 0.15]
    dropped = [d for d in CHECKS if d not in clean]
    print(f"  checkpoints used: {clean}"
          + (f"   dropped (survivor contamination): {dropped}" if dropped else ""))

    def total(data):
        return data[clean[-1]]["caution"] - data[clean[0]]["caution"]

    tot_raw, tot_lev = total(raw), total(lev)
    print(f"\n  caution growth after the transplant (days {clean[0]}→{clean[-1]})")
    print(f"    not levelled  {tot_raw:+.1f}")
    print(f"    levelled      {tot_lev:+.1f}   (relative {tot_lev / tot_raw:.0%})")

    # The core prediction of the weak reading: the barren twin is in worse shape, so it keeps meeting things that make it more cautious
    cond = lev[clean[-1]]["condition"]
    print(f"\n  Test of the weak reading: at day {clean[-1]} after levelling, the barren twin's condition differs by {cond:+.1f}")
    print("    The weak reading predicts this should be **negative** (it has not recovered yet).")

    print()
    if tot_lev >= 0.6 * tot_raw and tot_lev > 1.0:
        print("  ★ strong reading holds: the gap widens even after state levelling → differentiation is self-sustained by internal structure")
        if cond > 0:
            print("    and the barren twin is in **better** condition — it has not failed to recover, it is living better.")
    elif tot_lev <= 0.25 * tot_raw:
        print("  ✗ weak reading: no growth after levelling → the earlier curve was the shadow of state recovery")
    else:
        print("  ~ both: partly self-sustaining, partly state recovery")


if __name__ == "__main__":
    main()
