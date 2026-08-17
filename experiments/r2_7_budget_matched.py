"""R2.7 / R3.5: the empty cell in the paper's own cost table.

REVIEWER 2, COMMENT 7:
    "One-step correction and geographic greedy are weak comparators. It would be better to consider
     stronger ITERATIVE-BUT-BUDGETED baselines, warm-started MSA, damped or adaptive load
     balancing, ECMP-style multipath ... It would also help to compare inference quality AT MATCHED
     COMPUTATIONAL BUDGETS."

Table VI of the manuscript prices every policy in all-or-nothing passes:

    blind, geographic       1
    one-step correction     2
    GNN (ours)              2 + 1 forward
    UE, SO (MSA)            T ~ 20

Read as a ladder, there is a hole between 2 and 20 and nothing stands in it. Every CHEAP baseline
in the paper is weak, and every STRONG baseline is expensive. The proposed method claims the cell
"cheap AND strong", and no comparator occupies that cell. That is not a missing citation, it is a
missing experiment, and it is exactly what "iterative-but-budgeted" names.

The baseline that fills the hole needs no new algorithm: `ue_loads(..., iters=T)` already takes the
iteration count. MSA truncated at T = 2 costs the same two passes the GNN costs. If truncated MSA
recovers most of the blind-to-UE gap at that budget, the learned price field is buying much less
than the paper claims, and no amount of presentation work fixes that.

This is the same shape as the qi-beam-power case of 15/08: a metaheuristic beat CMA-ES and DE, then
lost 12/12 to random-restart L-BFGS-B once the budgets were matched. Beating the comparators one
chose is not evidence; the trivial-but-strong one has to be on the table.

METRIC. The paper's own: recovered = (blind_ttt - policy_ttt) / (blind_ttt - ue_ttt), the fraction
of the blind-to-UE gap a policy closes. 1.0 means it matched full UE. The GNN's published value
sits in results/p6_baselines.csv; this script prints truncated MSA on the same instances so the two
are directly comparable.
"""
import csv
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from constellation import Walker, grid_isl_graph          # noqa: E402
from traffic import (gravity_demands, edge_loads, link_cost,   # noqa: E402
                     _route_on_cost, evaluate)

SHELLS = [("w132", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264", Walker(264, 24, 1, 53.0, 550.0), 1200)]
SEEDS = [0, 1, 2]
CAP = 20.0
BUDGETS = [1, 2, 3, 5, 10, 20]          # MSA iterations = AoN passes spent
OUT = os.path.join(ROOT, "results", "r2_7_budget_matched.csv")


def msa_truncated(A, prop_W, demands, cap, iters):
    """MSA stopped after `iters` passes, then routed on the cost it has reached.

    iters=0 is the blind pass. The realized TTT is measured exactly as the paper measures it.
    """
    n = A.shape[0]
    free = link_cost(prop_W, np.zeros_like(prop_W), cap)
    paths = _route_on_cost(A, free, demands)
    load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    for k in range(1, iters + 1):
        cost = link_cost(prop_W, load, cap)
        aon = _route_on_cost(A, cost, demands)
        aload = edge_loads([(p, r) for p, r in aon if p is not None], n)
        load = load + (aload - load) / (k + 1)
    cost = link_cost(prop_W, load, cap)
    final = _route_on_cost(A, cost, demands)
    fload = edge_loads([(p, r) for p, r in final if p is not None], n)
    real = link_cost(prop_W, fload, cap)
    tot = 0.0
    for nodes, rate in final:
        if nodes is None:
            continue
        tot += rate * sum(real[a, b] for a, b in zip(nodes[:-1], nodes[1:]))
    return tot


def main():
    rows = []
    print("R2.7 -- MSA CAT NGAN o ngan sach khop, lap day o trong 2..20 cua Bang VI\n")
    print("recovered = (blind - policy) / (blind - ue); 1.00 = bang UE day du\n")
    hdr = f"{'shell':6s} {'sd':>2} | " + " ".join(f"T={t:<2d}".rjust(7) for t in BUDGETS)
    print(hdr)
    for name, w, npairs in SHELLS:
        A, W = grid_isl_graph(w, 0.0, seam=False)
        pos = w.positions(0.0)
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            dem = gravity_demands(pos, npairs, rng)
            blind = evaluate(A, W, dem, CAP, policy="blind")["total_ttt"]
            ue = evaluate(A, W, dem, CAP, policy="ue")["total_ttt"]
            span = blind - ue
            row = {"shell": name, "pairs": npairs, "seed": seed,
                   "blind_ttt": round(blind, 4), "ue_ttt": round(ue, 4),
                   "unit_of_analysis": "shell-x-seed"}
            cells = []
            for t in BUDGETS:
                ttt = msa_truncated(A, W, dem, CAP, t)
                rec = (blind - ttt) / span if span > 0 else float("nan")
                row[f"recovered_T{t}"] = round(rec, 4)
                cells.append(f"{rec:>7.3f}")
            rows.append(row)
            print(f"{name:6s} {seed:>2} | " + " ".join(cells))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== TRUNG VI theo ngan sach ===")
    for t in BUDGETS:
        print(f"  MSA T={t:<2d} ({t} luot AoN): recovered = "
              f"{st.median(r[f'recovered_T{t}'] for r in rows):.3f}")

    # doc lai chinh so cua bai de so, khong go tay
    p6 = os.path.join(ROOT, "results", "p6_baselines.csv")
    gnn_rec = None
    if os.path.exists(p6):
        pr = list(csv.DictReader(open(p6)))
        vals = []
        for r in pr:
            b, u, g = float(r["blind"]), float(r["ue"]), float(r["gnn"])
            if b - u > 0:
                vals.append((b - g) / (b - u))
        if vals:
            gnn_rec = st.median(vals)
            print(f"\n  GNN (2 luot + 1 forward), lay tu p6_baselines.csv: "
                  f"recovered = {gnn_rec:.3f}  (n={len(vals)})")

    print("\n=== PHAN QUYET: o ngan sach KHOP (~2 luot), ai hon? ===")
    m2 = st.median(r["recovered_T2"] for r in rows)
    print(f"  MSA T=2 : {m2:.3f}")
    if gnn_rec is None:
        print("  GNN     : khong doc duoc p6_baselines.csv => CHUA so sanh duoc")
        return 2
    print(f"  GNN     : {gnn_rec:.3f}")
    d = gnn_rec - m2
    if d > 0.05:
        print(f"  => GNN hon {d:+.3f}. Loi the o ngan sach khop la THAT, va day chinh la")
        print("     con so phai dua vao bai de tra loi R2.7.")
    elif d < -0.05:
        print(f"  => ⛔ GNN THUA {d:+.3f}. Mot vong MSA cat ngan re bang the ma tot hon.")
        print("     Day la loi tien de, khong phai loi trinh bay. PHAI biet truoc khi bo 3-5 tuan.")
    else:
        print(f"  => HOA ({d:+.3f}). O ngan sach khop, mang hoc khong mua them gi dang ke;")
        print("     tuyen bo phai chuyen sang truc khac (vd tinh chuyen giao, on dinh), khong")
        print("     phai truc chat luong-tren-ngan-sach.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
