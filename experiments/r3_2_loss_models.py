"""Is "UE loses goodput at extreme overload" a property of the system, or of my loss model?

r3_2_feasibility.py found that above ~4x offered load the delay-optimal routing delivers LESS than
blind routing, by up to 23%. Before that goes anywhere near the paper it has to survive the check
that the finding is not manufactured by the one modelling choice I made.

That choice was: per-link PROPORTIONAL drop, compounded MULTIPLICATIVELY along the path. Under it a
flow crossing k congested links keeps the product of k fractions, so LONGER paths are punished
super-linearly. The delay-optimal routing spreads traffic onto longer detours by construction. So
the mechanism I proposed for the negative result ("longer paths lose more") is exactly what that
model is built to produce. That is not evidence, that is a tautology waiting to be caught.

So run three models that disagree about precisely this, on the same routes and the same loads:

  product : delivery = product over links of min(1, C/L)   -- compounding, punishes hop count
  bottleneck : delivery = min over links of min(1, C/L)    -- NO compounding; only the worst link
               matters, so hop count is free
  maxmin  : per link, capacity is shared max-min fairly among the flows crossing it, then the
            flow's delivery is the min of its per-link shares -- protects small flows from being
            scaled down by an elephant sharing the link

TWO CLAIMS, SCORED SEPARATELY. My first attempt tested only whether the SIGN OF THE MEDIAN held,
and concluded from that alone that "the finding belongs to the routing". That is a proxy, and it
hides the thing actually under test. The positive claim (UE delivers more, and how much more) and
the negative claim (UE can deliver LESS at extreme overload) can survive the bracket differently,
so each gets its own verdict:

  positive : is the median gain > 0 under ALL three models, and what is the spread? If it holds,
             the number must be reported as the RANGE across models, not as the prettiest one.
  negative : does the fraction of configurations where UE loses hold up under all three? If it
             collapses when the compounding is removed, the effect was the model's, not the
             system's, and it must not enter the paper.

The three are not equally realistic and the point is not to pick a winner. They BRACKET the
question: `product` is the harshest possible reading of multi-hop loss, `bottleneck` the kindest,
`maxmin` a fairness-aware middle. A conclusion that survives the bracket is worth reporting with
the bracket shown.
"""
import csv
import os
import statistics as st
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from constellation import Walker, grid_isl_graph            # noqa: E402
from traffic import (gravity_demands, edge_loads, link_cost,  # noqa: E402
                     _route_on_cost, ue_loads)

SHELLS = [("starlink_mini132", Walker(132, 12, 1, 53.0, 550.0)),
          ("starlink_mini264", Walker(264, 24, 1, 53.0, 550.0))]
N_PAIRS = [100, 300, 600, 1000, 1600]
SEEDS = [0, 1, 2]
CAP = 20.0
OUT = os.path.join(ROOT, "results", "r3_2_loss_models.csv")


def paths_for(A, prop_W, demands, cap, policy):
    if policy == "blind":
        cost = link_cost(prop_W, np.zeros_like(prop_W), cap)
    else:
        load, _ = ue_loads(A, prop_W, demands, cap)
        cost = link_cost(prop_W, load, cap)
    return _route_on_cost(A, cost, demands)


def _edges(nodes):
    return list(zip(nodes[:-1], nodes[1:]))


def maxmin_shares(paths, cap):
    """Per link, split capacity max-min fairly across the flows crossing it."""
    on = defaultdict(list)
    for i, (nodes, rate) in enumerate(paths):
        if nodes is None:
            continue
        for e in _edges(nodes):
            on[e].append(i)
    share = {}
    rates = {i: r for i, (n, r) in enumerate(paths) if n is not None}
    for e, idxs in on.items():
        demand = sorted(((rates[i], i) for i in idxs))
        remaining, k = cap, len(demand)
        alloc = {}
        for r, i in demand:                      # classic water-filling
            fair = remaining / k
            if r <= fair:
                alloc[i] = r
                remaining -= r
            else:
                alloc[i] = fair
                remaining -= fair
            k -= 1
        share[e] = alloc
    return share


def delivered(paths, cap, model):
    """Total delivered rate under one of the three feasibility models."""
    n_nodes = max(max(nodes) for nodes, _ in paths if nodes is not None) + 1
    load = edge_loads([(p, r) for p, r in paths if p is not None], n_nodes)
    with np.errstate(divide="ignore", invalid="ignore"):
        keep = np.minimum(1.0, cap / np.where(load > 0, load, np.inf))
    mm = maxmin_shares(paths, cap) if model == "maxmin" else None
    offered = out = 0.0
    for i, (nodes, rate) in enumerate(paths):
        if nodes is None:
            continue
        offered += rate
        es = _edges(nodes)
        if model == "product":
            out += rate * float(np.prod([keep[a, b] for a, b in es]))
        elif model == "bottleneck":
            out += rate * float(min(keep[a, b] for a, b in es))
        elif model == "maxmin":
            out += float(min(mm[(a, b)][i] for a, b in es))
        else:
            raise ValueError(model)
    return offered, out


