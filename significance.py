"""
Does the spread metric mean anything at all? — a permutation test

Problem: spread takes "the largest mean difference across three user types × three personality
         dimensions". Taking a maximum inflates noise by itself. The standard deviation of
         personality is about 34, so with n balls per group the standard error of the mean is
         ≈ 34/√n; taking the max over 9 combinations yields a sizeable number from pure chance.

Method: shuffle the user-type labels N times, recompute spread, and obtain the "null distribution".
        If the real spread falls inside that distribution, it is noise.
"""

import random
import statistics

import sim
import scenarios


def spread_of(alive, labels):
    """Compute spread for a given set of labels"""
    names = list(scenarios.FEEDING)
    best = 0.0
    for t in sim.TRAITS:
        means = []
        for n in names:
            vals = [a.traits[t] for a, lb in zip(alive, labels) if lb == n]
            if vals:
                means.append(statistics.mean(vals))
        if len(means) >= 2:
            best = max(best, max(means) - min(means))
    return best


def main(pop=999, days=30, n_perm=400):
    names = list(scenarios.FEEDING)
    agents = [scenarios.run(n, names[n % len(names)]) for n in range(pop)]
    alive = [a for a in agents if a.alive]

    real_labels = [a.scenario for a in alive]
    observed = spread_of(alive, real_labels)

    # Null hypothesis: shuffle the labels
    null = []
    shuffled = list(real_labels)
    rng = random.Random(0)
    for _ in range(n_perm):
        rng.shuffle(shuffled)
        null.append(spread_of(alive, shuffled))

    null.sort()
    p95 = null[int(0.95 * len(null))]
    p99 = null[int(0.99 * len(null))]
    p_value = sum(1 for v in null if v >= observed) / len(null)

    print("=" * 66)
    print(f" spread significance test   {len(alive)} alive, {n_perm} permutations")
    print("=" * 66)
    print(f"  observed spread          : {observed:6.2f}")
    print(f"  null median (pure noise)  : {statistics.median(null):6.2f}")
    print(f"  null 95th percentile      : {p95:6.2f}   ← must clear this line to count as signal")
    print(f"  null 99th percentile      : {p99:6.2f}")
    print(f"  p value                  : {p_value:6.3f}")
    print()
    if p_value < 0.05:
        print("  ✓ user type really does explain the personality difference (the signal is real)")
    else:
        print("  ✗ the observed value falls inside the noise range — this spread is an artefact of taking a maximum.")
        print("    Conclusion: user behaviour currently has **no measurable effect** on personality.")

    # Also give a metric that is not contaminated by taking a maximum
    print()
    print("  Each dimension on its own (no maximum taken):")
    for t in sim.TRAITS:
        by = {}
        for n in names:
            vals = [a.traits[t] for a in alive if a.scenario == n]
            by[n] = (statistics.mean(vals), statistics.pstdev(vals), len(vals))
        rng_span = max(m for m, _, _ in by.values()) - min(m for m, _, _ in by.values())
        # between-group difference / pooled standard error
        se = max((s / (c ** 0.5)) for _, s, c in by.values())
        print(f"    {t:<10} largest between-group diff {rng_span:5.2f}   "
              f"single-group SE {se:4.2f}   diff/SE = {rng_span / se:4.1f}")


if __name__ == "__main__":
    main()
