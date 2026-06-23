"""
Kill-test for Pillar 1 (quantum-walk propagation) of the QW-GNN LEO routing paper.

Question under test
-------------------
Does a quantum-walk (ballistic, interfering) global operator resolve the routing
potential (hop distance to destination) at LARGE distance better than a classical
diffusion (real, decaying) global operator, with the advantage GROWING as the
constellation (graph diameter) grows -- at matched parameters and depth?

If QW does NOT beat Heat on far nodes, the "quantum" buys nothing over plain
globalness: kill Pillar 1, fall back to a pure proactive/inductive GNN paper.

Protocol
--------
- Torus-grid LEO constellations of increasing side -> increasing diameter.
- Shared fixed depth K for all models (so GCN's local reach is deliberately
  shorter than the diameter at large sizes -- that is the point).
- Train each model to regress the normalized hop-distance field for a set of
  training destinations; evaluate on held-out destinations.
- Report hop-MAE overall and on FAR nodes (true hop distance > K), averaged over
  multiple seeds. No single-seed cherry-picking.
"""

import csv
import os

import numpy as np
import torch

from data import make_samples
from models import GCN, HeatGNN, QWGNN, build_ctx, count_params

SIDES = [6, 10, 14, 18]      # diameter ~ side (torus)
SEEDS = [0, 1, 2]
DEPTH = 3                    # fixed for ALL models
HIDDEN = 32
N_DEST = 20                  # destinations per graph
N_TRAIN = 12                 # rest held out for eval
EPOCHS = 250
LR = 1e-2
OUT_CSV = os.path.join(os.path.dirname(__file__), "smoke_results.csv")


def train_eval(ModelCls, ctx, data, far_thr, seed):
    torch.manual_seed(seed)
    n = data["n"]
    model = ModelCls(hidden=HIDDEN, layers=DEPTH, in_dim=1)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    lossf = torch.nn.MSELoss()

    X, Y = data["X"], data["Y"]                 # (B,n,1), (B,n)
    Xtr, Ytr = X[:N_TRAIN], Y[:N_TRAIN]
    Xte, Yte = X[N_TRAIN:], Y[N_TRAIN:]
    Dte = data["Dhop"][N_TRAIN:]                # (Bte, n)
    diam = data["diameter"]

    for _ in range(EPOCHS):
        opt.zero_grad()
        pred = model(Xtr, ctx)
        loss = lossf(pred, Ytr)
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        pred = model(Xte, ctx) * diam          # back to hops
        true = Yte * diam
        err = (pred - true).abs()
        mae_all = err.mean().item()
        far = Dte > far_thr
        mae_far = err[far].mean().item() if far.any() else float("nan")
    return mae_all, mae_far, count_params(model)


def main():
    rows = []
    models = [GCN, HeatGNN, QWGNN]
    print(f"{'side':>4} {'diam':>4} {'seed':>4} | "
          f"{'GCN_far':>8} {'Heat_far':>8} {'QW_far':>8} | "
          f"{'GCN_all':>8} {'Heat_all':>8} {'QW_all':>8}")
    for side in SIDES:
        for seed in SEEDS:
            rng = np.random.default_rng(1000 * side + seed)
            data = make_samples(side, N_DEST, rng)
            ctx = build_ctx(data["A"])
            far_thr = DEPTH
            res = {}
            for M in models:
                mae_all, mae_far, nparam = train_eval(M, ctx, data, far_thr, seed)
                res[M.name] = (mae_all, mae_far, nparam)
            rows.append({
                "side": side, "diameter": data["diameter"], "seed": seed,
                **{f"{k}_all": res[k][0] for k in res},
                **{f"{k}_far": res[k][1] for k in res},
                **{f"{k}_params": res[k][2] for k in res},
            })
            print(f"{side:>4} {data['diameter']:>4} {seed:>4} | "
                  f"{res['GCN'][1]:>8.3f} {res['Heat'][1]:>8.3f} {res['QW'][1]:>8.3f} | "
                  f"{res['GCN'][0]:>8.3f} {res['Heat'][0]:>8.3f} {res['QW'][0]:>8.3f}")

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    verdict(rows)


def verdict(rows):
    print("\n" + "=" * 70)
    print("PARAM COUNTS (should be ~equal):",
          {k: rows[0][f"{k}_params"] for k in ["GCN", "Heat", "QW"]})

    sides = sorted({r["side"] for r in rows})
    print(f"\n{'side':>4} {'diam':>4} | {'Heat_far':>9} {'QW_far':>9} "
          f"{'QW<Heat gain%':>13}")
    gains = []
    for side in sides:
        rs = [r for r in rows if r["side"] == side]
        heat = np.mean([r["Heat_far"] for r in rs])
        qw = np.mean([r["QW_far"] for r in rs])
        gain = 100.0 * (heat - qw) / heat if heat > 0 else float("nan")
        gains.append((rs[0]["diameter"], gain))
        print(f"{side:>4} {rs[0]['diameter']:>4} | {heat:>9.3f} {qw:>9.3f} "
              f"{gain:>12.1f}%")

    # Does the QW-over-Heat advantage grow with diameter?
    diam = np.array([g[0] for g in gains], dtype=float)
    gv = np.array([g[1] for g in gains], dtype=float)
    if len(diam) >= 2 and np.std(diam) > 0:
        slope = np.polyfit(diam, gv, 1)[0]
    else:
        slope = float("nan")
    largest_gain = gv[-1]

    print("\nVERDICT")
    print(f"  QW-vs-Heat far-node gain at largest diameter: {largest_gain:.1f}%")
    print(f"  trend of gain vs diameter (slope, %/hop):     {slope:.2f}")
    go = largest_gain > 10.0 and slope > 0
    soft = largest_gain > 0 and slope > 0
    if go:
        print("  => GO: quantum walk gives a clear, scaling advantage. Keep Pillar 1.")
    elif soft:
        print("  => WEAK GO: positive but small/inconsistent. Tune (t-range, depth) "
              "before committing Pillar 1.")
    else:
        print("  => NO-GO: quantum offers no edge over plain global diffusion. "
              "Drop Pillar 1; pivot to pure proactive/inductive GNN.")
    print("=" * 70)


if __name__ == "__main__":
    main()
