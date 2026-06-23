"""
Congestion-pivot kill-gate: is there headroom for congestion-aware routing?

No GNN here. We only ask: across offered-load levels, how much does load-AWARE
routing (best-response equilibrium) beat load-BLIND shortest-path on realized mean
delay and drop rate? If the blind baseline is already close to aware, congestion
does not bite on this topology and the pivot is dead. If aware is much better
(lower delay, fewer drops) in a realistic load regime, a GNN that predicts that
congestion-aware decision has something real to learn.

Reported per shell across a sweep of demand counts (offered load).
"""

import csv
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from constellation import Walker                      # noqa: E402
from traffic import gravity_demands, evaluate         # noqa: E402

SHELLS = [
    ("starlink_mini132", Walker(132, 12, 1, 53.0, 550.0)),
    ("starlink_mini264", Walker(264, 24, 1, 53.0, 550.0)),
]
N_PAIRS = [100, 300, 600, 1000, 1600]    # offered-load sweep (BPR, no drops)
SEEDS = [0, 1, 2]
CAP = 20.0                               # ISL capacity (rate units)
OUT = os.path.join(ROOT, "results", "p4_headroom.csv")


def main():
    from constellation import grid_isl_graph
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    print(f"{'shell':18s} {'pairs':>5} {'seed':>4} | "
          f"{'maxutil':>7} | {'blind_ttt':>10} {'ue_ttt':>10} {'gain%':>6} | "
          f"{'blind_dl':>9} {'ue_dl':>9}")
    for name, w in SHELLS:
        A_np, W_np = grid_isl_graph(w, 0.0, seam=False)
        pos = w.positions(0.0)
        for npairs in N_PAIRS:
            for seed in SEEDS:
                rng = np.random.default_rng(seed)
                dem = gravity_demands(pos, npairs, rng)
                blind = evaluate(A_np, W_np, dem, CAP, policy="blind")
                ue = evaluate(A_np, W_np, dem, CAP, policy="ue")
                gain = (100.0 * (blind["total_ttt"] - ue["total_ttt"])
                        / blind["total_ttt"]) if blind["total_ttt"] > 0 else 0.0
                rows.append({"shell": name, "pairs": npairs, "seed": seed,
                             "blind_maxutil": blind["max_util"],
                             "ue_maxutil": ue["max_util"],
                             "blind_ttt": blind["total_ttt"], "ue_ttt": ue["total_ttt"],
                             "blind_delay": blind["mean_delay"],
                             "ue_delay": ue["mean_delay"], "gain": gain})
                print(f"{name:18s} {npairs:>5} {seed:>4} | "
                      f"{blind['max_util']:>7.2f} | {blind['total_ttt']:>10.1f} "
                      f"{ue['total_ttt']:>10.1f} {gain:>5.1f}% | "
                      f"{blind['mean_delay']:>9.3f} {ue['mean_delay']:>9.3f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    verdict(rows)


def verdict(rows):
    # Headroom is load-induced: light load -> ~0 gain (blind already optimal),
    # heavier load -> large gain (shortest-path concentrates on bottlenecks while
    # alternates idle). We judge on the gain CURVE, not on blind max_util (which is
    # itself inflated by the very concentration we are measuring).
    print("\n" + "=" * 78)
    print(f"{'shell':18s} {'pairs':>5} {'avg_util':>8} | {'TTT gain% (blind->UE)':>22}")
    loads = sorted({r["pairs"] for r in rows})
    light_gain, loaded_peak = [], 0.0
    for name in sorted({r["shell"] for r in rows}):
        for npairs in loads:
            rs = [r for r in rows if r["shell"] == name and r["pairs"] == npairs]
            gain = np.mean([r["gain"] for r in rs])
            mu = np.mean([r["ue_maxutil"] for r in rs])   # UE max util (post-balancing)
            if npairs == loads[0]:
                light_gain.append(gain)
            else:
                loaded_peak = max(loaded_peak, gain)
            print(f"{name:18s} {npairs:>5} {mu:>8.2f} | {gain:>21.1f}%")
    light = float(np.mean(light_gain)) if light_gain else 0.0
    print("\nHEADROOM VERDICT")
    print(f"  light-load gain: {light:.1f}%   loaded-peak gain: {loaded_peak:.1f}%")
    if loaded_peak >= 25.0 and light < 8.0:
        print("  => HEADROOM EXISTS (genuine, load-induced): blind shortest-path wastes")
        print("     tens of % of travel time by overloading bottlenecks under load;")
        print("     congestion-aware routing recovers it. A GNN target with real signal.")
    else:
        print("  => LOW / AMBIGUOUS headroom. Reconsider the pivot / task.")
    print("=" * 78)


if __name__ == "__main__":
    main()
