"""R3.2: does the headroom survive when a link cannot carry more than its capacity?

REVIEWER 3, COMMENT 2 (TNSM-2026-11591, 16/08/2026):
    "Blind routing is reported to drive some links to nine times their capacity, which
     produces the forty-fold headline gap through the fourth-power cost. A data link cannot
     actually carry nine times its capacity. You may want to enforce flow feasibility or
     packet loss and reassess how much headroom remains."

The objection is well aimed. `sim/traffic.py` says so in its own docstring: "No hard drops
(BPR), so every demand is delivered". BPR is a road-traffic volume-delay function, and on a road
v/c > 1 is a real state: cars still arrive, just later, and the fourth power describes that delay.

BE PRECISE ABOUT WHAT IS IMPOSSIBLE. Offering a link nine times its capacity IS a real operating
state; a moving hotspot produces exactly that. What cannot happen is a link CARRYING nine times its
capacity. So the flaw is not that the sweep visits an unreachable load regime. The flaw is in the
METRIC: BPR turns the excess into fourth-power DELAY, whereas on a packet link the excess is LOST.
The headline is therefore measured in a currency the system does not use up there.

That is not a hidden flaw. The paper reports the 9x utilisation in Section VIII-A and states in
Section XI that "below an average utilization of about one, blind shortest path is within a few
percent of optimal". What the paper never does is ask the reviewer's question: with feasibility
enforced, IS THERE STILL A GAP, and what is it a gap in?

WHAT THIS SCRIPT DOES. Same shells, same load sweep, same seeds as p4_congestion_headroom.py, so
every row here lines up with a row of results/p4_headroom.csv. For each policy it takes the routed
paths and applies a hard-capacity model:

    a link with load L and capacity C delivers min(L, C); each flow crossing it keeps the
    fraction min(1, C/L), and a flow's end-to-end delivery is the product along its path.

Goodput is then the delivered rate summed over demands. This is the simplest feasibility model that
does not require inventing a queueing discipline: it is proportional (max-min would be kinder to
small flows), it is memoryless across hops, and it is stated rather than assumed.

WHAT IT PRINTS. Per DC-6, the null condition sits next to the headline: the original BPR gain and
the feasibility-enforced gain, on the same row, so the reader sees exactly how much of the effect
was the extrapolation. It also splits rows by whether blind routing stayed inside capacity, because
that is the only regime where the BPR number was ever meaningful.
"""
import csv
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from constellation import Walker, grid_isl_graph          # noqa: E402
from traffic import (gravity_demands, edge_loads, link_cost,  # noqa: E402
                     _route_on_cost, ue_loads)

SHELLS = [("starlink_mini132", Walker(132, 12, 1, 53.0, 550.0)),
          ("starlink_mini264", Walker(264, 24, 1, 53.0, 550.0))]
N_PAIRS = [100, 300, 600, 1000, 1600]
SEEDS = [0, 1, 2]
CAP = 20.0
OUT = os.path.join(ROOT, "results", "r3_2_feasibility.csv")


def paths_for(A, prop_W, demands, cap, policy):
    """Return the routed paths for a policy, using the paper's own routines."""
    if policy == "blind":
        cost = link_cost(prop_W, np.zeros_like(prop_W), cap)
    else:
        load, _ = ue_loads(A, prop_W, demands, cap)
        cost = link_cost(prop_W, load, cap)
    return _route_on_cost(A, cost, demands)


def goodput(paths, load, cap):
    """Delivered rate under a hard capacity: each link passes min(1, cap/load) of what enters."""
    with np.errstate(divide="ignore", invalid="ignore"):
        keep = np.minimum(1.0, cap / np.where(load > 0, load, np.inf))
    offered = delivered = 0.0
    for nodes, rate in paths:
        if nodes is None:
            continue
        offered += rate
        surv = 1.0
        for a, b in zip(nodes[:-1], nodes[1:]):
            surv *= keep[a, b]
        delivered += rate * surv
    return offered, delivered


def ttt(prop_W, load, cap, paths):
    """Realized total travel time under BPR, i.e. the paper's own headline metric."""
    real = link_cost(prop_W, load, cap)
    tot = 0.0
    for nodes, rate in paths:
        if nodes is None:
            continue
        tot += rate * sum(real[a, b] for a, b in zip(nodes[:-1], nodes[1:]))
    return tot


