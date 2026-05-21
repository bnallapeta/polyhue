#!/usr/bin/env python3
"""Profile wasm component sizes under different strip/optimize passes.

Run from the project root: `python3 scripts/profile-sizes.py`.
Outputs go to dist/stripped/.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRIPPED = os.path.join(ROOT, "dist", "stripped")
os.makedirs(STRIPPED, exist_ok=True)

COMPONENTS = [
    ("color-rs",    "components/color-rs/target/wasm32-wasip2/release/color_rs.wasm"),
    ("color-py",    "components/color-py/color-py.wasm"),
    ("color-ts",    "components/color-ts/dist/color-ts.wasm"),
    ("policy-gate", "components/policy-gate/target/wasm32-wasip2/release/policy_gate.wasm"),
    ("polyhue",     "dist/polyhue.wasm"),
]


def kb(path):
    return os.path.getsize(path) / 1024


def run(cmd):
    return subprocess.run(cmd, capture_output=True, check=False)


results = []
for name, rel in COMPONENTS:
    src = os.path.join(ROOT, rel)
    if not os.path.exists(src):
        print(f"missing: {src}", file=sys.stderr)
        continue
    orig = kb(src)

    s_path = os.path.join(STRIPPED, f"{name}.strip.wasm")
    sa_path = os.path.join(STRIPPED, f"{name}.strip-all.wasm")

    run(["wasm-tools", "strip", src, "-o", s_path])
    run(["wasm-tools", "strip", "--all", src, "-o", sa_path])

    s = kb(s_path) if os.path.exists(s_path) else None
    sa = kb(sa_path) if os.path.exists(sa_path) else None

    results.append((name, orig, s, sa))

print()
print(f"{'component':<14} {'orig':>10} {'strip':>10} {'%':>6} {'strip-all':>12} {'%':>6}")
print("-" * 64)
for name, orig, s, sa in results:
    def pct(v):
        return f"{(1 - v / orig) * 100:5.1f}" if v else "  --"

    def show(v):
        return f"{v:10.1f}" if v is not None else "        --"

    print(f"{name:<14} {orig:10.1f} {show(s)} {pct(s):>6} {show(sa):>12} {pct(sa):>6}")
print("\n(all sizes in KB)")
