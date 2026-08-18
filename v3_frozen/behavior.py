"""
Behaviour-layer metrics — is the difference the user makes actually visible?
============================================================================

Run:  python behavior.py

Why this script is needed
-------------------------
The ablation experiment (014) exposed a blind spot: set `PERSONALITY_WEIGHT` to 0 and
personality numbers stop affecting behaviour **entirely** — yet industry dz only fell 4%.

    → meaning every metric we had was measuring "a difference in a number",
      and none of them was measuring "a difference in behaviour".

And what the user sees is behaviour. [[Design points and risks]] §5.5 puts it plainly:
"two balls at caution 78 vs 45 — if their outward behaviour looks the same, the user
cannot perceive it."

This script supplies that missing layer.

Three metrics
-------------
1. **Total variation distance TV of the action distribution** — the fraction of time the
   two balls spend on different things. TV ∈ [0,1], readable directly as "what percentage
   of the daily routine differs".

2. **Routine difference** — of the 24 hours in a day, how many have a different dominant
   action. This is the "daily routine" §5.5 asked for by name, and the best demo material.

3. **Visibly distinct features** — has a home / looks thin / has food stored / often out.
   This is what the user can actually *see*.

★ Noise floor (rule 9: a new metric must have its noise floor measured first)
-----------------------------------------------------------------------------
TV is always positive, so sign permutation cannot be used. The correct control here is:

    TV_user  = same seed, different user        ← behavioural difference caused by the user
    TV_base  = same user, different seed        ← difference the two balls have anyway

**TV_user must be clearly above TV_base**, otherwise "my ball is different from yours"
and "balls just differ anyway" cannot be told apart — and then the user still will not
feel it is the one they raised.

The two are compared with a permutation test on two independent samples.
"""

import random
import statistics

import sim
import scenarios
from paired import pad

SEEDS = 300
DAYS = 30
N_PERM = 2000
A_NAME, B_NAME = "doting", "hands-off"

ACTIONS = list(sim.ACTION_TRAIT_MATCH)
GLYPH = {"eat": "Ea", "sleep": "Sl", "gather_food": "Gf",
         "gather_material": "Gm", "build": "Bu", "explore": "Ex", "read": "Rd"}

# Visibly distinct features — what the user can really see
GLANCE = [
    ("has a real home",  lambda a: a.shelter >= 50),
    ("looks healthy",    lambda a: a.condition >= 90),
    ("has food stored",  lambda a: a.inventory["food"] >= 3),
    ("often out",        lambda a: profile(a)["explore"] >= 0.20),
]


GOAL_TYPES = list(sim.GOAL_ACTIONS)


def profile(agent):
    """Action distribution (normalised)"""
    tot = sum(agent.action_log.values()) or 1
    return {a: agent.action_log[a] / tot for a in ACTIONS}


def goal_profile(agent):
    """★Main carrier★ how many days of a lifetime went to each kind of goal.

    Why it is the main carrier (experiment 019):
      · stronger than routine — on the feeding axis the routine ratio is 0.72, the goal ratio 1.79
      · attributable — a goal carries `created_from`, traceable to the experience that generated it
      · sayable in one sentence — "it has spent the last fortnight hoarding food"; a routine
        distribution cannot say that
      · the most natural interface once an LLM is wired in (context_packet is built around it)
    """
    days = [g for g in agent.goal_by_day if g]
    n = len(days) or 1
    return {g: days.count(g) / n for g in GOAL_TYPES}


def goal_tv(a, b):
    pa, pb = goal_profile(a), goal_profile(b)
    return 0.5 * sum(abs(pa[g] - pb[g]) for g in GOAL_TYPES)


def tv(p, q):
    """Total variation distance. 0 = identical routines, 1 = no overlap at all"""
    return 0.5 * sum(abs(p[a] - q[a]) for a in ACTIONS)


def rhythm(agent):
    """The dominant action in each of the 24 hours. ★Demo printing only, never use as a metric★"""
    return [c.most_common(1)[0][0] if c else None for c in agent.action_by_hour]


def rhythm_diff(a, b):
    """Number of hours whose dominant action differs.
    ⚠ This metric is unreliable; kept only as a control. See the note on mode_margin()."""
    ra, rb = rhythm(a), rhythm(b)
    return sum(1 for x, y in zip(ra, rb) if x != y)


def mode_margin(agent):
    """Within each hour, how far the top action leads the runner-up (difference in share).

    ★Why this function exists★
    After experiment 016 rhythm_diff jumped from 5.05 to 10.58, which looked like the
    behavioural difference had grown. In fact this margin collapsed from 0.40 to 0.16 — the
    balls began to interleave several actions, the top action leads the runner-up by only 16
    percentage points, and so a tiny perturbation flips the "dominant action".
    **What rhythm_diff measures is the fragility of the mode, not the difference in behaviour.**
    Evidence: the baseline rose in step from 7.73 to 13.88, and the ratio barely moved.
    """
    ms = []
    for c in agent.action_by_hour:
        tot = sum(c.values()) or 1
        t2 = c.most_common(2)
        ms.append(1.0 if len(t2) < 2 else (t2[0][1] - t2[1][1]) / tot)
    return statistics.mean(ms)


