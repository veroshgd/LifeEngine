"""
Experiment 028 constant freezing — ★ group-blind ★
==================================================

Run:  python calibrate028.py          → writes interface028_frozen.json

★★ Structural group-blindness ★★
Only trait triples are collected, **with no world label of any kind**; `_assert_blind()` enforces that the pool
contains no field usable for grouping. This script **physically cannot compute a rich/poor difference**.

--------------------------------------------------------------------------
What is frozen (five problems solved at once)
---------------------------------------------
① **Negative beta** — instead of "linear rescale + clamp", use **quantile mapping**:
   map the ordering of each readout onto the **frozen beta marginal of arm A (the original 027 interface)**.
   Support / mean / SD / skew / tails / clamp rate are then **all identical to A**, the negative-beta problem
   **does not exist**, and there is no need to explain "actively avoiding the unknown option".

② **Unequal C+ / C− budgets** — this **disappears automatically** after quantile mapping:
   both receive A's entire marginal distribution, and **the only remaining difference is which agents get the
   larger beta** (the ordering), which is exactly what we want to compare.

③ **Collinearity** — measured `corr(x_A, industry) = −0.8781`, so raw industry is essentially A's mirror image.
   Using it directly gives `C− = A − B ≈ 2A`, which after standardisation looks a lot like A again, and
   **what is measured is not breadth but the sum and difference of two collinear variables**.
   So the formal breadth test uses the **orthogonal residual (OLS residual)**:

       slope = Cov(a_ord, x_B) / Var(a_ord)
       x_B⊥  = (x_B − slope · a_ord) / SD(residual)

   ⚠ **Do not use** `(x_B − ρ·x_A)/√(1−ρ²)` — that formula is orthogonal only when **both are already
     standardised**; measured σ(curiosity)=20.87, σ(caution)=29.55, so applying it leaves a **residual
     correlation of +0.8629** (caught by an assertion; see rule 81).

   ⚠ The basis of the orthogonalisation must be **a_ord = curiosity − caution**, i.e.
     **the variable that actually orders arm A's beta**, not `z(cur) − z(cau)`.
     A's beta = clamp((cur−cau+100)/200) is a monotone function of the **raw difference**;
     and since σ_cur ≠ σ_cau, the z difference and the raw difference **do not order identically**
     (Spearman 0.9999, close to but not equal to 1).
     Quantile mapping is entirely **ordering-based**, so it must be aligned to the ordering variable.
   The meaning of B sharpens accordingly: **not "can industry transfer" but "can the part of industry's
   historical information that the exploration axis does not explain transfer".**

④ **Sign arbitrariness** — after orthogonalisation B⊥ has even less of a natural direction, so both signs are run.

⑤ **A stays exactly as in 027** — A is not re-standardised; the other arms adapt to it.
   A is therefore a genuine **sampling-level replication arm** (rule 80).

--------------------------------------------------------------------------
⚠ Every constant is estimated once on the calibration block (20000–21499) and frozen;
   **the final stage only applies them and never re-estimates.**
"""

import hashlib
import json
import multiprocessing as mp
import os
import statistics as st

import novel_task as NT

WA, WB = "rich world", "barren world"
CAL_SEED0, CAL_N = 20000, 1500
CHUNK = 25
RANK_GATE = 0.05     # ★practical redundancy gate★ judged by magnitude, with no significance test
                     #  (at n=2936 even a tiny correlation can be "significant")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "interface028_frozen.json")


def task(job):
    """★ Returns only the trait triple, with no world label whatsoever ★"""
    world, seed0, n = job
    import novel_situation as NS
    sim = NS.sim
    sim.COND_RECOVER_AT = 65.0
    sim.COND_DEADZONE_RECOVER = sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02

    out = []
    for s in range(seed0, seed0 + n):
        life = NS.scenarios.make(s, world)
        ok, _ = NS.run_window(life, 0, 30)
        if not ok:
            continue
        w = sim.World(s, **NS.scenarios.WORLDS["baseline"])
        ok, _ = NS.run_window(life, 30, 30, world=w)
        if not ok:
            continue
        NS.level_state(life.agent)
        t = life.agent.traits
        out.append([t["curiosity"], t["caution"], t["industry"]])
    return out


def _dispatch(j):
    return task(j[1])


def _assert_blind(pool):
    """The pool must be nothing but bare [cur, cau, ind] triples — no groupable field at all"""
    for r in pool[:100]:
        assert isinstance(r, list) and len(r) == 3 and all(
            isinstance(v, float) for v in r), f"✗ group-blindness broken: {r}"


