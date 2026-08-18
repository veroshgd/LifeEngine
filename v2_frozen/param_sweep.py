"""
Parameter-randomisation set — answering "is this just a hand-tuned parameter set?"
==================================================================================

Run:  python param_sweep.py                    # default 500 configs × 300 seeds
       python param_sweep.py --configs 2000     # denser
       python param_sweep.py --seed-offset 10000 --out holdout.csv   # holdout set

Not a grid scan. N parameter sets are drawn independently from a prior, the transplant experiment
is re-run for each, and what is reported is **the distribution of the effect** rather than a point.
The conclusion reads like this:

    "across 500 randomly sampled parameter configurations, X% have a transplant ratio > 1, median 1.Y"

What a reviewer asks is "how do I know this isn't a parameter artifact", and this sentence is the
only thing that answers it directly.

★ Three methodological corrections (relative to transplant.py) ★
  1. The baseline uses K=5 **random** pairings, not adjacent pairing.
     Balls from adjacent seeds are more alike → baseline too small → ratio inflated by 2.2% (measured).
  2. The log ratio is reported too. A ratio = ratio of means, and a noisy denominator biases it systematically upward (Jensen).
  3. Mortality is written to disk as well. Extreme parameter draws wipe the population out, and those rows must be dropped at analysis time.

Resumable: results are flushed to the CSV row by row, and re-running the same command after an interruption skips the configs already done.
"""

import argparse
import csv
import math
import multiprocessing as mp
import os
import random
import statistics
import sys
import time

WA, WB, COMMON = "rich world", "barren world", "baseline"
BASE_PAIRINGS = 5          # number of random baseline pairings (K=5 measured to be saturated)

# Priors: ("logu", lo, hi) log-uniform · ("u", lo, hi) uniform · ("int", lo, hi) integer
# The ranges are roughly ×0.5 ~ ×2 of the default
PRIORS = {
    "PERSONALITY_WEIGHT":  ("logu", 15.0, 60.0),    # default 30.0
    "TRAIT_DRIFT":         ("logu", 0.60, 2.40),    # default 1.20
    "TRAIT_SATURATION":    ("u",    0.00, 0.98),    # default 0.90
    "LANDMARK_BONUS":      ("logu", 12.5, 50.0),    # default 25.0
    "HARDSHIP_MAX_BOOST":  ("logu", 11.0, 44.0),    # default 22.0
    "FLOOR_DECAY_PER_DAY": ("logu", 0.17, 0.70),    # default 0.35
    "LANDMARK_PERMANENT":  ("u",    0.10, 0.80),    # default 0.40
    "GOAL_BONUS":          ("logu", 16.0, 64.0),    # default 32.0
    "GOAL_OFF_TASK":       ("logu",  7.0, 28.0),    # default 14.0
    "GOAL_SWITCH_MARGIN":  ("logu", 0.125, 0.50),   # default 0.25
    "GOAL_MIN_DAYS":       ("int",   1,    4),      # default 2
    "GOAL_REFRACTORY":     ("int",   3,   12),      # default 6
    "GOAL_STALL_DAYS":     ("int",   2,    8),      # default 4
    "GOAL_SLACK_FOOD":     ("logu",  2.0,  8.0),    # default 4.0 (rule 27)
    "GOAL_SLACK_COND":     ("u",    60.0, 100.0),   # default 90.0
}

PARAM_NAMES = list(PRIORS)
FIELDS = (["config_id"] + PARAM_NAMES +
          ["n_move", "n_stay", "dead_move", "dead_stay",
           "ratio_move", "logratio_move", "ratio_stay",
           "goal_ratio_move", "keep"])


def sample_config(config_id):
    """config_id determines the parameters — the same id always draws the same set, so a resumed run is reproducible"""
    rng = random.Random(0xC0FFEE + config_id)
    out = {}
    for name, spec in PRIORS.items():
        kind, lo, hi = spec
        if kind == "logu":
            out[name] = math.exp(rng.uniform(math.log(lo), math.log(hi)))
        elif kind == "u":
            out[name] = rng.uniform(lo, hi)
        else:
            out[name] = rng.randint(lo, hi)
    return out


def _shuffled_baseline(windows, k, rng, tv):
    """K independent random pairings. Each ball is used K times, with far lower variance than a single adjacent pairing."""
    out = []
    idx = list(range(len(windows)))
    for _ in range(k):
        rng.shuffle(idx)
        out += [tv(windows[idx[j]], windows[idx[j + 1]])
                for j in range(0, len(idx) - 1, 2)]
    return out


