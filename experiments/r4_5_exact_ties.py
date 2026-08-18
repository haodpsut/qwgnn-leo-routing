"""R4.5: ECMP sach vo co thuc su la mot no-op tren topo nay khong? Dem TY LE HOA CHINH XAC.

Bai dung cau nay lam ly do bo ECMP nguyen ban va chuyen sang bien the co dung sai eps:

    "inter-satellite delays take continuous values, so of 2620 node-destination pairs examined
     not one had two out-edges of exactly equal cost"

Con so 2620 do, tinh den 18/08/2026, chi ton tai o MOT dong chu thich trong
r2_7_warmstart_ecmp.py va o van xuoi cua bai. Khong CSV, khong claim, khong cong nao voi toi.
Do la mot con so headline khong co xuat xu, va no chong do cho TOAN BO lua chon baseline.

Do lai cho tu te, tren nhieu vo, va ghi ra CSV. Neu ty le hoa khong phai 0 thi cau van trong
bai phai doi, va lua chon baseline phai duoc bien ho theo cach khac.

DINH NGHIA. Voi moi dich d, tinh khoang cach toi d tren do thi chi phi tu do. Mot nut u duoc
tinh la "co hoa" neu co it nhat HAI canh ra (u,v) cung thoa
    w(u,v) + dist(v) == dist(u)
o dung dang so hoc dau phay dong. Do la dieu kien ECMP sach vo dung de chia luu luong.
"""
import csv
import os
import sys

import networkx as nx
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker, grid_isl_graph                    # noqa: E402
from traffic import gravity_demands                                  # noqa: E402

SHELLS = [("w132_i53", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264_i53", Walker(264, 24, 1, 53.0, 550.0), 1200),
          ("w264_i70", Walker(264, 24, 1, 70.0, 550.0), 1200)]
SEEDS = [0, 1, 2]
OUT = os.path.join(ROOT, "results", "r4_5_exact_ties.csv")


def tie_counts(A, W, dests):
    """(so cap nut-dich xet, so cap CO hoa chinh xac) tren do thi chi phi tu do."""
    G = nx.DiGraph()
    rows, cols = np.nonzero(A)
    for a, b in zip(rows.tolist(), cols.tolist()):
        G.add_edge(a, b, weight=float(W[a, b]))
    Grev = G.reverse(copy=False)
    pairs = ties = 0
    for d in dests:
        dist = nx.single_source_dijkstra_path_length(Grev, d, weight="weight")
        for u in dist:
            if u == d:
                continue
            pairs += 1
            # So sanh BANG NHAU CHINH XAC, dung dung sai: day la dieu kien ECMP sach vo.
            n_shortest = sum(1 for v in G.successors(u)
                             if v in dist and G[u][v]["weight"] + dist[v] == dist[u])
            if n_shortest >= 2:
                ties += 1
    return pairs, ties


def main():
    print("R4.5 -- ECMP sach vo co phai no-op khong? Dem hoa chinh xac.\n", flush=True)
    rows = []
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            A, W = grid_isl_graph(w, 0.0, seam=False)
            pos = w.positions(0.0)
            dem = gravity_demands(pos, npairs, np.random.default_rng(900 + seed))
            dests = sorted({d for _, d, _ in dem})
            pairs, ties = tie_counts(A, W, dests)
            frac = ties / pairs if pairs else float("nan")
            rows.append({"shell": name, "n_sat": w.T, "seed": seed,
                         "unit_of_analysis": "vo-x-seed", "n_dests": len(dests),
                         "node_dest_pairs": pairs, "exact_tie_pairs": ties,
                         "tie_fraction": round(frac, 6)})
            print(f"  {name:10s} sd{seed}: {len(dests):4d} dich | {pairs:7d} cap nut-dich | "
                  f"hoa chinh xac: {ties}  ({100*frac:.4f}%)", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    tot_p = sum(r["node_dest_pairs"] for r in rows)
    tot_t = sum(r["exact_tie_pairs"] for r in rows)
    print("=== KET LUAN ===")
    print(f"  gop moi vo va seed: {tot_t} hoa tren {tot_p} cap nut-dich")
    if tot_t == 0:
        print("  ECMP sach vo la NO-OP tren topo nay: khong mot cap nao co hai canh ra dong chi phi.")
        print("  => bien the co dung sai eps khong phai mot lua chon tien loi, no la lua chon DUY NHAT")
        print("     co nghia. Cau trong bai dung, va nay co artifact do lai duoc.")
    else:
        print(f"  ⚠ CO {tot_t} cap co hoa. Cau 'khong mot cap nao' trong bai la SAI va phai sua.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
