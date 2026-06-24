"""
Aggregate the result CSVs into the exact numbers (mean +/- std over seeds and
instances) used by the paper's figures and tables. Run after the experiments; copy the
printed values into main.tex so every number, AND its standard deviation, is traceable
to a CSV (transaction-grade provenance, multi-seed).

  python paper/make_figs_data.py
"""
import csv
import os

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


def ms(vals):
    a = np.array(vals, dtype=float)
    return a.mean(), a.std()


print("=" * 70)
print("FIG/TAB headroom (P4): UE gain% over blind, mean+/-std over seeds")
h = load("p4_headroom.csv")
for shell in sorted({r["shell"] for r in h}):
    out = []
    for p in sorted({int(r["pairs"]) for r in h if r["shell"] == shell}):
        m, s = ms([r["gain"] for r in h if r["shell"] == shell and r["pairs"] == p])
        out.append(f"{p}:{m:.1f}+-{s:.1f}")
    print(f"  {shell:16s} " + "  ".join(out))

print("=" * 70)
print("TABLE/FIG baselines (P6): TTT relative to blind, mean+/-std")
p6 = load("p6_baselines.csv")
for split in ("in-dist", "ood"):
    rs = [r for r in p6 if r["split"] == split]
    parts = []
    for k, lbl in [("r_so", "SO"), ("r_ue", "UE"), ("r_geo", "geo"),
                   ("r_1step", "1step"), ("r_gnn", "GNN")]:
        m, s = ms([r[k] for r in rs])
        parts.append(f"{lbl} {m:.2f}+-{s:.2f}")
    gm, _ = ms([r["geo_stuck_frac"] for r in rs])
    print(f"  {split:8s} | " + "  ".join(parts) + f"  geo_stuck {gm:.0%}")

print("=" * 70)
print("FIG ablation (P5, 264 OOD): recovered% mean+/-std, by operator x split")
p5 = load("p5_router.csv")
for op in ("GCN", "Heat", "QW"):
    for split in ("in-dist", "ood-largeshell"):
        rs = [r for r in p5 if r["prop"] == op and r["split"] == split]
        if rs:
            m, s = ms([100 * r["recovered"] for r in rs])
            print(f"  {op:5s} {split:14s}: {m:.1f} +/- {s:.1f} (n={len(rs)})")

print("=" * 70)
print("FIG proactive (P7): TTT/blind by drift, mean+/-std over seeds")
p7 = load("p7_proactive.csv")
for drift in sorted({r["drift"] for r in p7}):
    rs = [r for r in p7 if r["drift"] == drift]
    rm, rs_ = ms([r["r_react"] for r in rs])
    pm, ps = ms([r["r_proact"] for r in rs])
    um, _ = ms([r["r_ue"] for r in rs])
    print(f"  drift {drift:.2f} | UE {um:.2f}  react {rm:.2f}+-{rs_:.2f}  "
          f"proact {pm:.2f}+-{ps:.2f}")

print("=" * 70)
print("TABLE/FIG decoder (p8_decoder.csv): TTT/blind + recovered%, mean+/-std")
try:
    p8 = load("p8_decoder.csv")
    for split in ("in-dist", "ood"):
        rs = [r for r in p8 if r["split"] == split]
        spm, sps = ms([r["r_gnn_sp"] for r in rs])
        mpm, mps = ms([r["r_gnn_mp"] for r in rs])
        uem, _ = ms([r["r_ue"] for r in rs])
        rsp = ms([100 * (1 - r["r_gnn_sp"]) / (1 - r["r_ue"]) for r in rs])
        rmp = ms([100 * (1 - r["r_gnn_mp"]) / (1 - r["r_ue"]) for r in rs])
        print(f"  {split:8s} single {spm:.2f}+-{sps:.2f} ({rsp[0]:.0f}+-{rsp[1]:.0f}%)  "
              f"multi {mpm:.2f}+-{mps:.2f} ({rmp[0]:.0f}+-{rmp[1]:.0f}%)  UE {uem:.2f}")
except FileNotFoundError:
    print("  (run experiments/p8_decoder.py)")

print("=" * 70)
print("FIG bound (p9_bound.csv): TTT gap to UE vs price error, mean+/-std")
try:
    for r in load("p9_bound.csv"):
        sd_sp = r.get("gap_sp_std", 0.0)
        sd_mp = r.get("gap_mp_std", 0.0)
        print(f"  eps {r['eps']:.2f} rel_err {r['rel_err']:.3f}  "
              f"single {r['gap_sp_pct']:.1f}+-{sd_sp:.1f}%  "
              f"multi {r['gap_mp_pct']:.1f}+-{sd_mp:.1f}%")
except FileNotFoundError:
    print("  (run experiments/p9_bound.py)")

print("=" * 70)
print("TABLE price of anarchy (poa.csv): UE/SO by load, PoA mean+/-std")
try:
    for r in load("poa.csv"):
        sd = r.get("poa_std", 0.0)
        print(f"  load {int(r['load'])}: UE {r['ue_ttt']:.2f}  SO {r['so_ttt']:.2f}"
              f"  PoA {r['poa']:.3f}+-{sd:.3f}")
except FileNotFoundError:
    print("  (run experiments/poa_check.py first)")

print("=" * 70)
print("NOTE: 1584 C2 and timing are in results/p5_full_1584.log + p6_full_1584.log")
print("      (server run; not in the small-shell CSVs).")