def main():
    workers = max(1, (os.cpu_count() or 2) - 2)
    jobs = [(task, (w, s0, min(CHUNK, CAL_SEED0 + CAL_N - s0)))
            for w in (WA, WB)
            for s0 in range(CAL_SEED0, CAL_SEED0 + CAL_N, CHUNK)]
    pool = []
    with mp.Pool(workers) as p:
        for recs in p.imap_unordered(_dispatch, jobs):
            pool.extend(recs)
    _assert_blind(pool)
    n = len(pool)
    print(f"★ group-blind ★ calibration pool n={n}"
          f" (seeds {CAL_SEED0}–{CAL_SEED0+CAL_N-1}, two worlds mixed, unlabelled)")

    cur = [p[0] for p in pool]
    cau = [p[1] for p in pool]
    ind = [p[2] for p in pool]
    mc, sc = st.mean(cur), st.stdev(cur)
    ma, sa = st.mean(cau), st.stdev(cau)
    mi, si = st.mean(ind), st.stdev(ind)

    z = lambda v, m, s: (v - m) / s
    # ★Orthogonalisation basis = the **variable that actually orders** arm A's beta★ (see the docstring)
    a_ord = [p[0] - p[1] for p in pool]
    m_ao, s_ao = st.mean(a_ord), st.stdev(a_ord)
    xA = [(v - m_ao) / s_ao for v in a_ord]          # the standardised A axis
    xB = [z(p[2], mi, si) for p in pool]
    rho = st.covariance(xA, xB) / (st.stdev(xA) * st.stdev(xB))
    print(f"  corr(A axis, industry_raw) = {rho:+.4f}"
          f"   ← raw industry is highly collinear with the exploration axis")

    # ★Orthogonal residual★ use the OLS residual, not (x_B − ρ·x_A)/√(1−ρ²) —
    # the latter is orthogonal only when x_A and x_B are **both standardised**, and here
    # x_A = z(cur) − z(cau) has SD 1.93 (not 1), so that formula leaves a residual correlation of +0.86.
    # (That mistake was caught by the assert below; the note is kept so it is not repeated.)
    slope = st.covariance(xA, xB) / st.variance(xA)
    xBo_raw = [b - slope * a for a, b in zip(xA, xB)]
    s_res = st.stdev(xBo_raw)
    xBo = [v / s_res for v in xBo_raw]                     # rescale to unit variance
    rho2 = st.covariance(xA, xBo) / (st.stdev(xA) * st.stdev(xBo))
    print(f"  corr(A axis, B⊥)          = {rho2:+.6f}   ← after Pearson orthogonalisation")
    assert abs(rho2) < 1e-9, "✗ Pearson orthogonalisation failed"

    # ★★ rank-space redundancy gate ★★
    # Quantile mapping is entirely ordering-based, so Pearson orthogonality is **not enough** —
    # the rank space that actually decides the coupling assignment must be checked.
    def _rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for k, i in enumerate(o):
            r[i] = k
        return r

    def _spearman(u, v):
        ru, rv = _rank(u), _rank(v)
        return st.covariance(ru, rv) / (st.stdev(ru) * st.stdev(rv))

    rho_s = _spearman(a_ord, xBo)      # a_ord decides the ordering of beta_A
    print(f"  Spearman(beta_A ordering, B⊥ ordering) = {rho_s:+.4f}"
          f"   threshold |ρs| < {RANK_GATE}")
    assert abs(rho_s) < RANK_GATE, (
        f"✗ rank-space redundancy {rho_s:+.4f} exceeds the threshold — after quantile mapping the two"
        f" interfaces still share a great deal of ordering information; switch to rank-space / normal-score residualisation")

    xCp = [a + b for a, b in zip(xA, xBo)]
    xCm = [a - b for a, b in zip(xA, xBo)]

    # Arm A = the original 027 interface, untouched
    ns = [min(1.0, max(0.0, (p[0] - p[1] + 100.0) / 200.0)) for p in pool]
    betaA = sorted(NT.BETA * v for v in ns)
    print(f"  arm A (original 027 interface): μ={st.mean(betaA):.6f}  SD={st.stdev(betaA):.6f}"
          f"  range [{betaA[0]:.6f}, {betaA[-1]:.6f}]")

    frozen = {
        "n_cal": n, "cal_seed0": CAL_SEED0, "cal_n": CAL_N,
        "mu": {"curiosity": mc, "caution": ma, "industry": mi},
        "sd": {"curiosity": sc, "caution": sa, "industry": si},
        "rho_A_Braw": rho, "rho_spearman_A_Bperp": rho_s,
        "resid_slope": slope, "resid_sd": s_res,
        "a_ord_mu": m_ao, "a_ord_sd": s_ao,
        "betaA_sorted": betaA,
        "x_sorted": {"B": sorted(xBo), "Cp": sorted(xCp), "Cm": sorted(xCm)},
        "task_fingerprint": NT.config_fingerprint(),
    }
    payload = json.dumps(frozen, sort_keys=True, separators=(",", ":"))
    frozen["sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(frozen, f, ensure_ascii=False)

    print(f"\n  After quantile mapping the beta marginals of the five arms are **completely identical**")
    print(f"  (support / mean / SD / skew / tails / clamp rate all equal to A's)")
    print(f"  The only difference = which agents receive the larger beta (the ordering)")
    print(f"\nFrozen → {OUT}")
    print(f"  sha256 {frozen['sha256'][:32]}…")
    print(f"  task fingerprint {frozen['task_fingerprint']}")
    print("\n⚠ The final stage only applies these constants and never re-estimates them.")


if __name__ == "__main__":
    mp.freeze_support()
    main()
