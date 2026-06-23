"""
P1 kill-gate: replicate Pillar 1 on REAL LEO topology from the orbital sim.

Sweep shells of increasing diameter; for each, train the three param-matched
models (GCN local / Heat real-global / QW complex-global) at fixed depth to
regress the delay-weighted routing potential, and measure far-node error.

PASS criterion (same logic as the corrected smoke analyze.py): QW beats Heat on
far nodes in every shell/seed cell, and the absolute far-node error gap over Heat
widens as the shell diameter grows. PASS here clears the gate to the full
system-level evaluation (traffic, queues, proactive handover, OOD scaling).
"""

import csv
import os
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "smoke"))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from models import GCN, HeatGNN, QWGNN, build_ctx, count_params   # from smoke/
from constellation import Walker                                   # from sim/
from dataset import build_routing_dataset                          # from sim/

# shells ordered by expected diameter (small -> large)
SHELLS = [
    ("iridium66",        Walker(66,  6, 1, 86.4, 780.0)),
    ("starlink_mini132", Walker(132, 12, 1, 53.0, 550.0)),
    ("starlink_mini264", Walker(264, 24, 1, 53.0, 550.0)),
]
# add the full shell on a capable box:  QWGNN_FULL=1 python experiments/p1_far_resolution.py
if os.environ.get("QWGNN_FULL") == "1":
    SHELLS.append(("starlink_shell1", Walker(1584, 72, 1, 53.0, 550.0)))

SEEDS = [0, 1, 2]
DEPTH = 3
HIDDEN = 32
N_DEST = 30
TRAIN_FRAC = 0.6
EPOCHS = 300
LR = 1e-2
FAR_HOP = DEPTH
OUT = os.path.join(ROOT, "results", "p1_results.csv")


def train_eval(ModelCls, ctx, ds, seed):
    torch.manual_seed(seed)
    model = ModelCls(hidden=HIDDEN, layers=DEPTH, in_dim=1)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    lossf = torch.nn.MSELoss()
    B = ds["X"].shape[0]
    ntr = int(TRAIN_FRAC * B)
    Xtr, Ytr = ds["X"][:ntr], ds["Y"][:ntr]
    Xte, Yte = ds["X"][ntr:], ds["Y"][ntr:]
    Dte = ds["Dhop"][ntr:]
    for _ in range(EPOCHS):
        opt.zero_grad()
        loss = lossf(model(Xtr, ctx), Ytr)
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        err = (model(Xte, ctx) - Yte).abs()        # normalized-potential units
        far = Dte > FAR_HOP
        mae_far = err[far].mean().item() if far.any() else float("nan")
        mae_all = err.mean().item()
    return mae_all, mae_far, count_params(model)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    print(f"{'shell':18s} {'diam':>4} {'seed':>4} | "
          f"{'GCN_far':>8} {'Heat_far':>8} {'QW_far':>8}")
    for name, w in SHELLS:
        for seed in SEEDS:
            ds = build_routing_dataset(w, 0.0, N_DEST, seed=seed, seam=False)
            ctx = build_ctx(ds["A"])
            res = {}
            for M in (GCN, HeatGNN, QWGNN):
                res[M.name] = train_eval(M, ctx, ds, seed)
            rows.append({
                "shell": name, "diameter": ds["diameter"], "n": ds["n"],
                "seed": seed,
                **{f"{k}_all": res[k][0] for k in res},
                **{f"{k}_far": res[k][1] for k in res},
                **{f"{k}_params": res[k][2] for k in res},
            })
            print(f"{name:18s} {ds['diameter']:>4} {seed:>4} | "
                  f"{res['GCN'][1]:>8.4f} {res['Heat'][1]:>8.4f} {res['QW'][1]:>8.4f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    verdict(rows)


def verdict(rows):
    print("\n" + "=" * 72)
    shells = []
    seen = set()
    for r in rows:
        if r["shell"] not in seen:
            seen.add(r["shell"])
            shells.append((r["shell"], r["diameter"]))
    print(f"{'shell':18s} {'diam':>4} | {'Heat_far':>9} {'QW_far':>9} "
          f"{'absGap':>8} {'win/cells':>9}")
    diam_list, gap_list = [], []
    tot_win = tot = 0
    for name, diam in shells:
        rs = [r for r in rows if r["shell"] == name]
        heat = np.mean([r["Heat_far"] for r in rs])
        qw = np.mean([r["QW_far"] for r in rs])
        wins = sum(1 for r in rs if r["QW_far"] < r["Heat_far"])
        tot_win += wins
        tot += len(rs)
        diam_list.append(diam)
        gap_list.append(heat - qw)
        print(f"{name:18s} {diam:>4} | {heat:>9.4f} {qw:>9.4f} "
              f"{heat - qw:>8.4f} {wins:>4}/{len(rs):<4}")
    slope = np.polyfit(diam_list, gap_list, 1)[0] if len(diam_list) >= 2 else float("nan")
    print("\nP1 VERDICT")
    print(f"  QW beats Heat (far) in {tot_win}/{tot} param-matched cells")
    print(f"  absolute far-node gap vs diameter slope: {slope:+.5f} /hop")
    if tot_win == tot and slope > 0:
        print("  => PASS: Pillar 1 holds on real LEO topology. Proceed to P2/P3.")
    elif tot_win >= 0.8 * tot and slope > 0:
        print("  => SOFT PASS: mostly holds; inspect the losing cells before P2.")
    else:
        print("  => FAIL: drop Pillar 1; pivot to proactive/inductive GNN paper.")
    print("=" * 72)


if __name__ == "__main__":
    main()
