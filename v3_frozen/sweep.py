"""⚠ DEPRECATED (experiment 018)
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
Parameter sweep — finding "that narrow band"

Run:  python sweep.py

The right parameters cannot be reasoned out, only swept. This script runs one population per
parameter set and reports three criteria:

  spread  personality gap between user types   goal > 8    ← the core selling point
  peaks   number of (effective) personality types  goal >= 3   ← multimodality
  death   mortality                            goal < 10%
"""

import statistics
from collections import Counter

import sim


def evaluate(pw, drift, hunger, pop=300, days=30):
    sim.PERSONALITY_WEIGHT = pw
    sim.TRAIT_DRIFT = drift
    sim.HUNGER_RATE = hunger
    sim.SIM_DAYS = days

    names = list(sim.USER_ARCHETYPES)
    agents = [sim.Agent(seed=n, archetype=names[n % len(names)]).run()
              for n in range(pop)]
    alive = [a for a in agents if a.alive]
    if len(alive) < pop * 0.4:
        return {"spread": 0.0, "peaks": 0, "death": 1 - len(alive) / pop,
                "sigma": 0.0, "styles": Counter()}

    # Largest personality gap between user types
    spread = 0.0
    for t in sim.TRAITS:
        means = [statistics.mean([a.traits[t] for a in alive if a.archetype == n])
                 for n in names]
        spread = max(spread, max(means) - min(means))

    styles = Counter(a.dominant_style() for a in alive)
    peaks = sum(1 for _, n in styles.items() if n >= len(alive) * 0.08)
    sigma = statistics.pstdev([a.traits["caution"] for a in alive])

    return {"spread": spread, "peaks": peaks,
            "death": 1 - len(alive) / pop, "sigma": sigma, "styles": styles}


def main():
    grid = [(pw, dr, hr)
            for pw in (8, 18, 30, 45)
            for dr in (0.55, 1.2)
            for hr in (2.2, 1.2, 0.7)]

    print("=" * 74)
    print(" Parameter sweep  ——  goal: spread>8, peaks>=3, death<10%")
    print("=" * 74)
    print(f"{'PW':>4} {'drift':>6} {'hunger':>7} | {'spread':>7} {'peaks':>6} "
          f"{'death':>7} {'sigma':>6} |")
    print("-" * 74)

    results = []
    for pw, dr, hr in grid:
        r = evaluate(pw, dr, hr)
        results.append(((pw, dr, hr), r))
        ok = "  ★" if (r["spread"] > 8 and r["peaks"] >= 3
                       and r["death"] < 0.10) else ""
        print(f"{pw:>4} {dr:>6.2f} {hr:>7.1f} | {r['spread']:>7.1f} "
              f"{r['peaks']:>6} {r['death']:>6.1%} {r['sigma']:>6.1f} |{ok}")

    winners = [(p, r) for p, r in results
               if r["spread"] > 8 and r["peaks"] >= 3 and r["death"] < 0.10]

    print("\n" + "=" * 74)
    if winners:
        winners.sort(key=lambda x: -x[1]["spread"])
        print(f" Found {len(winners)} usable parameter sets. Best:")
        (pw, dr, hr), r = winners[0]
        print(f"   PERSONALITY_WEIGHT = {pw}")
        print(f"   TRAIT_DRIFT        = {dr}")
        print(f"   HUNGER_RATE        = {hr}")
        print(f"\n   spread={r['spread']:.1f}  peaks={r['peaks']}  "
              f"death={r['death']:.1%}")
        print("   types that emerged on their own:")
        for s, n in r["styles"].most_common():
            print(f"     {s:<8} {n:4d}")
    else:
        print(" No parameter set satisfies all three criteria — this is a structural problem, not a tuning problem.")
        best = max(results, key=lambda x: x[1]["spread"])
        print(f" Closest: PW={best[0][0]} drift={best[0][1]} "
              f"hunger={best[0][2]}  spread={best[1]['spread']:.1f}")


if __name__ == "__main__":
    main()
