"""
Persistence — once the cause is removed, which environmental factor still holds?
================================================================================

Run:  python persistence.py

`transplant.py` showed that the difference of the combined worlds (rich↔barren) retains 91%
after a transplant. This script **splits that combination into single factors** and asks the
same question of each one:

    days 0–29    world A / world B          ← creates the difference
    days 30–59   both switched to "baseline"  ← removes the cause
    measured only on the second 30-day window

★ The main metric is **persistence**, not **current difference** ★
A difference that exists only while "the current conditions differ" is a thermometer, not a
personality. The line the product wants — "there was a heavy rain once… ever since then I have
not liked being unprepared" — requires it to **still** exist after the transplant.

★ The mechanistic hypothesis to test ★
Whether a factor survives depends on **whether it was written into a persistent structure**:

    knowledge (semantic memory)  ·  trait_identity (permanent identity)  ·  flags (landmark experiences)

Prediction: books > weather > material > food rate.
Books are written into knowledge ("books hold worlds I have not seen") and generate a `learn` goal;
the food regrowth rate is written into no persistent structure at all — it is only the current
resource level. If this prediction holds, then **persistence comes from structure, not from strength**.
"""

import statistics
from collections import Counter

import sim
import scenarios
from behavior import ACTIONS, GLANCE
from transplant import run_phased, window_tv, SPLIT, TOTAL
from paired import pad

SEEDS = 150
COMMON = "baseline"

# Single-factor pairs + the combination as a reference
FACTORS = [
    ("has books",     COMMON,            "books"),
    ("has music",     COMMON,            "music"),
    ("rainy",         "stable weather",  "weather"),
    ("material-rich", "material-scarce", "material"),
    ("food-rich",     "food-poor",       "food rate"),
    ("rich world",    "barren world",    "combination (reference)"),
]

GOAL_TYPES = list(sim.GOAL_ACTIONS)


def goal_profile_window(agent):
    """★Goal layer★ only what it pursued each day inside the window.

    This is the strongest carrier found in 018: the ratio of goal TV is generally above that of
    routine TV, and it can be stated in one sentence ("it has spent the last fortnight hoarding
    food"), which also makes it the most natural interface once an LLM is wired in.
    """
    days = [g for g in agent.goal_by_day[SPLIT:TOTAL] if g]
    n = len(days) or 1
    return {g: days.count(g) / n for g in GOAL_TYPES}


def goal_tv(a, b):
    pa, pb = goal_profile_window(a), goal_profile_window(b)
    return 0.5 * sum(abs(pa[g] - pb[g]) for g in GOAL_TYPES)


_COHORT_CACHE = {}


def cohort(first, second, seeds):
    """★Cached★ six factors × four cohorts, so the baseline world would be recomputed many times.
    With 120-day runs and multi-direction restoration coming, that cost becomes painful."""
    key = (first, second, len(seeds))
    if key not in _COHORT_CACHE:
        _COHORT_CACHE[key] = [run_phased(s, first, second) for s in seeds]
    return _COHORT_CACHE[key]


def measure(cohA, cohB, seeds):
    """Return the routine ratio, the goal ratio, and the differences in persistent structure"""
    live = [i for i, (a, b) in enumerate(zip(cohA, cohB))
            if a[0] is not None and b[0] is not None]
    if len(live) < 20:
        return None
    pairs = [(cohA[i], cohB[i]) for i in live]

    # The baseline uses only seeds alive on both sides — otherwise the filtered within-group variance is too small and the ratio is inflated
    base = []
    for coh in (cohA, cohB):
        al = [coh[i] for i in live]
        base += [(al[j], al[j + 1]) for j in range(0, len(al) - 1, 2)]

    hu = statistics.mean(window_tv(a[1], b[1]) for a, b in pairs)
    hb = statistics.mean(window_tv(a[1], b[1]) for a, b in base)
    gu = statistics.mean(goal_tv(a[0], b[0]) for a, b in pairs)
    gb = statistics.mean(goal_tv(a[0], b[0]) for a, b in base)

    # Persistent structure: what did this factor leave on the ball?
    # ⚠ The first version computed len(b) - len(a), which is "how many more B has than A", not
    #    "how far the two differ". Two balls with 3 **completely different** knowledge entries each
    #    would score 0 — a systematic underestimate. Changed to the symmetric difference of the
    #    sets (how many entries only one side has).
    def keys(agent):
        return (set(agent.knowledge),
                {t for t, v in agent.trait_identity.items() if v > 0},
                set(agent.flags))

    def symdiff(i):
        return statistics.mean(len(keys(a[0])[i] ^ keys(b[0])[i])
                               for a, b in pairs)

    dk, di, df = symdiff(0), symdiff(1), symdiff(2)

    return {
        "hr": hu / hb if hb else 0.0, "gr": gu / gb if gb else 0.0,
        "n": len(pairs), "dead": 1 - len(pairs) / len(cohA),
        "dk": dk, "di": di, "df": df,
        "traits": {t: statistics.mean(b[0].traits[t] - a[0].traits[t]
                                      for a, b in pairs) for t in sim.TRAITS},
    }


