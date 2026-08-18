"""
Three fixes for the condition balance — they cure mortality, but do they flatten the world difference too?
==========================================================================================================

Run:  python cond_compare.py

Rule 47: after a transplant the recovery channel almost never fires, the system spends 90–98%
of its time being drained in the dead zone, and after day 30 no ball has a positive balance.
Three candidate fixes (already parameterised in `sim.py`):

    ① COND_RECOVER_AT       raise the recovery threshold (30 → 45/55/65), cutting away the dead zone
    ② COND_DEADZONE_RECOVER slow recovery inside the dead zone too
    ③ COND_SHELTER_RECOVER  shelter also contributes to condition

★ The lesson of rule 45 ★ Looking at mortality alone picks the wrong one. **The ratio must be
measured at the same time.** A fix that keeps the balls alive but flattens the world difference
has failed — and all three carry that risk: condition improves across the board → the pressure
of the barren world weakens → the two worlds may no longer be that different.
The direction of ③ is not even easy to predict (shelter contributing to condition → the rich

world's material advantage is amplified → it could widen the difference instead).
Criterion: both mortalities <15%, and neither ratio significantly below "status quo".
"""

import sim
from fix_compare import ratio_and_death, N_RATIO, N_DEATH

# (label, recovery threshold, dead-zone recovery, shelter recovery)
VARIANTS = [
    ("status quo",            30.0, 0.00, 0.00),
    ("① threshold 45",        45.0, 0.00, 0.00),
    ("① threshold 55",        55.0, 0.00, 0.00),
    ("① threshold 65",        65.0, 0.00, 0.00),
    ("② dead zone +0.03",     30.0, 0.03, 0.00),
    ("② dead zone +0.06",     30.0, 0.06, 0.00),
    ("③ shelter +0.05",       30.0, 0.00, 0.05),
    ("③ shelter +0.10",       30.0, 0.00, 0.10),
    ("①55 + ③0.05 combined",  55.0, 0.00, 0.05),
]


def main():
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    print("=" * 104)
    print(f" Three condition-balance fixes   022 on   ratio N={N_RATIO}(60d)   mortality N={N_DEATH}(120d)")
    print("=" * 104)
    print(f"  {'fix':<24}{'dead% full':>12}{'dead% no floor':>16}"
          f"{'ratio full':>22}{'ratio no floor':>22}")
    print("  " + "-" * 100)

    for label, rec_at, dz, sh in VARIANTS:
        sim.COND_RECOVER_AT = rec_at
        sim.COND_DEADZONE_RECOVER = dz
        sim.COND_SHELTER_RECOVER = sh
        r_f, ci_f, _ = ratio_and_death(False, 60)
        r_a, ci_a, _ = ratio_and_death(True, 60)
        _, _, d_f = ratio_and_death(False, 120, N_DEATH)
        _, _, d_a = ratio_and_death(True, 120, N_DEATH)
        print(f"  {label:<18}{d_f:>10.1%}{'' if d_f < .15 else '⚠':<1}"
              f"{d_a:>11.1%}{'' if d_a < .15 else '⚠':<1}"
              f"{r_f:>10.3f} [{ci_f[0]:.3f},{ci_f[1]:.3f}]"
              f"{r_a:>10.3f} [{ci_a[0]:.3f},{ci_a[1]:.3f}]")

    print("\n  Criterion: both mortality columns <15% (no ⚠), and neither ratio column significantly below \"status quo\"")
    print("  ⚠ A collapsed ratio is a failure, even if mortality drops to 0")


if __name__ == "__main__":
    main()
