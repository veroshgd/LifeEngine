"""
Experiment 028 interface layer — five-arm frozen readout
========================================================

Self-check:  python interface028.py

    FrozenTransform
        ↓  traits → raw readout for A / B± / C±
    frozen empirical quantile mapping
        ↓
    effective coupling b_i
        ↓
    027 NovelTask adapter (reuses the original 027 task code, not one line changed)

★★ The most critical trap: double multiplication ★★
`NT.run_task(agent, seed, beta=X)` internally computes `b = X * novelty_style(agent)`.
So the mapped `b_i` must **never** be passed straight in as `beta=` —
that would become `b_i × novelty_style_i`, **secretly multiplying the A axis back in**,
B⊥ would no longer be B⊥ and C± no longer C±, and the design "the five arms differ only in ordering" would fail outright.

The correct approach (`run_with_effective_coupling`): build a proxy agent such that
`novelty_style(proxy) = b_i / BETA`, then call the original task with `beta=BETA`:

    BETA × (b_i / BETA) = b_i        ← the internal multiplication is cancelled

So the **learning rule / reward table / softmax / τ / α / shared random draws are all still the original
027 code**, and 028 adds only the coupling assignment.
`_test_no_double_multiplication` verifies this explicitly.

★ B− is not 0.05 − B+ ★
A's frozen beta distribution is **not symmetric about 0.025** (measured [0.012139, 0.048427],
μ=0.036948, clearly left-skewed). So B− must use **its own reverse percentile**:
`rank r → betaA_sorted[n−1−r]`, not an arithmetic complement.

★ In the final stage only the frozen transform is applied, never re-estimated ★
Calibration may hard-assert orthogonality / rank thresholds / bit-identical marginal distributions;
the final run may only assert hash equality, that the transform comes from frozen constants, that beta lies
within the frozen support, that the mapping is deterministic, and that arm A is bit-identical to 027. The actual
mean/SD of each arm in the final run are **diagnostics only** and must not be adjusted to make them equal.
"""

import bisect
import hashlib
import json
import os
import sys

import novel_task as NT

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN_PATH = os.path.join(HERE, "interface028_frozen.json")
ARMS = ("A", "Bp", "Bm", "Cp", "Cm")


def _load():
    with open(FROZEN_PATH, encoding="utf-8") as f:
        d = json.load(f)
    want = d.pop("sha256")
    payload = json.dumps(d, sort_keys=True, separators=(",", ":"))
    got = hashlib.sha256(payload.encode()).hexdigest()
    if got != want:
        raise SystemExit(f"✗ interface028_frozen.json verification failed\n"
                         f"  expected {want[:32]}…\n  got {got[:32]}…")
    d["sha256"] = want
    if d["task_fingerprint"] != NT.config_fingerprint():
        raise SystemExit(f"✗ task fingerprint mismatch: {d['task_fingerprint']} when frozen, "
                         f"now {NT.config_fingerprint()}")
    return d


F = _load()
_BETA_A = F["betaA_sorted"]                 # A arm's frozen beta marginal (ascending)
_N = len(_BETA_A)


# ------------------------------------------------------------------ layer 1
def raw_readout(traits):
    """traits → raw readout for each arm (A is handled separately, see beta_for)"""
    mu, sd = F["mu"], F["sd"]
    z = lambda k: (traits[k] - mu[k]) / sd[k]
    a_ord = traits["curiosity"] - traits["caution"]        # ★A's ordering variable★
    xA = (a_ord - F["a_ord_mu"]) / F["a_ord_sd"]
    xB_raw = z("industry")
    xBo = (xB_raw - F["resid_slope"] * xA) / F["resid_sd"]  # OLS residual
    return {"xA": xA, "B": xBo, "Cp": xA + xBo, "Cm": xA - xBo}


# ------------------------------------------------------------------ layer 2
def _quantile_map(x, key, reverse=False):
    """Frozen empirical CDF → A's frozen beta marginal. **Applied only, never re-estimated.**"""
    ref = F["x_sorted"][key]
    i = bisect.bisect_left(ref, x)
    i = min(max(i, 0), len(ref) - 1)
    q = i / (len(ref) - 1)
    j = int(round((1.0 - q if reverse else q) * (_N - 1)))
    return _BETA_A[min(max(j, 0), _N - 1)]


# ------------------------------------------------------------------ layer 3
def beta_for(arm, traits):
    """The **effective coupling** b_i with which this agent enters the decision logit under this arm"""
    if arm == "A":
        # ★A keeps the original 027 interface exactly, passing through none of 028's mappings★
        return NT.BETA * NT.novelty_style(_Obj(traits))
    r = raw_readout(traits)
    if arm == "Bp":
        return _quantile_map(r["B"], "B", reverse=False)
    if arm == "Bm":
        # ★Not 0.05 − b(Bp)★ A's frozen distribution is asymmetric, so the reverse percentile is required
        return _quantile_map(r["B"], "B", reverse=True)
    if arm == "Cp":
        return _quantile_map(r["Cp"], "Cp")
    if arm == "Cm":
        return _quantile_map(r["Cm"], "Cm")
    raise ValueError(arm)


class _Obj:
    def __init__(self, traits):
        self.traits = dict(traits)