def main():
    models = ("product", "bottleneck", "maxmin")
    rows = []
    print("R3.2b -- MOT phat hien, BA mo hinh mat mat. Dau cua khoang cach co doi khong?\n")
    print(f"{'shell':17s} {'pairs':>5} {'sd':>2} {'util':>6} | "
          + " | ".join(f"{m:>12s}" for m in models))
    for name, w in SHELLS:
        A, W = grid_isl_graph(w, 0.0, seam=False)
        pos = w.positions(0.0)
        n = A.shape[0]
        for npairs in N_PAIRS:
            for seed in SEEDS:
                rng = np.random.default_rng(seed)
                dem = gravity_demands(pos, npairs, rng)
                P = {p: paths_for(A, W, dem, CAP, p) for p in ("blind", "ue")}
                ld = edge_loads([(q, r) for q, r in P["blind"] if q is not None], n)
                util = float((ld / CAP).max())
                row = {"shell": name, "pairs": npairs, "seed": seed,
                       "blind_maxutil": round(util, 4), "unit_of_analysis": "shell-x-load-x-seed"}
                cells = []
                for m in models:
                    _, db = delivered(P["blind"], CAP, m)
                    _, du = delivered(P["ue"], CAP, m)
                    g = 100.0 * (du - db) / db if db > 0 else float("nan")
                    row[f"gain_{m}_pct"] = round(g, 3)
                    cells.append(f"{g:>12.1f}")
                rows.append(row)
                print(f"{name:17s} {npairs:>5} {seed:>2} {util:>6.2f} | " + " | ".join(cells))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== TRUNG VI theo mien tai, ba mo hinh canh nhau ===")
    print(f"{'tai dua vao':22s} {'n':>3} " + " ".join(f"{m:>12s}" for m in models))
    bands = (("<= dung luong", 0, 1.0), ("1-2x", 1.0, 2.0), ("2-4x", 2.0, 4.0), (">4x", 4.0, 1e9))
    for lbl, lo, hi in bands:
        sel = [r for r in rows if lo <= r["blind_maxutil"] < hi]
        if not sel:
            continue
        print(f"{lbl:22s} {len(sel):>3} "
              + " ".join(f"{st.median(r[f'gain_{m}_pct'] for r in sel):>12.1f}" for m in models))

    # HAI tuyen bo, phai cham RIENG. Ban dau toi chi kiem DAU CUA TRUNG VI roi ket luan
    # "phat hien thuoc ve dinh tuyen" -- do la do mot PROXY. Tuyen bo duong (UE thang bao nhieu)
    # va tuyen bo am (UE co thua khong) song sot khac han nhau, va gop chung lai thi giau mat
    # dung cai dang kiem.
    print("\n=== PHAN QUYET 1: tuyen bo DUONG -- UE co thang khong, va bao nhieu? ===")
    hi = [r for r in rows if r["blind_maxutil"] >= 4.0]
    meds = {m: st.median(r[f"gain_{m}_pct"] for r in hi) for m in models}
    for m in models:
        print(f"  {m:11s} trung vi {meds[m]:+7.1f}%")
    lo_m, hi_m = min(meds.values()), max(meds.values())
    same = all(v > 0 for v in meds.values())
    print(f"  => {'BEN VUNG' if same else 'KHONG ben vung'}: ca ba mo hinh cho UE thang, "
          f"khoang {lo_m:.0f}-{hi_m:.0f}%.")
    print("     Bao con so thi phai bao CA KHOANG nay, dung chon mo hinh cho so dep nhat.")

    print("\n=== PHAN QUYET 2: tuyen bo AM -- 'UE co the THUA o qua tai cuc doan' ===")
    for m in models:
        neg = sum(1 for r in hi if r[f"gain_{m}_pct"] < 0)
        print(f"  {m:11s} {neg}/{len(hi)} cau hinh UE thua")
    negs = {m: sum(1 for r in hi if r[f"gain_{m}_pct"] < 0) for m in models}
    robust = min(negs.values()) >= len(hi) // 3
    if robust:
        print("  => SONG SOT qua ca ba mo hinh.")
    else:
        worst = max(negs, key=negs.get); best = min(negs, key=negs.get)
        print(f"  => KHONG song sot. Voi '{worst}' thi {negs[worst]}/{len(hi)}, voi '{best}' chi "
              f"{negs[best]}/{len(hi)}.")
        print("     Co che 'duong dai hon mat nhieu hon' la thu ma phep NHAN DON theo chang")
        print("     duoc dung de sinh ra. Bo phep nhan do di thi hien tuong gan nhu bien mat.")
        print("     ⛔ KHONG duoc dua phat hien am nay vao bai nhu mot tinh chat cua he thong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
