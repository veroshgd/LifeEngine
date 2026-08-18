"""
028 statistics layer — joint same-seed bootstrap + validity gates
=================================================================

Self-check:  python stats028.py

★★ The only correct way to do the inference ★★
The five arms come from **the same batch of paired seeds** and are highly correlated. So the CI of `G` **must**
be recomputed in full **inside each bootstrap replicate**:

    for each replicate b:
        idx = resample the seed indices once (★the same idx shared by all five arms★)
        E_A^(b), E_Bp^(b), E_Bm^(b), E_Cp^(b), E_Cm^(b)  ← all using that idx
        G^(b)  = min(|E_Cp^(b)|, |E_Cm^(b)|) − |E_A^(b)|
        R_B^(b)= min(|E_Bp^(b)|, |E_Bm^(b)|)
    the CI is taken directly from the distributions of {G^(b)} and {R_B^(b)}

⛔ **Two equivalent wrong approaches, which this module makes fail explicitly through adversarial tests:**
   ① compute the marginal CIs of A / C+ / C− separately, then subtract the endpoints
   ② take the bootstrap mean of each arm first, then apply abs() / min()
   Both ignore the inter-arm correlation, and since `G` contains `abs` and `min` it is **non-linear** —
   a non-linear function must be applied per replicate, never to an aggregate.

★ validity gates (frozen before the run) ★
    support gate           raw out-of-range ≤ 2.0%  and  boundary mass ≤ 2.0%
    budget-transport gate  |μ_j − μ_A|/SD_A ≤ 10%  and  |SD_j − SD_A|/SD_A ≤ 10%
    ⚠ μ_A / SD_A must be **arm A as actually run on the same confirmatory population**,
      not calibration's A — that way any population shift cancels automatically.

★ Layered handling of a gate failure ★
    either C+ or C− fails → the primary G is **invalid / not cleanly interpretable**;
                            neither a breadth gain nor a no-gain may be claimed
    B+ or B− fails        → R_B secondary invalid; **if both C± pass, G is unaffected**
    A has no mapping transport gate (it is the contemporaneous reference itself),
                            but still undergoes the 027 exact-replication and sampling-level replication checks

★ Reading order ★ **The gates must be printed and judged before the task outcome** —
  even if the code has already computed the outcome, validity is judged first,
  to avoid the interpretive freedom that comes from having seen the result.
"""

import random
import statistics as st
import sys

SUPPORT_GATE = 0.02        # upper bound on the raw out-of-range share / boundary mass
BUDGET_GATE = 0.10         # upper bound on |Δμ| and |ΔSD| relative to SD_A
N_BOOT = 10000
BOOT_SEED = 20260817

CLOSURE_TEXT = (
    "Frozen coupling normalization did not transport adequately to the "
    "confirmatory population; breadth contrast is not cleanly interpretable "
    "under the preregistered equal-budget assumption.")


# ------------------------------------------------------------------ gates
def check_gates(diag, muA, sdA):
    """diag[arm] = {'oos': share, 'boundary': share, 'mu': mean, 'sd': standard deviation}"""
    out = {}
    for arm, d in diag.items():
        sup_ok = d["oos"] <= SUPPORT_GATE and d["boundary"] <= SUPPORT_GATE
        dmu = abs(d["mu"] - muA) / sdA
        dsd = abs(d["sd"] - sdA) / sdA
        bud_ok = dmu <= BUDGET_GATE and dsd <= BUDGET_GATE
        out[arm] = {"support": sup_ok, "budget": bud_ok,
                    "ok": sup_ok and bud_ok, "dmu": dmu, "dsd": dsd}
    primary_valid = all(out[a]["ok"] for a in ("Cp", "Cm") if a in out)
    secondary_valid = all(out[a]["ok"] for a in ("Bp", "Bm") if a in out)
    return out, primary_valid, secondary_valid


# ------------------------------------------------- joint same-seed bootstrap
def joint_bootstrap(d, n_boot=N_BOOT, seed=BOOT_SEED):
    """d[arm] = per-seed paired differences (five arms of equal length, aligned by seed).

    ★Each replicate draws the indices once, shared by all five arms★ — the only correct way to exploit
    the same-seed design. The non-linearity of `G` is applied **inside each replicate**.
    """
    arms = list(d)
    n = len(d[arms[0]])
    assert all(len(d[a]) == n for a in arms), "the arms have different lengths"
    rng = random.Random(seed)
    G, RB, E = [], [], {a: [] for a in arms}
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]          # ★shared★
        e = {a: st.mean(d[a][i] for i in idx) for a in arms}
        for a in arms:
            E[a].append(e[a])
        if {"Cp", "Cm", "A"} <= set(arms):
            G.append(min(abs(e["Cp"]), abs(e["Cm"])) - abs(e["A"]))
        if {"Bp", "Bm"} <= set(arms):
            RB.append(min(abs(e["Bp"]), abs(e["Bm"])))
    return {"G": G, "RB": RB, "E": E}


def ci(vals, lo=0.025, hi=0.975):
    v = sorted(vals)
    n = len(v)
    return v[int(lo * n)], v[int(hi * n)]


def point_G(d):
    """Point estimate: apply the non-linearity in full on the **original sample** too, never on an aggregate"""
    e = {a: st.mean(d[a]) for a in d}
    return min(abs(e["Cp"]), abs(e["Cm"])) - abs(e["A"])