def evaluate(args):
    """Run one parameter set. Executed in a subprocess — changes to sim globals affect this process only."""
    config_id, n_seeds, seed_offset = args
    import sim
    import scenarios
    from transplant import run_phased, window_tv, SPLIT, TOTAL

    cfg = sample_config(config_id)
    for name, value in cfg.items():
        setattr(sim, name, value)

    goal_types = list(sim.GOAL_ACTIONS)

    def goal_tv(a, b):
        def prof(ag):
            days = [g for g in ag.goal_by_day[SPLIT:TOTAL] if g]
            n = len(days) or 1
            return {g: days.count(g) / n for g in goal_types}
        pa, pb = prof(a), prof(b)
        return 0.5 * sum(abs(pa[g] - pb[g]) for g in goal_types)

    seeds = range(seed_offset, seed_offset + n_seeds)

    def condition(dest_a, dest_b):
        ca = [run_phased(s, WA, dest_a) for s in seeds]
        cb = [run_phased(s, WB, dest_b) for s in seeds]
        live = [i for i in range(n_seeds) if ca[i][0] is not None and cb[i][0] is not None]
        # The threshold follows the sample size. ★Note★ this threshold is itself a selection effect:
        # what gets dropped are the configurations where "the parameters were drawn too harshly and the
        # balls cannot survive", not a random subset. So dead_* must be written to disk, and the report
        # must state how many were dropped and why.
        if len(live) < max(30, int(0.2 * n_seeds)):
            return None
        rng = random.Random(config_id)
        treat = [window_tv(ca[i][1], cb[i][1]) for i in live]
        base = (_shuffled_baseline([ca[i][1] for i in live], BASE_PAIRINGS, rng, window_tv) +
                _shuffled_baseline([cb[i][1] for i in live], BASE_PAIRINGS, rng, window_tv))
        gt = [goal_tv(ca[i][0], cb[i][0]) for i in live]
        gb = (_shuffled_baseline([ca[i][0] for i in live], BASE_PAIRINGS, rng, goal_tv) +
              _shuffled_baseline([cb[i][0] for i in live], BASE_PAIRINGS, rng, goal_tv))
        mt, mb = statistics.mean(treat), statistics.mean(base)
        mgt, mgb = statistics.mean(gt), statistics.mean(gb)
        # Log ratio: pair up the log differences to sidestep the upward bias of E[X/Y]
        logr = (statistics.mean(math.log(v) for v in treat if v > 0) -
                statistics.mean(math.log(v) for v in base if v > 0))
        return {"n": len(live), "dead": 1 - len(live) / n_seeds,
                "r": mt / mb if mb else 0.0, "logr": logr,
                "gr": mgt / mgb if mgb else 0.0}

    # ★ Two independent records ★ The "stay" arm has high 60-day mortality in the barren world and often
    #   misses the threshold. An early version discarded the whole row as soon as stay failed, throwing away
    #   perfectly valid move data — and move is the headline, measured in the **baseline world** with far lower mortality.
    move = condition(COMMON, COMMON)
    if move is None:
        return None
    stay = condition(WA, WB)

    row = {"config_id": config_id}
    row.update({k: round(v, 6) if isinstance(v, float) else v for k, v in cfg.items()})
    row.update({
        "n_move": move["n"], "dead_move": round(move["dead"], 4),
        "ratio_move": round(move["r"], 5), "logratio_move": round(move["logr"], 5),
        "goal_ratio_move": round(move["gr"], 5),
        "n_stay": stay["n"] if stay else "",
        "dead_stay": round(stay["dead"], 4) if stay else "",
        "ratio_stay": round(stay["r"], 5) if stay else "",
        "keep": round(move["r"] / stay["r"], 5) if stay and stay["r"] else "",
    })
    return row


def done_ids(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {int(r["config_id"]) for r in csv.DictReader(f) if r.get("config_id")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", type=int, default=500)
    ap.add_argument("--seeds", type=int, default=300)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--seed-offset", type=int, default=0,
                    help="for the holdout set: switch to an untouched seed block, e.g. 10000")
    ap.add_argument("--out", default="sweep_results.csv")
    a = ap.parse_args()

    already = done_ids(a.out)
    todo = [(i, a.seeds, a.seed_offset) for i in range(a.configs) if i not in already]

    print(f"Parameter sweep  {a.configs} configs × {a.seeds} seeds  "
          f"seed range [{a.seed_offset}, {a.seed_offset + a.seeds})")
    print(f"done {len(already)}, to run {len(todo)}, processes {a.workers}")
    if not todo:
        print("All done.")
        return

    new_file = not os.path.exists(a.out)
    t0 = time.time()
    with open(a.out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        with mp.Pool(a.workers) as pool:
            n_ok = 0
            for k, row in enumerate(pool.imap_unordered(evaluate, todo), 1):
                if row is not None:
                    w.writerow(row)
                    f.flush()
                    n_ok += 1
                if k % 10 == 0 or k == len(todo):
                    el = time.time() - t0
                    eta = el / k * (len(todo) - k)
                    print(f"  {k}/{len(todo)}  valid {n_ok}  "
                          f"elapsed {el/60:.1f}min  remaining ~{eta/60:.1f}min", flush=True)

    print(f"\nFinished, written to {a.out}. Use python sweep_report.py to view the results.")


if __name__ == "__main__":
    mp.freeze_support()
    main()
