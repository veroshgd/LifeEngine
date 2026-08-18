"""
Paired experiment — same seed, different users
==============================================

Run:  python paired.py

Why this script exists
----------------------
`significance.py` asks: "do the means of the three groups of balls differ much?"
But that is not the question in the user's mind, which is:

    "if someone else had raised it, would it have turned out different?"

A group comparison cannot answer that, because the balls in each group already carry
different initial seeds, and the difference caused by the seed (σ≈34) is far larger than
the difference caused by the user. The user's signal drowns in it.

What a paired experiment does instead: **run the same seed twice, changing only the user.**
Initial personality identical → the largest noise source, the seed, is cancelled → what is
left is the user's contribution.

Two benefits:
  1. Far more sensitive (measured: paired 11.6× the standard error vs grouped 7.2×)
  2. It asks exactly the question the product has to answer

★ One limitation that must be admitted
--------------------------------------
The same seed only guarantees the same **initial state**. Once the actions of the two runs
diverge, the rng streams fall out of step, and the later storms / gathering successes differ too.
So pairing cancels "seed noise" but not "world-luck noise".
The sign-permutation test below exists to treat the latter as the null hypothesis.

Noise floor (following the lesson of experiment 009)
----------------------------------------------------
The correct null-hypothesis test for paired data is **sign permutation**:
if the user has no systematic effect, then which way each pair's difference leans is random,
and flipping the signs of the differences at random should not change the conclusion. Flip
2000 times and see where the observed mean lands.
"""

import random
import statistics
import unicodedata
from collections import Counter

import sim
import scenarios

SEEDS         = 400     # how many seeds to run (each × 3 kinds of user)
DAYS          = 30
N_PERM        = 2000    # number of sign permutations
VISIBLE_DELTA = 5.0     # how many points apart before a pair counts as "really different"

HEADLINE = ("doting", "hands-off")   # the two extremes; the main result reads this pair

# Carriers: personality / state — the notes concluded the latter two are the strong signals, so measure both
CARRIERS = [
    ("personality", "caution",   lambda a: a.traits["caution"]),
    ("personality", "curiosity", lambda a: a.traits["curiosity"]),
    ("personality", "industry",  lambda a: a.traits["industry"]),
    ("state",       "condition", lambda a: a.condition),
    ("state",       "shelter",   lambda a: a.shelter),
]

FLAGS = [("fears_hunger", "hunger-scarred"),
         ("fears_storm",  "storm-fearing"),   # control arm: an act of god, there should be no difference
         ("loves_exploring", "exploration-loving")]


# ---------- mixed-width alignment (format counts characters, so wide glyphs misalign) ----------

def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def pad(s, n, right=False):
    s = str(s)
    fill = " " * max(0, n - _w(s))
    return fill + s if right else s + fill


# ---------- statistics ----------

def signflip_p(diffs, n_perm, rng):
    """Sign-permutation test (two-sided). Null: the differences are symmetric about 0, i.e. the user has no systematic effect."""
    obs = abs(statistics.mean(diffs))
    n = len(diffs)
    hits = 0
    for _ in range(n_perm):
        tot = 0.0
        for d in diffs:
            tot += d if rng.getrandbits(1) else -d
        if abs(tot / n) >= obs:
            hits += 1
    return hits / n_perm


def describe(diffs, perm_rng=None):
    """Full description of one set of paired differences"""
    n = len(diffs)
    mean = statistics.mean(diffs)
    sd = statistics.pstdev(diffs)
    return {
        "n": n,
        "mean": mean,
        # ★The median matters more than the mean★ If the mean is non-zero but the median is 0,
        # the effect is not "every ball changed a little" but "the vast majority did not change
        # at all and a few changed drastically".
        # For the product these are completely different: the latter means most users feel nothing.
        "median": statistics.median(diffs),
        "sd": sd,
        "se": sd / n ** 0.5 if n else 0.0,
        # dz = paired effect size. 0.2 small / 0.5 medium / 0.8 large
        "dz": mean / sd if sd else 0.0,
        # 50% = no effect; the further from 50%, the more stable the direction
        "pos": sum(1 for d in diffs if d > 0) / n,
        "big": sum(1 for d in diffs if abs(d) >= VISIBLE_DELTA) / n,
        "p": signflip_p(diffs, N_PERM, perm_rng) if perm_rng else None,
    }


# ---------- run the simulations ----------

def run_all():
    sim.SIM_DAYS = DAYS
    return {(s, arch): scenarios.run(s, arch)
            for s in range(SEEDS)
            for arch in scenarios.FEEDING}


def valid_pairs(world, a_name, b_name):
    """Pairs alive on both sides. The dead are reported separately and must not be mixed into means (survivorship bias)"""
    both, only_a_died, only_b_died = [], 0, 0
    for s in range(SEEDS):
        a, b = world[(s, a_name)], world[(s, b_name)]
        if a.alive and b.alive:
            both.append((a, b))
        elif a.alive:
            only_b_died += 1
        else:
            only_a_died += 1
    return both, only_a_died, only_b_died


# ---------- report ----------

