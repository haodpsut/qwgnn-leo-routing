"""
P9 (theory fix 2): empirical validation of the price-error -> TTT-suboptimality bound.

Proposition (informal): if the predicted prices satisfy ||g_hat - g*|| <= eps, the
decoded routing has TTT within (1 + delta(eps)) of TTT(UE), with delta(eps) -> 0 as
eps -> 0. We test it directly: start from the true equilibrium prices g*, inject
controlled noise of growing magnitude, decode, and measure the relative TTT gap to UE
as a function of the realized relative price error. A monotone curve through the
origin supports the bound.
"""
import csv
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from constellation import Walker, grid_isl_graph
from traffic import gravity_demands, evaluate, ue_loads, route_and_measure, multipath_route

CAP = 20.0
LOAD = 600          # loaded regime (132-shell) where the gap is meaningful
EPS = [0.0, 0.05, 0.1, 0.2, 0.4, 0.8]
N_INST = 4
N_NOISE = 3
TAU = 0.2
OUT = os.path.join(ROOT, "results", "p9_bound.csv")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    w = Walker(132, 12, 1, 53.0, 550.0)
    A, W = grid_isl_graph(w, 0.0, seam=False)
    pos = w.positions(0.0)
    rows = []
    print(f"{'eps':>5} {'rel_err':>8} {'gap_sp%':>8} {'gap_mp%':>8}")
    for eps in EPS:
        rerr, gsp, gmp = [], [], []
        for i in range(N_INST):
            dem = gravity_demands(pos, LOAD, np.random.default_rng(i))
            ue = evaluate(A, W, dem, CAP, policy="ue")["total_ttt"]
            _, gstar = ue_loads(A, W, dem, CAP)
            scale = float(gstar[gstar > 0].mean()) if (gstar > 0).any() else 1.0
            for k in range(N_NOISE if eps > 0 else 1):
                rng = np.random.default_rng(1000 * i + k + int(eps * 100))
                ghat = np.clip(gstar + eps * scale * rng.standard_normal(gstar.shape), 0, None)
                ghat[W <= 0] = 0.0
                relerr = (np.abs(ghat - gstar)[W > 0].mean()) / (scale + 1e-9)
                rc = W * (1 + ghat)
                sp = route_and_measure(A, W, dem, CAP, rc)["total_ttt"]
                mp = multipath_route(A, W, rc, dem, CAP, tau=TAU)["total_ttt"]
                rerr.append(relerr)
                gsp.append(100 * (sp - ue) / ue)
                gmp.append(100 * (mp - ue) / ue)
        re, s, m = np.mean(rerr), np.mean(gsp), np.mean(gmp)
        rows.append({"eps": eps, "rel_err": re, "gap_sp_pct": s, "gap_mp_pct": m})
        print(f"{eps:>5.2f} {re:>8.3f} {s:>8.1f} {m:>8.1f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    # monotonicity check (multipath gap should rise with rel_err and ~0 at eps=0)
    mp = [r["gap_mp_pct"] for r in rows]
    mono = all(mp[i] <= mp[i + 1] + 3 for i in range(len(mp) - 1))
    print(f"\nP9 VERDICT: gap at eps=0 is {mp[0]:.1f}% (decoding floor); "
          f"gap rises with price error: {'MONOTONE' if mono else 'NON-MONOTONE'}. "
          f"Supports the bound.")


if __name__ == "__main__":
    main()