# ------------------------------------------------------------ adversarial regression tests
def _wrong_endpoint_subtraction(d, n_boot=N_BOOT, seed=BOOT_SEED):
    """⛔ Wrong approach ①: bootstrap a marginal CI per arm, then subtract the endpoints"""
    rng = random.Random(seed)
    n = len(d["A"])
    marg = {a: [] for a in d}
    for a in d:                                   # ★each arm draws its own★ ← the mistake is here
        for _ in range(n_boot):
            idx = [rng.randrange(n) for _ in range(n)]
            marg[a].append(st.mean(d[a][i] for i in idx))
    mc = {a: ci([abs(x) for x in marg[a]]) for a in ("Cp", "Cm")}
    ma = ci([abs(x) for x in marg["A"]])
    lo = min(mc["Cp"][0], mc["Cm"][0]) - ma[1]
    hi = min(mc["Cp"][1], mc["Cm"][1]) - ma[0]
    return lo, hi


def _wrong_abs_after_average(boot):
    """⛔ Wrong approach ②: take the bootstrap mean of each arm first, then apply abs()/min()"""
    e = {a: st.mean(v) for a, v in boot["E"].items()}
    return min(abs(e["Cp"]), abs(e["Cm"])) - abs(e["A"])


def _test_joint_vs_endpoint_subtraction():
    """★Adversarial test★ construct data where A and C are highly correlated, making endpoint subtraction fail explicitly"""
    rng = random.Random(4242)
    n = 800
    base = [rng.gauss(0.5, 1.0) for _ in range(n)]        # the common component (large)
    d = {
        "A": [b + rng.gauss(0, 0.05) for b in base],
        "Cp": [b + rng.gauss(0, 0.05) for b in base],
        "Cm": [b + rng.gauss(0, 0.05) for b in base],
        "Bp": [rng.gauss(0, 1.0) for _ in range(n)],
        "Bm": [rng.gauss(0, 1.0) for _ in range(n)],
    }
    boot = joint_bootstrap(d, n_boot=4000, seed=7)
    jlo, jhi = ci(boot["G"])
    wlo, whi = _wrong_endpoint_subtraction(d, n_boot=4000, seed=7)
    jw, ww = jhi - jlo, whi - wlo
    assert jw < 0.5 * ww, (
        f"✗ the adversarial construction failed: joint width {jw:.4f} is not clearly narrower than endpoint subtraction's {ww:.4f}")
    # Endpoint subtraction must include values the joint CI clearly excludes
    outside = [x for x in (wlo, whi) if x < jlo or x > jhi]
    assert outside, "✗ endpoint subtraction produced no value excluded by the joint CI"
    print(f"  ✓ adversarial test: joint CI width {jw:.4f}, endpoint subtraction width {ww:.4f}"
          f" ({ww/jw:.1f}× too wide) — the old method fails explicitly")


def _test_abs_after_average_is_wrong():
    """abs/min must be applied per replicate, never to an aggregate"""
    rng = random.Random(99)
    n = 500
    d = {"A": [rng.gauss(0.0, 1.0) for _ in range(n)],     # true value ≈ 0 → abs is biased
         "Cp": [rng.gauss(0.0, 1.0) for _ in range(n)],
         "Cm": [rng.gauss(0.0, 1.0) for _ in range(n)]}
    boot = joint_bootstrap(d, n_boot=4000, seed=11)
    right = st.mean(boot["G"])
    wrong = _wrong_abs_after_average(boot)
    assert abs(right - wrong) > 1e-6, "the two approaches somehow agree? the construction is invalid"
    print(f"  ✓ non-linearity applied per replicate {right:+.5f}"
          f" ≠ averaging first then abs/min {wrong:+.5f} (difference {abs(right-wrong):.5f})")


def _test_shared_indices():
    """The five arms must share one set of resampling indices — verified with completely identical data"""
    n = 300
    same = [float(i) for i in range(n)]
    d = {"A": list(same), "Cp": list(same), "Cm": list(same)}
    boot = joint_bootstrap(d, n_boot=500, seed=5)
    for a in ("Cp", "Cm"):
        assert boot["E"][a] == boot["E"]["A"], \
            "✗ identical data gave different bootstrap trajectories across arms — the indices are not shared"
    assert all(abs(g) < 1e-12 for g in boot["G"]), "✗ G should be identically 0"
    print("  ✓ the five arms share one set of resampling indices (identical data → identical per replicate)")


def _test_gates():
    sdA, muA = 0.0122, 0.0367
    good = {"Cp": {"oos": 0.001, "boundary": 0.002, "mu": muA + 0.0003,
                   "sd": sdA - 0.0002}}
    _, pv, _ = check_gates(good, muA, sdA)
    assert pv
    bad = {"Cp": dict(good["Cp"], mu=muA + 0.0020)}       # Δμ = 16% SD_A
    g, pv2, _ = check_gates(bad, muA, sdA)
    assert not pv2 and not g["Cp"]["budget"]
    # A B failure must not drag down the primary
    mix = {"Cp": good["Cp"], "Cm": good["Cp"],
           "Bp": dict(good["Cp"], oos=0.05), "Bm": good["Cp"]}
    g3, pv3, sv3 = check_gates(mix, muA, sdA)
    assert pv3 and not sv3, "✗ an arm-B failure should not invalidate the primary G"
    print("  ✓ gates: C± failure → primary invalid; B± failure → secondary invalid only")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("028 statistics-layer self-check")
    _test_shared_indices()
    _test_joint_vs_endpoint_subtraction()
    _test_abs_after_average_is_wrong()
    _test_gates()
    print(f"\nFrozen thresholds: support ≤ {SUPPORT_GATE:.0%}  boundary ≤ {SUPPORT_GATE:.0%}"
          f"  |Δμ|,|ΔSD| ≤ {BUDGET_GATE:.0%} × SD_A")
    print("All passed.")
