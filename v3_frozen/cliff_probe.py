"""
Cliff probe — one sampling run answering three questions at once
================================================================

Run:  python cliff_probe.py

§3g left a to-do: "first sweep 58/60/62/65/68/70 to locate the cliff". But a sweep can only
confirm where the cliff is; it cannot explain **why** it is there, nor answer a reviewer's
"why 65?". And a sweep misses a more pressing risk (question 3).

So instead of sweeping thresholds, this samples three things at once:

  ① the per-tick distribution of hunger
     The cliff can be **computed** straight from the distribution, no sweep needed:
         net condition/tick(T) = COND_RECOVER·P(hunger<T) − COND_DRAIN·P(hunger>70)
     one distribution → a prediction of the whole curve → then 2–3 points to verify is enough.

  ② the **support width** of the distribution
     Hunger is a sawtooth: +2.2 per tick, −20 per meal. So the support is only about 20 points
     wide, and both step thresholds (COND_DRAIN_AT=70 and COND_RECOVER_AT) sit inside those 20 points.
     ★If the support really is only 20 points wide, the cliff is structural★ —
     any parameter that shifts the sawtooth (HUNGER_RATE / FOOD_NUTRITION / food regrowth)
     will make mortality step. A sweep cannot remove that, only record it.

  ③ ⚠ is the hardship channel still there — the risk the criteria table cannot see
     sim.py:936  hardship += (100−condition)/100 / 24
     sim.py:941  trait_floor ← hardship_norm × 22          ← the ratchet lives here
     sim.py:890  at condition ≥ 99.5, hardship is instead **forgotten**
     Raising the recovery threshold = condition permanently high = deficit≈0 = **the ratchet is cut off**.
     And that ratchet is exactly what experiment 021 §3 and 022 are studying.
     The criteria table cannot see it: the no-floor column already has the floors switched off.

Only the barren world is run → transplanted to baseline on day 30 (the setup of rule 47);
all statistics take only the ticks after the transplant (day ≥ 30).
"""

import statistics
import sys
from collections import Counter

import sim
import scenarios
import persistence_ablation as PA

WB, COMMON = "barren world", "baseline"
N = 60
SPLIT, TOTAL = 30, 120
BIN = 2.5                      # hunger histogram resolution
NBINS = int(100 / BIN) + 1

# (label, recovery threshold, dead-zone recovery, shelter recovery)
VARIANTS = [
    ("status quo",     30.0, 0.00, 0.00),
    ("① threshold 55", 55.0, 0.00, 0.00),
    ("① threshold 60", 60.0, 0.00, 0.00),
    ("① threshold 65", 65.0, 0.00, 0.00),
    ("③ shelter +0.10", 30.0, 0.00, 0.10),
]


def run_one(seed, floor_off):
    """Run 120 days. Returns (day of death or None, hunger histogram, final-state dict)"""
    scenarios.make = PA.patched_make(False, floor_off)
    try:
        life = scenarios.make(seed, WB)
    finally:
        scenarios.make = PA._orig_make
    agent = life.agent
    hist = [0] * NBINS

    def phase(d0, d1, record):
        for day in range(d0, d1):
            for t in range(sim.TICKS_PER_DAY):
                life.world.tick(day, t)
                for inf in life.influences:
                    inf(life.world, agent, day, t, life.inf_rng)
                agent.tick(day, t)
                if record:
                    hist[min(NBINS - 1, int(agent.hunger / BIN))] += 1
                if not agent.alive:
                    return day
            agent.daily(day)
        return None

    d = phase(0, SPLIT, False)
    if d is not None:
        return d, hist, snapshot(agent, floor_off)
    w = sim.World(seed, **scenarios.WORLDS[COMMON])
    life.world = w
    agent.world = w
    d = phase(SPLIT, TOTAL, True)
    return d, hist, snapshot(agent, floor_off)


def snapshot(agent, floor_off):
    """Final state: the three readings of the hardship channel + condition"""
    lift = 0.0
    if not floor_off:      # with floors off, trait_floor is FrozenZero and the boost is meaningless
        lift = max(agent.trait_floor[t] - agent.trait_identity[t]
                   for t in sim.TRAITS)
    return dict(condition=agent.condition,
                hardship=agent.hardship,
                hnorm=agent.hardship_norm,
                lift=lift,
                fears="fears_hunger" in agent.flags)


def net_budget(hist, T):
    """Net condition/tick from the histogram: +COND_RECOVER·P(hunger<T) − COND_DRAIN·P(hunger>70)"""
    tot = sum(hist) or 1
    lo = sum(hist[i] for i in range(NBINS) if (i + 0.5) * BIN < T)
    hi = sum(hist[i] for i in range(NBINS) if (i + 0.5) * BIN > sim.COND_DRAIN_AT)
    return (sim.COND_RECOVER * lo - sim.COND_DRAIN * hi) / tot, lo / tot, hi / tot