def main():
    seeds = list(range(SEEDS))
    print("=" * 100)
    print(f" Persistence experiment   {SEEDS} seeds   days 0–{SPLIT-1} diverge, "
          f"days {SPLIT}–{TOTAL-1} measured in the **baseline world**")
    print("=" * 100)
    print("  \"stay\" = second half spent in the original world (cause still present)   "
          "\"move\" = second half switched to baseline on both sides (cause removed)")
    print(f"\n  {pad('factor', 24)}{pad('stay routine', 14, True)}{pad('move routine', 14, True)}"
          f"{pad('retained', 10, True)}{pad('stay goal', 12, True)}"
          f"{pad('move goal', 12, True)}{pad('retained', 10, True)}{pad('dead', 8, True)}")
    print("  " + "-" * 84)

    rows = []
    for wa, wb, label in FACTORS:
        stay = measure(cohort(wa, wa, seeds), cohort(wb, wb, seeds), seeds)
        move = measure(cohort(wa, COMMON, seeds), cohort(wb, COMMON, seeds), seeds)
        if stay is None or move is None:
            print(f"  {pad(label, 24)}  — not enough samples")
            continue
        keep_h = move["hr"] / stay["hr"] if stay["hr"] else 0
        keep_g = move["gr"] / stay["gr"] if stay["gr"] else 0
        rows.append((label, stay, move, keep_h, keep_g))
        star = "  ★" if move["hr"] >= 1.0 or move["gr"] >= 1.0 else ""
        print(f"  {pad(label, 14)}{pad(f'{stay['hr']:.2f}', 11, True)}"
              f"{pad(f'{move['hr']:.2f}', 11, True)}{pad(f'{keep_h:.0%}', 8, True)}"
              f"{pad(f'{stay['gr']:.2f}', 11, True)}{pad(f'{move['gr']:.2f}', 11, True)}"
              f"{pad(f'{keep_g:.0%}', 8, True)}"
              f"{pad(f'{move['dead']:.1%}', 8, True)}{star}")

    print("\n  ★ = the ratio is still ≥ 1 after the transplant, i.e. the difference survives removing the cause")

    # --- mechanism: do the factors that survive get written into persistent structure? ---
    print("\n" + "=" * 100)
    print(" Mechanism check: were the surviving factors written into persistent structure?")
    print("=" * 100)
    print(f"  {pad('factor', 24)}{pad('routine after move', 20, True)}{pad('goal after move', 18, True)}"
          f"{pad('semantic memory diff', 22, True)}{pad('permanent identity diff', 25, True)}"
          f"{pad('landmark diff', 15, True)}")
    for label, stay, move, kh, kg in rows:
        print(f"  {pad(label, 14)}{pad(f'{move['hr']:.2f}', 12, True)}"
              f"{pad(f'{move['gr']:.2f}', 12, True)}"
              f"{pad(f'{move['dk']:.2f}', 12, True)}"
              f"{pad(f'{move['di']:.2f}', 12, True)}"
              f"{pad(f'{move['df']:.2f}', 12, True)}")
    print("\n  All three columns are **symmetric differences**: how many entries on average exist on only one side (larger = more different)")
    print("  semantic memory = knowledge keys   permanent identity = non-zero trait_identity dimensions   "
          "landmark = flags")
    print("  Hypothesis: only factors written into these three survive; factors that only move the resource level do not.")
    print("  ⚠ But knowledge and memories currently **do not enter score()** — they are written and never read,")
    print("     so a large first column does not mean it survives behaviourally — see experiment 019 rule 30.")

    # --- run the restoration phase in three directions ---
    # ⚠ "baseline" is not neutral: its objects are empty, so on the question of "are there books"
    #    it equals the barren world. A rich twin moved there **loses its books**, and the whole
    #    `learn` goal channel is cut away; the barren twin loses nothing. That is an asymmetric
    #    adaptation cost which would contaminate the result. So the restoration phase must be run
    #    in at least three directions.
    print("\n" + "=" * 100)
    print(" Direction dependence of the restoration phase: transplanted into different worlds, is the conclusion the same?")
    print("=" * 100)
    print(f"  {pad('factor', 24)}" + "".join(pad(f"→{d}", 16, True)
                                            for d in ("baseline", "rich world", "barren world")))
    for wa, wb, label in FACTORS:
        cells = ""
        for dest in ("baseline", "rich world", "barren world"):
            m = measure(cohort(wa, dest, seeds), cohort(wb, dest, seeds), seeds)
            cells += pad(f"{m['hr']:.2f}" if m else "—", 14, True)
        print(f"  {pad(label, 14)}{cells}")
    print("\n  Large differences between directions → what we measured is mixed with the cost of \"having to re-adapt after the move\",")
    print("  not pure persistence. Only ≥1 in all three directions counts as solid.")

    # --- residual personality ---
    print("\n" + "=" * 100)
    print(" Personality difference still present 30 days after the transplant (second − first)")
    print("=" * 100)
    print(f"  {pad('factor', 24)}" + "".join(pad(t, 13, True) for t in sim.TRAITS))
    for label, stay, move, kh, kg in rows:
        print(f"  {pad(label, 14)}"
              + "".join(pad(f"{move['traits'][t]:+.1f}", 13, True)
                        for t in sim.TRAITS))


if __name__ == "__main__":
    main()
