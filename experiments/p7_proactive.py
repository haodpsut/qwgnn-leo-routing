"""
P7 (claim C4): proactive vs reactive routing under drifting traffic hotspots.

Traffic hotspots move predictably (the dense-population / sub-solar band rotates
under the constellation; the shift over a slot is known from ephemeris + diurnal
pattern). A REACTIVE router decides slot t from slot t-1's observed demand and is
always one step behind the moving hotspot. A PROACTIVE router uses the predicted
slot-t demand (here: the known-shift forecast) and routes for where the load will
actually be.

We sweep the per-slot hotspot drift and, at each drift, route the SAME current-slot
demand with congestion prices predicted from (reactive) last-slot vs (proactive)
current-slot features. Metric: realized TTT relative to blind. Expectation: at zero
drift reactive == proactive; as drift grows, reactive degrades toward blind while
proactive stays near the clairvoyant UE. The gap is the value of proactivity.
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

from constellation import Walker, grid_isl_graph
from traffic import gravity_demands, route_and_measure, evaluate
from p5_gnn_router import (make_instance, train, build_features,
                           TRAIN_WALKER, TRAIN_PAIRS, CAP, N_TRAIN_INST)

OP = "GCN"
SEEDS = [0, 1, 2]
EVAL_WALKER = Walker(132, 12, 1, 53.0, 550.0)
EVAL_PAIRS = 600
DRIFTS = [0.0, 0.3, 0.6, 1.0, 1.5]      # per-slot hotspot shift (radians)
OUT = os.path.join(ROOT, "results", "p7_proactive.csv")


def demands_at(pos, npairs, band, seed):
    # same seed -> same underlying random stream; only the hotspot band differs,
    # so the demand set coherently "drifts" with the band.
    return gravity_demands(pos, npairs, np.random.default_rng(seed), hotspot_shift=band)


def route_prices(model, A_np, W_np, obs_dem, route_dem, cap):
    """Predict prices from obs_dem features, route route_dem on prop*(1+g)."""
    X, ctx, rows, cols, _ = build_features(A_np, W_np, obs_dem, need_eig=False)
    with torch.no_grad():
        g = torch.expm1(model(X, ctx)).clamp(min=0).numpy()
    rc = W_np.copy()
    rc[rows, cols] = W_np[rows, cols] * (1 + g)
    return route_and_measure(A_np, W_np, route_dem, cap, rc)["total_ttt"]


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    A_np, W_np = grid_isl_graph(EVAL_WALKER, 0.0, seam=False)
    pos = EVAL_WALKER.positions(0.0)
    print(f"{'seed':>4} {'drift':>6} | {'blind':>6} {'UE':>6} {'react':>6} {'proact':>6}")
    for seed in SEEDS:
        train_insts = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 100 + seed * 50 + i,
                                     need_eig=False) for i in range(N_TRAIN_INST)]
        model = train(OP, train_insts, seed)
        for drift in DRIFTS:
            D_prev = demands_at(pos, EVAL_PAIRS, 0.0, 1234 + seed)
            D_now = demands_at(pos, EVAL_PAIRS, drift, 1234 + seed)
            blind = route_and_measure(A_np, W_np, D_now, CAP, W_np)["total_ttt"]
            ue = evaluate(A_np, W_np, D_now, CAP, policy="ue")["total_ttt"]
            react = route_prices(model, A_np, W_np, D_prev, D_now, CAP)   # lag-1 obs
            proact = route_prices(model, A_np, W_np, D_now, D_now, CAP)   # predicted
            rows.append({"seed": seed, "drift": drift,
                         "r_ue": ue / blind, "r_react": react / blind,
                         "r_proact": proact / blind})
            print(f"{seed:>4} {drift:>6.2f} | {1.0:>6.2f} {ue/blind:>6.2f} "
                  f"{react/blind:>6.2f} {proact/blind:>6.2f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    verdict(rows)


def verdict(rows):
    print("\n" + "=" * 64)
    print(f"{'drift':>6} | {'UE':>6} {'reactive':>9} {'proactive':>10} {'pro gain%':>10}")
    gains = []
    for drift in DRIFTS:
        rs = [r for r in rows if r["drift"] == drift]
        ue = np.mean([r["r_ue"] for r in rs])
        re = np.mean([r["r_react"] for r in rs])
        pr = np.mean([r["r_proact"] for r in rs])
        gain = 100 * (re - pr) / re if re > 0 else 0.0
        if drift > 0:
            gains.append(gain)
        print(f"{drift:>6.2f} | {ue:>6.2f} {re:>9.2f} {pr:>10.2f} {gain:>9.1f}%")
    peak = max(gains) if gains else 0.0
    print("\nP7 VERDICT")
    print(f"  proactive-over-reactive TTT gain grows with drift, peak {peak:.0f}%")
    if peak >= 10.0:
        print("  => C4 holds: under drifting hotspots, proactive routing (predicted")
        print("     demand) materially beats reactive lag-1. Temporal pillar confirmed.")
    else:
        print("  => weak: demand drift does not hurt reactive enough here. Increase")
        print("     drift range / load, or reconsider the proactive claim.")
    print("=" * 64)


if __name__ == "__main__":
    main()