def main():
    rng = random.Random(0)
    print("=" * 78)
    print(f" Paired experiment   same seed, different users   "
          f"{SEEDS} seeds × {DAYS} days   {N_PERM} sign permutations")
    print("=" * 78)

    world = run_all()

    # --- survival: death is itself a user effect, so look at it separately first ---
    print("\n[survival rate]")
    for arch in scenarios.FEEDING:
        alive = sum(1 for s in range(SEEDS) if world[(s, arch)].alive)
        print(f"  {pad(arch, 10)}{alive / SEEDS:6.1%}")

    # --- main result: the pairing of the two extremes ---
    a_name, b_name = HEADLINE
    pairs, a_died, b_died = valid_pairs(world, a_name, b_name)
    print(f"\n[{a_name} → {b_name}] {len(pairs)} valid pairs"
          f" ({a_name} died alone {a_died}, {b_name} died alone {b_died})")
    print(f"  {pad('carrier', 24)}{pad('mean diff', 12, True)}{pad('median', 10, True)}"
          f"{pad('dz', 7, True)}{pad('share increased', 17, True)}"
          f"{pad('|d|≥5', 8, True)}{pad('p', 8, True)}")
    print("  " + "-" * 74)

    headline_dz = None
    for kind, label, get in CARRIERS:
        st = describe([get(b) - get(a) for a, b in pairs], rng)
        if label == "industry":
            headline_dz = st["dz"]
        note = ""
        if st["p"] >= 0.05:
            note = "   ← noise"
        elif abs(st["median"]) < 0.5 <= abs(st["mean"]):
            note = "   ← median 0: most balls did not change at all"
        print(f"  {pad(kind + ' ' + label, 20)}{pad(f'{st['mean']:+.2f}', 11, True)}"
              f"{pad(f'{st['median']:+.2f}', 10, True)}{pad(f'{st['dz']:+.2f}', 7, True)}"
              f"{pad(f'{st['pos']:.1%}', 12, True)}{pad(f'{st['big']:.1%}', 8, True)}"
              f"{pad(f'{st['p']:.3f}', 8, True)}{note}")

    print("\n  How to read:")
    print("    median          ★the column to watch★ median≈0 while the mean is non-zero")
    print("                    = attribution is all-or-nothing, not gradual → most users feel nothing")
    print("    dz              paired effect size. 0.2 small / 0.5 medium / 0.8 large")
    print("    share increased 50% = no effect. The further off, the more stable the direction")
    print("    |d|≥5           share of pairs where the difference is actually visible")

    # --- event carrier: the difference shows up in "what happened" ---
    print(f"\n[irreversible events] {a_name} → {b_name}   pairs where only one side fired (discordant pairs)")
    print(f"  {pad('event', 22)}{pad('only ' + b_name, 16, True)}"
          f"{pad('only ' + a_name, 16, True)}{pad('net diff', 10, True)}")
    for key, label in FLAGS:
        only_b = sum(1 for a, b in pairs if key in b.flags and key not in a.flags)
        only_a = sum(1 for a, b in pairs if key in a.flags and key not in b.flags)
        net = (only_b - only_a) / len(pairs)
        print(f"  {pad(label, 12)}{pad(only_b, 14, True)}{pad(only_a, 14, True)}"
              f"{pad(f'{net:+.1%}', 9, True)}")
    print(f"  (\"storm-fearing\" is the control arm: an act of god, so the two columns should be close — it is the self-check of the measurement pipeline)")

    # --- dose response: a real signal should be monotone ---
    print("\n[dose response] less feeding → larger effect? A real signal should increase monotonically")
    order = ["doting", "balanced", "hands-off"]
    print(f"  {pad('comparison', 24)}" + "".join(pad(l, 13, True) for _, l, _ in CARRIERS))
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            pr, _, _ = valid_pairs(world, order[i], order[j])
            row = "".join(
                pad(f"{statistics.mean([g(b) - g(a) for a, b in pr]):+.2f}", 13, True)
                for _, _, g in CARRIERS)
            print(f"  {pad(order[i] + '→' + order[j], 20)}{row}")

    # --- product criteria ---
    same = sum(1 for a, b in pairs if a.dominant_style() == b.dominant_style())
    flip = 1 - same / len(pairs)
    print("\n" + "=" * 78)
    print(" Product criterion: change the user, and does this ball become something else?")
    print("=" * 78)
    print(f"  share whose personality label changed   {flip:6.1%}      target > 50%")
    print("    (the criterion-ordering bug was fixed in experiment 015; but the label still reads"
          " personality numbers, and the behaviour-layer metrics show personality and behaviour can"
          " decouple — for the main result see behavior.py)")
    changed = Counter(f"{a.dominant_style()} → {b.dominant_style()}"
                      for a, b in pairs if a.dominant_style() != b.dominant_style())
    for k, v in changed.most_common(5):
        print(f"      {pad(k, 26)}{v:4d}")

    # Pairs where the user changed but hardly any carrier moved — this is the most direct product criterion
    untouched = sum(
        1 for a, b in pairs
        if all(abs(get(b) - get(a)) < VISIBLE_DELTA for _, _, get in CARRIERS)
        and a.flags == b.flags)
    print(f"\n  pairs where the user changed but **no carrier moved**   {untouched / len(pairs):6.1%}"
          f"      target < 20%")
    print("    No matter how these users raise it, they end up with the same ball.")

    print(f"\n  ★ the four numbers to track (compare these four lines after a config change)")
    print(f"      industry effect size dz   {headline_dz:+.3f}   target > 0.8")
    print(f"      pairs with no change      {untouched / len(pairs):6.1%}   target < 20%")
    print(f"      personality-label flip    {flip:6.1%}   target > 50%")
    dead = 1 - sum(1 for s in range(SEEDS) if world[(s, 'hands-off')].alive) / SEEDS
    print(f"      hands-off mortality       {dead:6.1%}   target < 10%")


if __name__ == "__main__":
    main()