def main():
    rows = []
    print("R3.2 -- ep kha thi theo dung luong, so canh ket qua BPR goc\n")
    print(f"{'shell':17s} {'pairs':>5} {'sd':>2} | {'blind_util':>10} | "
          f"{'gain BPR%':>9} | {'goodput blind':>13} {'goodput ue':>10} {'gain gp%':>8}")
    for name, w in SHELLS:
        A, W = grid_isl_graph(w, 0.0, seam=False)
        pos = w.positions(0.0)
        n = A.shape[0]
        for npairs in N_PAIRS:
            for seed in SEEDS:
                rng = np.random.default_rng(seed)
                dem = gravity_demands(pos, npairs, rng)
                out = {}
                for pol in ("blind", "ue"):
                    p = paths_for(A, W, dem, CAP, pol)
                    ld = edge_loads([(q, r) for q, r in p if q is not None], n)
                    off, dlv = goodput(p, ld, CAP)
                    out[pol] = {"util": float((ld / CAP).max()), "ttt": ttt(W, ld, CAP, p),
                                "offered": off, "delivered": dlv}
                g_bpr = 100.0 * (out["blind"]["ttt"] - out["ue"]["ttt"]) / out["blind"]["ttt"]
                g_gp = 100.0 * (out["ue"]["delivered"] - out["blind"]["delivered"]) \
                    / out["blind"]["delivered"] if out["blind"]["delivered"] > 0 else float("nan")
                rows.append({"shell": name, "pairs": npairs, "seed": seed,
                             "blind_maxutil": round(out["blind"]["util"], 4),
                             "ue_maxutil": round(out["ue"]["util"], 4),
                             "gain_bpr_pct": round(g_bpr, 3),
                             "blind_delivered_frac": round(out["blind"]["delivered"] / out["blind"]["offered"], 4),
                             "ue_delivered_frac": round(out["ue"]["delivered"] / out["ue"]["offered"], 4),
                             "gain_goodput_pct": round(g_gp, 3),
                             "unit_of_analysis": "shell-x-load-x-seed"})
                print(f"{name:17s} {npairs:>5} {seed:>2} | {out['blind']['util']:>10.2f} | "
                      f"{g_bpr:>9.1f} | {out['blind']['delivered']/out['blind']['offered']:>13.3f} "
                      f"{out['ue']['delivered']/out['ue']['offered']:>10.3f} {g_gp:>8.1f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")
    print("=== NULL CONDITION theo DC-6: hai thuoc do canh nhau, tach theo mien kha thi ===")
    print(f"{'mien':28s} {'n':>3} {'gain BPR% (trung vi)':>21} {'gain goodput% (trung vi)':>25}")
    # Nhan phai chinh xac: tai DUA VAO 9x la trang thai VAN HANH CO THAT (hotspot). Cai bat kha
    # la tai DUOC CHUYEN 9x. Loi cua BPR khong phai o cho cho phep dua vao qua nhieu, ma o cho no
    # bien phan thua thanh DO TRE mu bon thay vi thanh MAT GOI.
    for lbl, lo, hi in (("tai dua vao <= dung luong", 0, 1.0),
                        ("tai dua vao 1-2x", 1.0, 2.0),
                        ("tai dua vao 2-4x", 2.0, 4.0),
                        ("tai dua vao >4x", 4.0, 1e9)):
        sel = [r for r in rows if lo <= r["blind_maxutil"] < hi]
        if not sel:
            continue
        print(f"{lbl:28s} {len(sel):>3} {st.median(r['gain_bpr_pct'] for r in sel):>21.2f} "
              f"{st.median(r['gain_goodput_pct'] for r in sel):>25.2f}")
    feas = [r for r in rows if r["blind_maxutil"] <= 1.0]
    print(f"\n  {len(feas)}/{len(rows)} cau hinh co tai dua vao nam trong dung luong.")
    print("  Cac dong con lai VAN la trang thai van hanh co that: mot hotspot CO THE dua vao")
    print("  gap 9 lan dung luong. Cai khong the xay ra la lien ket CHUYEN duoc 9 lan do.")
    print("  ⇒ Loi khong nam o mien tai, ma o THUOC DO: BPR bien phan thua thanh do tre mu bon,")
    print("    trong khi tren lien ket goi phan thua bi MAT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