def pct(hist, q):
    tot = sum(hist)
    if not tot:
        return float("nan")
    target, acc = tot * q, 0
    for i in range(NBINS):
        acc += hist[i]
        if acc >= target:
            return (i + 0.5) * BIN
    return 100.0


def run_variant(label, rec_at, dz, sh, floor_off):
    sim.COND_RECOVER_AT, sim.COND_DEADZONE_RECOVER, sim.COND_SHELTER_RECOVER = rec_at, dz, sh
    hist = [0] * NBINS
    dead, snaps = 0, []
    for s in range(N):
        d, h, snap = run_one(s, floor_off)
        if d is not None:
            dead += 1
        else:
            snaps.append(snap)         # hardship counts survivors only, to avoid contamination by near-death states
        hist = [a + b for a, b in zip(hist, h)]
    return dead / N, hist, snaps


def main():
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02

    for floor_off in (False, True):
        arch = "all floors off (the contamination source of rule 44)" if floor_off else "full architecture"
        print("=" * 100)
        print(f" Cliff probe · {arch} · N={N} seeds · barren→baseline@30 · ticks with day≥30")
        print("=" * 100)

        rows = []
        for label, rec_at, dz, sh in VARIANTS:
            rows.append((label, rec_at) + run_variant(label, rec_at, dz, sh, floor_off))

        # ---- ① hunger distribution + support width ----
        print(f"\n  [hunger distribution] how wide is the sawtooth support? (width ≈ FOOD_NUTRITION = "
              f"{sim.FOOD_NUTRITION:.0f} means a structural cliff)")
        print(f"  {'fix':<18}{'dead%':>8}{'p5':>7}{'p25':>7}{'median':>8}{'p75':>7}"
              f"{'p95':>7}{'p5–p95 width':>14}{'P(hunger>70)':>14}")
        print("  " + "-" * 88)
        for label, _, dead, hist, _ in rows:
            p5, p95 = pct(hist, .05), pct(hist, .95)
            _, _, hi = net_budget(hist, 30)
            print(f"  {label:<14}{dead:>7.1%}{p5:>7.1f}{pct(hist,.25):>7.1f}"
                  f"{pct(hist,.5):>7.1f}{pct(hist,.75):>7.1f}{p95:>7.1f}"
                  f"{p95-p5:>10.1f}{hi:>10.1%}")

        # ---- cliff prediction: net balance vs threshold ----
        Ts = [30, 40, 45, 50, 55, 58, 60, 62, 65, 68, 70]
        print(f"\n  [cliff prediction] net condition/tick = {sim.COND_RECOVER}·P(hunger<T) − "
              f"{sim.COND_DRAIN}·P(hunger>70), extrapolated from the \"status quo\" distribution")
        print("  " + " " * 8 + "".join(f"{t:>7}" for t in Ts))
        for label, _, _, hist, _ in rows[:1] + rows[-1:]:
            print(f"  {label:<8}" + "".join(
                f"{net_budget(hist,t)[0]:>7.3f}" for t in Ts))
        print("  (>0 is required for a steady state; the sign flip is the cliff. Per-variant predictions from each variant's own distribution are below)")
        print("  " + " " * 8 + "".join(f"{t:>7}" for t in Ts))
        for label, _, _, hist, _ in rows:
            print(f"  {label:<8}" + "".join(
                f"{net_budget(hist,t)[0]:>7.3f}" for t in Ts))

        # ---- ③ the hardship channel ----
        print(f"\n  [hardship ratchet] ⚠ the risk the criteria table cannot see (survivors only)")
        print(f"  {'fix':<18}{'final cond':>12}{'hardship':>10}{'hnorm':>8}"
              f"{'floor boost':>13}{'fears_hunger%':>14}")
        print("  " + "-" * 66)
        for label, _, _, _, snaps in rows:
            if not snaps:
                print(f"  {label:<18}{'—— wiped out ——':>50}")
                continue
            m = lambda k: statistics.mean(s[k] for s in snaps)
            fr = sum(s["fears"] for s in snaps) / len(snaps)
            lift = f"{m('lift'):>10.2f}" if not floor_off else f"{'n/a':>10}"
            print(f"  {label:<14}{m('condition'):>8.1f}{m('hardship'):>10.2f}"
                  f"{m('hnorm'):>8.3f}{lift}{fr:>13.0%}")
        print("\n  hnorm → floor boost = HARDSHIP_MAX_BOOST(22) × hnorm (sim.py:941)")
        print("  hnorm collapsed = the ratchet is cut off = the very mechanism studied in 021 §3 / 022 has been changed\n")

    sim.COND_RECOVER_AT, sim.COND_DEADZONE_RECOVER, sim.COND_SHELTER_RECOVER = 30.0, 0.0, 0.0


if __name__ == "__main__":
    main()
