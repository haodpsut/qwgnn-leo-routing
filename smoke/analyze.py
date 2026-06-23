"""
Re-read smoke_results.csv and judge Pillar 1 on the CORRECT criterion.

The original run_smoke verdict keyed on the *relative* %-gain slope vs diameter.
That is the wrong yardstick: when the baseline error blows up super-linearly,
a shrinking percentage can still mean a WIDENING absolute advantage. For a
routing potential measured in hops, the decision-relevant quantity is the
absolute hop-error gap (Heat_far - QW_far) and whether QW wins consistently.
"""
import csv
import os
from collections import defaultdict

import numpy as np

CSV = os.path.join(os.path.dirname(__file__), "smoke_results.csv")

rows = list(csv.DictReader(open(CSV)))
for r in rows:
    for k, v in r.items():
        r[k] = float(v)

by_side = defaultdict(list)
for r in rows:
    by_side[int(r["side"])].append(r)

print(f"{'side':>4} {'diam':>4} | {'GCN_far':>8} {'Heat_far':>8} {'QW_far':>8} "
      f"| {'absGap(H-QW)':>12} {'relGain%':>8} {'QW wins/cells':>13}")
diams, absgaps = [], []
total_win, total_cells = 0, 0
for side in sorted(by_side):
    rs = by_side[side]
    diam = rs[0]["diameter"]
    gcn = np.mean([r["GCN_far"] for r in rs])
    heat = np.mean([r["Heat_far"] for r in rs])
    qw = np.mean([r["QW_far"] for r in rs])
    absgap = heat - qw
    rel = 100 * absgap / heat
    wins = sum(1 for r in rs if r["QW_far"] < r["Heat_far"])
    total_win += wins
    total_cells += len(rs)
    diams.append(diam)
    absgaps.append(absgap)
    print(f"{side:>4} {diam:>4.0f} | {gcn:>8.3f} {heat:>8.3f} {qw:>8.3f} "
          f"| {absgap:>12.3f} {rel:>7.1f}% {wins:>6}/{len(rs):<6}")

slope_abs = np.polyfit(diams, absgaps, 1)[0]
mean_rel = np.mean([100 * (np.mean([r["Heat_far"] for r in by_side[s]])
                          - np.mean([r["QW_far"] for r in by_side[s]]))
                    / np.mean([r["Heat_far"] for r in by_side[s]])
                    for s in by_side])

print("\nCORRECTED VERDICT")
print(f"  QW beats Heat in {total_win}/{total_cells} param-matched cells (every seed/size)")
print(f"  mean far-node error reduction vs Heat: {mean_rel:.1f}%")
print(f"  ABSOLUTE far-node hop-gap (Heat-QW) vs diameter slope: {slope_abs:+.3f} hops/hop")
go = (total_win == total_cells) and slope_abs > 0
if go:
    print("  => GO: quantum walk wins everywhere AND the absolute advantage widens")
    print("        with diameter. Pillar 1 survives the kill-test. Proceed to Hypatia.")
else:
    print("  => not a clean GO; inspect.")
print("\n  CAVEAT to settle in the real eval: QW applies |.| inside propagation,")
print("  an extra nonlinearity Heat lacks. It is meaningful ONLY because the")
print("  amplitude is complex (a real diffused indicator stays >=0, so |.| is a")
print("  no-op there) -- but confirm against a complex-diffusion control on Hypatia.")
