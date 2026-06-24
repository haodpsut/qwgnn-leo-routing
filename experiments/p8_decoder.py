"""
P8 (formulation fix 1): single-path vs multipath decoding of the predicted prices.

The user equilibrium splits flow across equal-cost paths, so a single shortest-path
decode of the predicted (or even the true) equilibrium prices cannot reproduce it.
We add a one-shot multipath decoder (traffic.multipath_route) and show it routes the
GNN's predicted prices materially closer to UE than the single-path decode, in
distribution and zero shot, confirming the gap is a decoding limit, not only a
prediction limit.

Reports TTT relative to blind for: blind, GNN single-path, GNN multipath, UE.
"""
import csv
import os
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "smoke"))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker
from traffic import evaluate, route_and_measure, multipath_route
from p5_gnn_router import make_instance, train, TRAIN_WALKER, TRAIN_PAIRS, N_TRAIN_INST

OP = "GCN"
SEEDS = [0, 1, 2]
N_EVAL = 3
TAU = 0.2
OOD = (Walker(264, 24, 1, 53.0, 550.0), 1200)
OUT = os.path.join(ROOT, "results", "p8_decoder.csv")


def predicted_cost(model, ins):
    with torch.no_grad():
        g = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()
    rc = ins["W_np"].copy()
    rc[ins["rows"], ins["cols"]] = ins["W_np"][ins["rows"], ins["cols"]] * (1 + g)
    return rc


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    print(f"{'seed':>4} {'split':8s} | {'blind':>6} {'GNN-1p':>7} {'GNN-mp':>7} {'UE':>6}")
    for seed in SEEDS:
        tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 100 + seed * 50 + i, need_eig=False)
              for i in range(N_TRAIN_INST)]
        model = train(OP, tr, seed)
        for split, (w, npairs) in [("in-dist", (TRAIN_WALKER, TRAIN_PAIRS)), ("ood", OOD)]:
            for j in range(N_EVAL):
                ins = make_instance(w, npairs, 800 + seed * 10 + j, need_eig=False,
                                    need_target=False)
                A, W, dem, cap = ins["A_np"], ins["W_np"], ins["dem"], ins["cap"]
                blind = route_and_measure(A, W, dem, cap, W)["total_ttt"]
                ue = evaluate(A, W, dem, cap, policy="ue")["total_ttt"]
                rc = predicted_cost(model, ins)
                sp = route_and_measure(A, W, dem, cap, rc)["total_ttt"]
                mp = multipath_route(A, W, rc, dem, cap, tau=TAU)["total_ttt"]
                rows.append({"seed": seed, "split": split, "r_blind": 1.0,
                             "r_gnn_sp": sp / blind, "r_gnn_mp": mp / blind,
                             "r_ue": ue / blind})
            rs = [r for r in rows if r["seed"] == seed and r["split"] == split]
            m = lambda k: np.mean([r[k] for r in rs])
            print(f"{seed:>4} {split:8s} | {1.0:>6.2f} {m('r_gnn_sp'):>7.2f} "
                  f"{m('r_gnn_mp'):>7.2f} {m('r_ue'):>6.2f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    verdict(rows)


def verdict(rows):
    print("\n" + "=" * 60)
    for split in ("in-dist", "ood"):
        rs = [r for r in rows if r["split"] == split]
        g = lambda k: np.mean([r[k] for r in rs])
        print(f"  {split:8s} | GNN single-path {g('r_gnn_sp'):.2f}  "
              f"multipath {g('r_gnn_mp'):.2f}  UE {g('r_ue'):.2f}")
    ood = [r for r in rows if r["split"] == "ood"]
    sp, mp, ue = (np.mean([r[k] for r in ood]) for k in ("r_gnn_sp", "r_gnn_mp", "r_ue"))
    closed = (sp - mp) / (sp - ue) if sp > ue else float("nan")
    print(f"\nP8 VERDICT: multipath closes {closed:.0%} of the single-path-to-UE gap "
          f"(OOD: {sp:.2f} -> {mp:.2f}, UE {ue:.2f})")
    print("=" * 60)


if __name__ == "__main__":
    main()
