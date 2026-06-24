"""
Price of anarchy by load (reproducible source for the paper's tab:poa).

Computes TTT(UE)/TTT(SO) on the 132-satellite shell across offered loads, confirming
the ordering TTT(SO) <= TTT(UE) that validates the corrected estimator
(Section "Pitfalls"). Writes results/poa.csv.
"""
import csv
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from constellation import Walker, grid_isl_graph
from traffic import gravity_demands, evaluate

CAP = 20.0
LOADS = [300, 600, 1000]
SEEDS = [0, 1, 2]
OUT = os.path.join(ROOT, "results", "poa.csv")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    w = Walker(132, 12, 1, 53.0, 550.0)
    A, W = grid_isl_graph(w, 0.0, seam=False)
    pos = w.positions(0.0)
    rows = []
    print(f"{'load':>5} {'UE':>10} {'SO':>10} {'PoA=UE/SO':>10}")
    for L in LOADS:
        ues, sos = [], []
        for s in SEEDS:
            dem = gravity_demands(pos, L, np.random.default_rng(s))
            ues.append(evaluate(A, W, dem, CAP, policy="ue")["total_ttt"])
            sos.append(evaluate(A, W, dem, CAP, policy="so")["total_ttt"])
        ue, so = float(np.mean(ues)), float(np.mean(sos))
        poa = ue / so
        rows.append({"load": L, "ue_ttt": ue, "so_ttt": so, "poa": poa})
        print(f"{L:>5} {ue:>10.2f} {so:>10.2f} {poa:>10.3f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    assert all(r["poa"] >= 0.999 for r in rows), "PoA < 1 violates SO <= UE!"
    print("OK: SO <= UE at every load.")


if __name__ == "__main__":
    main()