def hour_profile(agent):
    """The action distribution within each hour"""
    out = []
    for c in agent.action_by_hour:
        tot = sum(c.values()) or 1
        out.append({a: c[a] / tot for a in ACTIONS})
    return out


def hourly_tv(a, b):
    """★The correct measure of routine difference★ compare distributions hour by hour, then average.

    Strictly more sensitive than the aggregated TV (aggregation can only shrink distances, by
    convexity), and without the flip-fragility of the "dominant action".
    """
    pa, pb = hour_profile(a), hour_profile(b)
    return sum(0.5 * sum(abs(pa[h][x] - pb[h][x]) for x in ACTIONS)
               for h in range(len(pa))) / len(pa)


def perm_diff_p(g1, g2, n_perm, rng):
    """Two independent samples: how much of the mean difference could come from random grouping"""
    obs = abs(statistics.mean(g1) - statistics.mean(g2))
    pool = list(g1) + list(g2)
    n1 = len(g1)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        if abs(statistics.mean(pool[:n1]) - statistics.mean(pool[n1:])) >= obs:
            hits += 1
    return hits / n_perm


def main():
    rng = random.Random(0)
    sim.SIM_DAYS = DAYS
    print("=" * 78)
    print(f" Behaviour-layer metrics   {SEEDS} seeds × {DAYS} days   pairing: {A_NAME} → {B_NAME}")
    print("=" * 78)

    world = {(s, arch): scenarios.run(s, arch)
             for s in range(SEEDS) for arch in scenarios.FEEDING}

    # Behavioural difference caused by the user: same seed, different user
    pairs = [(world[(s, A_NAME)], world[(s, B_NAME)]) for s in range(SEEDS)
             if world[(s, A_NAME)].alive and world[(s, B_NAME)].alive]
    tv_user = [tv(profile(a), profile(b)) for a, b in pairs]

    # Baseline: same user, different seed. Both are computed — doting may be naturally more homogeneous
    base = {}
    for arch in (A_NAME, B_NAME):
        alive = [world[(s, arch)] for s in range(SEEDS) if world[(s, arch)].alive]
        base[arch] = [tv(profile(alive[i]), profile(alive[i + 1]))
                      for i in range(0, len(alive) - 1, 2)]

    print(f"\n[1. total variation distance of the action distribution] {len(pairs)} pairs")
    print(f"  {pad('comparison', 30)}{pad('mean TV', 10, True)}"
          f"{pad('median', 10, True)}{pad('n', 7, True)}")
    print("  " + "-" * 55)
    print(f"  {pad('caused by user (same seed, swap user)', 38)}"
          f"{pad(f'{statistics.mean(tv_user):.3f}', 10, True)}"
          f"{pad(f'{statistics.median(tv_user):.3f}', 10, True)}"
          f"{pad(len(tv_user), 7, True)}")
    for arch, vals in base.items():
        print(f"  {pad(f'baseline (both {arch}, swap seed)', 38)}"
              f"{pad(f'{statistics.mean(vals):.3f}', 10, True)}"
              f"{pad(f'{statistics.median(vals):.3f}', 10, True)}"
              f"{pad(len(vals), 7, True)}")

    pooled_base = base[A_NAME] + base[B_NAME]
    ratio = statistics.mean(tv_user) / statistics.mean(pooled_base) \
        if statistics.mean(pooled_base) else float("inf")
    p = perm_diff_p(tv_user, pooled_base, N_PERM, rng)
    print(f"\n  user / baseline = {ratio:.2f}×      permutation test p = {p:.3f}")
    if ratio < 1.2:
        print("  ✗ the behavioural difference caused by the user is no larger than the balls' innate difference")
        print("    → the user cannot perceive that this one is theirs")
    elif p < 0.05:
        print("  ✓ the behavioural difference caused by the user is significantly above baseline")

    # Which behaviours are changing
    print("\n[action level: where the time flows from and to] (hands-off − doting)")
    for act in ACTIONS:
        d = [profile(b)[act] - profile(a)[act] for a, b in pairs]
        m = statistics.mean(d)
        bar = ("+" if m >= 0 else "-") * min(30, int(abs(m) * 300))
        print(f"  {pad(act, 18)}{pad(f'{m:+.1%}', 9, True)}  {bar}")

    # 2. Routine — compare distributions hour by hour, not "dominant action"
    print("\n[2. routine difference] action distribution per hour, then averaged")
    base_pairs = []
    for arch in (A_NAME, B_NAME):
        al = [world[(s, arch)] for s in range(SEEDS) if world[(s, arch)].alive]
        base_pairs += [(al[i], al[i + 1]) for i in range(0, len(al) - 1, 2)]
    hu = [hourly_tv(a, b) for a, b in pairs]
    hb = [hourly_tv(a, b) for a, b in base_pairs]
    print(f"  caused by user TV(per hour)   {statistics.mean(hu):.3f}")
    print(f"  baseline                      {statistics.mean(hb):.3f}"
          f"      ratio {statistics.mean(hu) / statistics.mean(hb):.2f}×")
    margin = statistics.mean(mode_margin(world[(s, A_NAME)]) for s in range(SEEDS))
    print(f"\n  (control) hours with a different dominant action   user "
          f"{statistics.mean(rhythm_diff(a, b) for a, b in pairs):5.2f}/24   "
          f"baseline {statistics.mean(rhythm_diff(a, b) for a, b in base_pairs):5.2f}/24")
    print(f"  ⚠ do not read the line above on its own: the lead of the dominant action is only {margin:.2f},"
          f" so the mode flips easily")
    print(f"    in experiment 016 it rose from 5.05 to 10.58, but the baseline rose in step from 7.73 to 13.88 "
          f"— what rose was fragility, not difference")

    # ★Main carrier★ the goal layer
    print("\n[★ main carrier: the goal layer] days of a lifetime spent on each goal")
    gu = [goal_tv(a, b) for a, b in pairs]
    gb = [goal_tv(a, b) for a, b in base_pairs]
    gr = statistics.mean(gu) / statistics.mean(gb) if statistics.mean(gb) else 0
    print(f"  caused by user {statistics.mean(gu):.3f}   baseline {statistics.mean(gb):.3f}"
          f"   ratio {gr:.2f}×")
    if gr >= 1.0:
        print("  ✓ on the goal layer, the difference caused by the user **exceeds** the balls' innate difference")
    print(f"  {pad('goal', 24)}{pad(f'{A_NAME} share', 14, True)}"
          f"{pad(f'{B_NAME} share', 14, True)}{pad('diff', 9, True)}")
    for g in GOAL_TYPES:
        pa = statistics.mean(goal_profile(a)[g] for a, _ in pairs)
        pb = statistics.mean(goal_profile(b)[g] for _, b in pairs)
        print(f"  {pad(sim.GOAL_LABEL[g], 18)}{pad(f'{pa:.1%}', 12, True)}"
              f"{pad(f'{pb:.1%}', 12, True)}{pad(f'{pb - pa:+.1%}', 9, True)}")

    # 3. Visibly distinct
    print("\n[3. visibly distinct features] pairs where only one side holds")
    print(f"  {pad('feature', 20)}{pad(f'only {B_NAME}', 16, True)}"
          f"{pad(f'only {A_NAME}', 16, True)}{pad('mismatch rate', 15, True)}")
    for label, test in GLANCE:
        only_b = sum(1 for a, b in pairs if test(b) and not test(a))
        only_a = sum(1 for a, b in pairs if test(a) and not test(b))
        print(f"  {pad(label, 16)}{pad(only_b, 14, True)}{pad(only_a, 14, True)}"
              f"{pad(f'{(only_a + only_b) / len(pairs):.1%}', 12, True)}")
    any_diff = sum(1 for a, b in pairs
                   if any(t(a) != t(b) for _, t in GLANCE)) / len(pairs)
    print(f"\n  ★ pairs differing in at least one feature: {any_diff:.1%}      target > 60%")
    print("    This is the share the user can notice at a glance, without looking at any number.")

    # Demo material: take the most different pair and print its routine
    print("\n" + "=" * 78)
    print(" demo material: same seed, two users, one day of routine")
    print("=" * 78)
    idx = max(range(len(pairs)), key=lambda i: tv_user[i])
    a, b = pairs[idx]
    print(f"  hour       " + "".join(f"{h:>2}" for h in range(24)))
    for agent, name in ((a, A_NAME), (b, B_NAME)):
        line = "".join(GLYPH.get(x, " ·") for x in rhythm(agent))
        print(f"  {pad(name, 10)} {line}")
    print(f"\n  {pad(A_NAME, 10)} {a.dominant_style()}   "
          f"shelter {a.shelter:.0f}  condition {a.condition:.0f}  "
          f"industry {a.traits['industry']:.0f}")
    print(f"  {pad(B_NAME, 10)} {b.dominant_style()}   "
          f"shelter {b.shelter:.0f}  condition {b.condition:.0f}  "
          f"industry {b.traits['industry']:.0f}")
    for agent, name in ((a, A_NAME), (b, B_NAME)):
        if agent.landmarks:
            print(f"  {name} remembers: " +
                  "; ".join(f"day {d + 1}: {t}" for d, t in agent.landmarks))
    print("\n  legend: " + "  ".join(f"{v}={k}" for k, v in GLYPH.items()))


if __name__ == "__main__":
    main()
