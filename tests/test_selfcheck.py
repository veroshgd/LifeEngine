"""
Core self-check — one `pytest` command proving the environment is sound
=======================================================================

After a fresh clone:

    pip install -r requirements.txt     # only the standard library + pytest is needed
    pytest

It should be all green in under 2 minutes. **This does not re-run the paper's experiments**; it only verifies:

  ① frozen integrity   the SHA256 of v2_frozen / v3_frozen matches the manifest
  ② frozen import      the model really comes from v3_frozen, with the right version and key constants
  ③ mechanism layer    the 8 self-checks of novel_situation (rules 60/61/63 etc.)
  ④ regression         the window-convention fix of rule 72
  ⑤ determinism        the same input run twice is bit-identical (the minimal version of rule 55)

For a full reproduction see `REPRODUCE.md`.
"""

import hashlib
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ---------------------------------------------------------------- ① frozen integrity
@pytest.mark.parametrize("frozen", ["v2_frozen", "v3_frozen"])
def test_frozen_checksums(frozen):
    d = os.path.join(ROOT, frozen)
    sums = os.path.join(d, "SHA256SUMS.txt")
    assert os.path.exists(sums), f"{frozen}/SHA256SUMS.txt is missing"
    bad, n = [], 0
    for line in open(sums, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        want, name = line.split(maxsplit=1)
        p = os.path.join(d, name)
        assert os.path.exists(p), f"{frozen}/{name} is missing"
        got = hashlib.sha256(open(p, "rb").read()).hexdigest()
        n += 1
        # the v2 manifest stores the first 16 characters, v3 stores the full 64
        if not got.startswith(want):
            bad.append(name)
    assert not bad, f"{frozen} checksum failure: {bad}"
    assert n >= 25, f"{frozen} only verified {n} files, the manifest may be incomplete"


# ---------------------------------------------------------------- ② frozen import
def test_v3_frozen_import():
    import novel_situation as NS
    assert os.path.abspath(NS.sim.__file__).startswith(
        os.path.join(ROOT, "v3_frozen")), "the model does not come from v3_frozen"
    assert NS.sim.MODEL_VERSION == "v3"
    assert NS.sim.COND_RECOVER_AT == 65.0, "a key constant of v3 has been changed"


def test_v2_v3_differ_only_by_one_constant():
    """The only executable difference from v2 → v3 must still be COND_RECOVER_AT (+ the new MODEL_VERSION)

    ⚠ "strip # comments and compare line by line" will not do — the v3 module docstring contains a long
      explanation of why 65, which would be misread as a code difference. **The AST must be compared,
      with docstrings stripped**, for a genuine "executable difference".
    """
    import ast

    def top_nodes(path):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                body = node.body
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    node.body = body[1:]          # strip the docstring
        return [ast.dump(n) for n in tree.body]

    a = top_nodes(os.path.join(ROOT, "v2_frozen", "sim.py"))
    b = top_nodes(os.path.join(ROOT, "v3_frozen", "sim.py"))

    only_a = [x for x in a if x not in b]
    only_b = [x for x in b if x not in a]
    for x in only_a:
        assert "COND_RECOVER_AT" in x, f"executable statement unique to v2: {x[:200]}"
    for x in only_b:
        assert ("COND_RECOVER_AT" in x or "MODEL_VERSION" in x), \
            f"executable statement unique to v3: {x[:200]}"
    assert len(only_a) == 1 and len(only_b) == 2, \
        f"wrong number of differences: {len(only_a)} unique to v2, {len(only_b)} unique to v3"


# ---------------------------------------------------------------- ③ mechanism layer
def test_mechanism_layer():
    import novel_situation as NS
    NS._test_gate_non_destructive()      # rule 60
    NS._test_sibling_isolation()         # rule 61
    NS._test_identical_branches()        # negative control
    NS._test_floor_off_fork()            # the deepcopy trap of 024
    NS._test_field_audit()               # rule 63
    NS._test_probe_c()                   # rules 60/61/65


# ---------------------------------------------------------------- ④ regression
def test_rule72_window_regression():
    r = subprocess.run([sys.executable, "novel_calibrate3.py", "--test"],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "rule 72 regression test passed" in r.stdout


# ---------------------------------------------------------------- ⑤ determinism
def test_determinism():
    """The same seed run twice must give a bit-identical complete executable state (the minimal version of rule 55)"""
    import novel_situation as NS

    def run():
        life = NS.scenarios.make(20000, "barren world")
        NS.run_window(life, 0, 6)
        return NS.full_hash(life)
    assert run() == run(), "the same input gave different results across two runs — there is uncontrolled randomness"


def test_final_confirm_gate():
    """The frozen-verification gate of final_confirm must pass on its own"""
    r = subprocess.run([sys.executable, "final_confirm.py", "--check"],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MODEL_VERSION=v3" in r.stdout
