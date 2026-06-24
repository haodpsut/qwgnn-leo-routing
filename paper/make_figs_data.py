"""
Aggregate the result CSVs into the exact numbers used by the paper's figures and
tables. Run after the experiments; copy the printed values into main.tex so every
number is traceable to a CSV (transaction-grade provenance).

  python paper/make_figs_data.py
"""
import csv
import os
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")


def load(name):
    rows = list(csv.DictReader(open(os.path.join(RES, name))))
    for r in rows:
        for k, v in r.items():
            try:
                r[k] = float(v)
            except (ValueError, TypeError):
                pass
    return rows


def agg(rows, keyfn, valfn):
    d = defaultdict(list)
    for r in rows:
        d[keyfn(r)].append(valfn(r))
    return {k: (float(np.mean(v)), float(np.std(v))) for k, v in d.items()}


print("=" * 64)
print("FIG headroom (P4): TTT gain% of UE over blind, by shell x load")
h = load("p4_headroom.csv")
for shell in sorted({r["shell"] for r in h}):
    pts = agg([r for r in h if r["shell"] == shell],
              lambda r: int(r["pairs"]), lambda r: r["gain"])
    s = "  ".join(f"{p}:{pts[p][0]:.1f}" for p in sorted(pts))
    print(f"  {shell:18s} {s}")

print("=" * 64)
print("TABLE/FIG baselines (P6): TTT relative to blind, by split")
p6 = load("p6_baselines.csv")
for split in ("in-dist", "ood"):
    rs = [r for r in p6 if r["split"] == split]
    g = lambda k: np.mean([r[k] for r in rs])
    print(f"  {split:8s} | SO {g('r_so'):.2f}  UE {g('r_ue'):.2f}  geo {g('r_geo'):.2f}"
          f"  1step {g('r_1step'):.2f}  GNN {g('r_gnn'):.2f}"
          f"  geo_stuck {g('geo_stuck_frac'):.0%}")

print("=" * 64)
print("FIG ablation (P5, 264 OOD): recovered% mean+/-std, by operator x split")
p5 = load("p5_router.csv")
for op in ("GCN", "Heat", "QW"):
    for split in ("in-dist", "ood-largeshell"):
        rs = [r for r in p5 if r["prop"] == op and r["split"] == split]
        if rs:
            v = 100 * np.array([r["recovered"] for r in rs])
            print(f"  {op:5s} {split:14s}: {v.mean():.1f} +/- {v.std():.1f} (n={len(rs)})")

print("=" * 64)
print("FIG proactive (P7): TTT/blind by drift")
p7 = load("p7_proactive.csv")
for drift in sorted({r["drift"] for r in p7}):
    rs = [r for r in p7 if r["drift"] == drift]
    g = lambda k: np.mean([r[k] for r in rs])
    gain = 100 * (g("r_react") - g("r_proact")) / g("r_react")
    print(f"  drift {drift:.2f} | UE {g('r_ue'):.2f}  react {g('r_react'):.2f}"
          f"  proact {g('r_proact'):.2f}  gain {gain:.0f}%")

print("=" * 64)
print("TABLE price of anarchy (poa.csv): UE/SO by load on the 132-shell")
try:
    for r in load("poa.csv"):
        print(f"  load {int(r['load'])}: UE {r['ue_ttt']:.2f}  SO {r['so_ttt']:.2f}"
              f"  PoA {r['poa']:.3f}")
except FileNotFoundError:
    print("  (run experiments/poa_check.py first)")

print("=" * 64)
print("NOTE: 1584 C2 and timing are in results/p5_full_1584.log + p6_full_1584.log")
print("      (server run; not in the small-shell CSVs).")
