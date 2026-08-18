"""
Persistence ablation — of what survives the transplant, how much is "hardcoded"?
================================================================================

Run:  python persistence_ablation.py

`transplant.py` shows the difference retains 90%+ after a transplant. But the architecture contains
**three** mechanisms whose only job is to make a difference more persistent, and all three are hand-written:

    ① trait_identity   permanent floor, monotonically increasing (the max() at sim.py:463)
    ② trait_floor      soft floor, retreating only 0.35 per day and never below ①
    ③ TRAIT_SATURATION the more extreme, the harder to change (pull as low as 0.12 = 8.3× slower)

③ was added in this version to cure the 60-day wipeout. But it doubles as a **persistence mechanism**:
a ball pushed to caution=90 has extremity=0.8 → pull=0.28, so it drifts back at only a third of the
speed of a mid-range ball. That is not consolidation, that is a multiplier.

The sentence a reviewer will say:
    "you did not discover irreversibility, you wrote irreversibility in."

This script answers it. It also supplies the missing null control (both twins walk the same world).
"""

import statistics

import sim
import scenarios
from transplant import run_phased, window_tv, SPLIT, TOTAL
from behavior import GLANCE

SEEDS = 150
WA, WB = "rich world", "barren world"
COMMON = "baseline"


class FrozenZero(dict):
    """A floor that cannot be written: it always reads 0"""
    def __init__(self):
        super().__init__({t: 0.0 for t in sim.TRAITS})

    def __setitem__(self, k, v):
        pass


_orig_make = scenarios.make


def patched_make(kill_identity=False, kill_floor=False):
    def make(seed, name, **kw):
        life = _orig_make(seed, name, **kw)
        if kill_identity or kill_floor:
            life.agent.trait_identity = FrozenZero()
        if kill_floor:
            life.agent.trait_floor = FrozenZero()
        return life
    return make


CONDITIONS = [
    ("full architecture",       dict()),
    ("− saturation (③)",        dict(sat=0.0)),
    ("− permanent identity (①)", dict(ident=True)),
    ("− all floors (①②)",       dict(floor=True)),
    ("− all three off",         dict(sat=0.0, floor=True)),
]


def run_condition(cfg, first_a, first_b):
    """Run the transplant experiment under one ablation condition and return the retention and other metrics"""
    sat_backup = sim.TRAIT_SATURATION
    if "sat" in cfg:
        sim.TRAIT_SATURATION = cfg["sat"]
    scenarios.make = patched_make(cfg.get("ident", False), cfg.get("floor", False))
    try:
        stay_a = [run_phased(s, first_a, first_a) for s in range(SEEDS)]
        stay_b = [run_phased(s, first_b, first_b) for s in range(SEEDS)]
        mov_a = [run_phased(s, first_a, COMMON) for s in range(SEEDS)]
        mov_b = [run_phased(s, first_b, COMMON) for s in range(SEEDS)]
    finally:
        sim.TRAIT_SATURATION = sat_backup
        scenarios.make = _orig_make

    def ratio(cA, cB):
        live = [i for i in range(SEEDS)
                if cA[i][0] is not None and cB[i][0] is not None]
        if len(live) < 20:
            return None
        num = statistics.mean(window_tv(cA[i][1], cB[i][1]) for i in live)
        base = []
        for coh in (cA, cB):
            al = [coh[i] for i in live]
            base += [(al[j], al[j + 1]) for j in range(0, len(al) - 1, 2)]
        den = statistics.mean(window_tv(x[1], y[1]) for x, y in base)
        traits = {t: statistics.mean(cB[i][0].traits[t] - cA[i][0].traits[t]
                                     for i in live) for t in sim.TRAITS}
        eye = sum(1 for i in live
                  if any(f(cA[i][0]) != f(cB[i][0]) for _, f in GLANCE)) / len(live)
        return {"r": num / den if den else 0, "traits": traits,
                "dead": 1 - len(live) / SEEDS, "eye": eye, "n": len(live)}

    return ratio(stay_a, stay_b), ratio(mov_a, mov_b)


def main():
    print("=" * 104)
    print(f" Persistence ablation   {SEEDS} seeds   {WA} ↔ {WB} → {COMMON}")
    print("=" * 104)
    print(f"  {'condition':<26}{'stay ratio':>12}{'move ratio':>12}{'retained':>10}"
          f"{'visibly distinct':>18}{'dead':>8}   personality diff after move")
    print("  " + "-" * 100)

    for label, cfg in CONDITIONS:
        stay, move = run_condition(cfg, WA, WB)
        if stay is None or move is None:
            print(f"  {label:<26}  — not enough samples (too many died)")
            continue
        keep = move["r"] / stay["r"] if stay["r"] else 0
        tr = "  ".join(f"{t[:2]} {move['traits'][t]:+5.1f}" for t in sim.TRAITS)
        print(f"  {label:<16}{stay['r']:>10.2f}{move['r']:>10.2f}{keep:>7.0%}"
              f"{move['eye']:>10.1%}{move['dead']:>8.1%}   {tr}")

    # ---- Null hypothesis: both twins walk the same world ----
    print("\n" + "=" * 104)
    print(" Null control: both twins spend the first 30 days in **the same** world, then both enter baseline")
    print(" (this measures \"how far two runs differ anyway\". This variant should carry no signal.)")
    print("=" * 104)
    for w in (WA, WB):
        stay, move = run_condition(dict(), w, w)
        if move:
            print(f"  both sides in \"{w}\"   move ratio {move['r']:.2f}   "
                  f"visibly distinct {move['eye']:.1%}   "
                  + "  ".join(f"{t[:2]} {move['traits'][t]:+5.1f}"
                              for t in sim.TRAITS))

    print("\n  How to read:")
    print("    move ratio ≥ 1        →  with the cause removed, the difference still exceeds the balls' innate difference")
    print("    still ≥ 1 with floors off  →  the persistence comes from the dynamics; it is a discovery")
    print("    collapses with floors off  →  the persistence comes from those max() calls; it is an assumption")
    print("    the two null rows must be close to 0, otherwise the measurement pipeline leaks")


if __name__ == "__main__":
    main()
