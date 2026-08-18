"""⚠ DEPRECATED (experiment 018)
⚠ DEPRECATED — superseded by param_sweep.py. Kept as experiment history; do not use for new analysis.
=====================================================================================================
Two reasons:
  1. The criterion `spread > 8` is below the noise floor at its own population size
     (at pop=300 the 95th percentile of noise is 10.48, at pop=450 it is 9.18) → it would award ★ to pure noise
  2. Group comparison has been superseded by the paired experiment in paired.py, which is far more sensitive

The file is kept only for historical traceability. Use instead:
    python paired.py     numeric layer
    python behavior.py   behaviour layer
    python ablation.py   mechanism contribution
"""

raise SystemExit(__doc__)

"""
Food-economy sweep — find the point where "the ball can survive, but not comfortably"

The core tension:
  self-sufficiency too high → the user is redundant → no attribution (spread=6)
  self-sufficiency too low  → hands-off balls die → retention collapses

Goal: hands-off survives but lives on the edge; doting has plenty of slack.
"""

import statistics
from collections import Counter

import sim


def evaluate(regen, pop=450, days=30):
    sim.LOCAL_FOOD_REGEN = regen
    sim.SIM_DAYS = days

    names = list(sim.USER_ARCHETYPES)
    agents = [sim.Agent(seed=n, archetype=names[n % len(names)]).run()
              for n in range(pop)]
    alive = [a for a in agents if a.alive]
    if len(alive) < pop * 0.3:
        return None

    spread = 0.0
    for t in sim.TRAITS:
        means = [statistics.mean([a.traits[t] for a in alive if a.archetype == n])
                 for n in names]
        spread = max(spread, max(means) - min(means))

    # Mortality per user type — this now matters more than the overall mortality
    death_by = {}
    for n in names:
        grp = [a for a in agents if a.archetype == n]
        death_by[n] = sum(1 for a in grp if not a.alive) / len(grp)

    styles = Counter(a.dominant_style() for a in alive)
    peaks = sum(1 for _, c in styles.items() if c >= len(alive) * 0.08)

    return {
        "spread": spread,
        "death_total": 1 - len(alive) / pop,
        "death_by": death_by,
        "peaks": peaks,
        "starve_flag": sum(1 for a in alive if "fears_hunger" in a.flags) / len(alive),
        "sigma": statistics.pstdev([a.traits["caution"] for a in alive]),
    }


def main():
    print("=" * 78)
    print(" Food-economy sweep   daily demand ≈ 2.64 portions")
    print(" Goal: spread>8, total mortality<10%, hands-off mortality<20%")
    print("=" * 78)
    print(f"{'regen':>6} | {'spread':>7} {'σ':>6} {'peaks':>6} | "
          f"{'dead all':>9} {'doting':>8} {'balanced':>10} {'hands-off':>11} | {'hunger-scarred':>16}")
    print("-" * 78)

    best = None
    for regen in (2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.4):
        r = evaluate(regen)
        if r is None:
            print(f"{regen:>6.1f} |  ——  wiped out")
            continue
        d = r["death_by"]
        ok = (r["spread"] > 8 and r["death_total"] < 0.10
              and d["hands-off"] < 0.20 and r["peaks"] >= 3)
        mark = "  ★" if ok else ""
        print(f"{regen:>6.1f} | {r['spread']:>7.1f} {r['sigma']:>6.1f} "
              f"{r['peaks']:>6} | {r['death_total']:>6.1%} "
              f"{d['doting']:>8.1%} {d['balanced']:>10.1%} {d['hands-off']:>11.1%} | "
              f"{r['starve_flag']:>6.1%}{mark}")
        if ok and (best is None or r["spread"] > best[1]["spread"]):
            best = (regen, r)

    print("=" * 78)
    if best:
        print(f" ★ best: LOCAL_FOOD_REGEN = {best[0]}   "
              f"spread={best[1]['spread']:.1f}   "
              f"total mortality={best[1]['death_total']:.1%}")
    else:
        print(" No point satisfies all criteria at once — survival and differentiation are still squeezing"
              " each other; the ball needs a way to save itself without the user (but at a cost).")


if __name__ == "__main__":
    main()
