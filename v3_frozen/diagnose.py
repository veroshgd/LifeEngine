"""Is the ratchet actually differentiating by user type? — this decides what to change next"""

import statistics

import sim
import scenarios

names = list(scenarios.FEEDING)
agents = [scenarios.run(n, names[n % 3]) for n in range(999)]
alive = [a for a in agents if a.alive]

print("=" * 96)
print(" Ratchet trigger rate (by user type) — we want to see three rows that differ a lot")
print("=" * 96)
head = f"{'':<9}{'hunger':>9}{'storm':>10}{'explore':>10}{'industry':>9}{'cond':>9}"
print(head)
print("-" * 56)
for n in names:
    g = [a for a in alive if a.scenario == n]
    rate = lambda k: sum(1 for a in g if k in a.flags) / len(g)
    ind = statistics.mean([a.traits["industry"] for a in g])
    cond = statistics.mean([a.condition for a in g])
    print(f"{n:<9}{rate('fears_hunger'):>9.1%}{rate('fears_storm'):>10.1%}"
          f"{rate('loves_exploring'):>10.1%}{ind:>9.1f}{cond:>9.1f}")

print()
print(" How to read:")
print("  · large spread in 'hunger-scarred' across the three rows → mechanism correct, only the magnitude is short → amplify the ratchet")
print("  · small spread in 'hunger-scarred' → the mechanism is not working → the user's food has no effect at all")
print("  · 'storm-fearing' should be the same in all three rows (an act of god, unrelated to the user) — it serves as the control arm")