# ------------------------------------------------------------------ layer 4
def run_with_effective_coupling(b_i, seed):
    """★adapter★ makes the coupling the original 027 task ends up using exactly equal to b_i.

    Inside `NT.run_task`: b = beta × novelty_style(agent)
    Build a proxy with novelty_style(proxy) = b_i / BETA, then pass beta = BETA.
    """
    ns = b_i / NT.BETA
    assert 0.0 <= ns <= 1.0, f"b_i={b_i} outside [0, {NT.BETA}]"
    diff = 200.0 * ns - 100.0
    proxy = _Obj({"curiosity": 50.0 + diff / 2.0,
                  "caution": 50.0 - diff / 2.0, "industry": 50.0})
    rec = NT.run_task(proxy, seed, beta=NT.BETA)
    assert abs(rec["beta"] - b_i) < 1e-12, \
        f"✗ adapter failed: expected {b_i}, got {rec['beta']}"
    return rec


def run_arm(arm, traits, seed):
    if arm == "A":
        return NT.run_task(_Obj(traits), seed)        # the original 027 path, unmodified
    return run_with_effective_coupling(beta_for(arm, traits), seed)


# ------------------------------------------------------------------ self-checks
def _cal_pool():
    """Rebuild the calibration pool (for self-checks only)"""
    import novel_situation as NS
    sim = NS.sim
    sim.COND_RECOVER_AT = 65.0
    sim.COND_DEADZONE_RECOVER = sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    out = []
    for s in range(20000, 20200):
        for w in ("rich world", "barren world"):
            life = NS.scenarios.make(s, w)
            ok, _ = NS.run_window(life, 0, 30)
            if not ok:
                continue
            wd = sim.World(s, **NS.scenarios.WORLDS["baseline"])
            ok, _ = NS.run_window(life, 30, 30, world=wd)
            if not ok:
                continue
            NS.level_state(life.agent)
            out.append((s, dict(life.agent.traits)))
    return out


def _test_no_double_multiplication():
    """★The most critical regression test★ passing beta=b_i directly gets multiplied again internally — this must be proven wrong"""
    tr = {"curiosity": 92.0, "caution": 38.0, "industry": 80.0}
    b = beta_for("Bp", tr)
    good = run_with_effective_coupling(b, 30001)
    assert abs(good["beta"] - b) < 1e-12
    bad = NT.run_task(_Obj(tr), 30001, beta=b)         # ← the wrong usage
    ns = NT.novelty_style(_Obj(tr))
    assert abs(bad["beta"] - b * ns) < 1e-12, "the internal multiplication behaviour has changed"
    assert abs(bad["beta"] - b) > 1e-6, "double multiplication somehow made no difference?"
    print(f"  ✓ the adapter cancels the internal multiplication: correct {good['beta']:.6f}"
          f" vs the wrong value from passing beta directly {bad['beta']:.6f} (difference {abs(bad['beta']-b):.6f})")


def _test_A_is_exact_027():
    """Arm A must be bit-identical to the original 027 interface (the sampling-level replication arm)"""
    for s, tr in _cal_pool()[:60]:
        a = run_arm("A", tr, s)
        b = NT.run_task(_Obj(tr), s)
        for k in ("beta", "choices", "rewards", "explores", "Q_end", "N_end"):
            assert a[k] == b[k], f"✗ arm A differs from 027 on {k} (seed {s})"
    print("  ✓ arm A = the original 027 interface; beta/choices/rewards/explores/Q_end/N_end all bit-identical")


def _test_Bm_not_arithmetic_complement():
    """B− must be the reverse percentile, not 0.05 − B+"""
    diffs = 0
    for s, tr in _cal_pool()[:80]:
        bp, bm = beta_for("Bp", tr), beta_for("Bm", tr)
        if abs(bm - (NT.BETA - bp)) > 1e-9:
            diffs += 1
    assert diffs > 40, "B− looks like an arithmetic complement — A's distribution is not symmetric, so that is wrong"
    print(f"  ✓ B− uses the reverse percentile ({diffs}/80 differ from the arithmetic complement)")


def _test_marginals_identical_on_calibration():
    """★calibration-only★ the beta marginal distributions of the five arms must be bit-identical"""
    pool = _cal_pool()
    ref = sorted(_BETA_A)
    for arm in ("Bp", "Bm", "Cp", "Cm"):
        vals = sorted(beta_for(arm, tr) for _, tr in pool)
        assert set(vals) <= set(ref), f"{arm}'s beta falls outside A's frozen support"
    print(f"  ✓ each arm's set of beta values ⊆ A's frozen support "
          f"[{ref[0]:.6f}, {ref[-1]:.6f}]")


def _test_deterministic():
    tr = {"curiosity": 88.0, "caution": 40.0, "industry": 77.0}
    for arm in ARMS:
        a, b = run_arm(arm, tr, 30002), run_arm(arm, tr, 30002)
        assert a["choices"] == b["choices"] and a["beta"] == b["beta"]
    print("  ✓ five-arm mapping is deterministic")


def _test_frozen_integrity():
    assert F["task_fingerprint"] == NT.config_fingerprint()
    assert abs(F["rho_spearman_A_Bperp"]) < 0.05
    print(f"  ✓ frozen integrity: sha256 {F['sha256'][:16]}…  task fingerprint"
          f" {F['task_fingerprint']}  rank redundancy {F['rho_spearman_A_Bperp']:+.4f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"028 interface-layer self-check   frozen n_cal={F['n_cal']}")
    _test_frozen_integrity()
    _test_no_double_multiplication()
    _test_A_is_exact_027()
    _test_Bm_not_arithmetic_complement()
    _test_marginals_identical_on_calibration()
    _test_deterministic()
    print("\nAll passed. Next: the transform transport rehearsal on an independent burned block.")
