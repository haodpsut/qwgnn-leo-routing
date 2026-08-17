"""R2.7, the two comparators that were still missing: WARM-STARTED MSA and ECMP.

r2_7_budget_matched.py filled the hole in Table VI with COLD-STARTED truncated MSA, and the GNN won
easily: 0.957 of the blind-to-UE gap recovered against -0.003 at the same two-pass budget. But that
is the easy half of Reviewer 2's request. MSA cold-started oscillates in its first iterations, so
truncating it at T=2 is close to a straw man, and the reviewer did not ask for that. They asked for
"WARM-STARTED MSA" by name.

Warm starting is the version that can actually threaten the learned price field. A constellation
drifts slowly, so consecutive slots are similar; an operator who keeps last slot's equilibrium load
and runs one or two MSA passes from THERE begins near the answer instead of at the blind pass. If
that recovers most of the gap at the GNN's budget, then what the network buys is not a learned
price field but a warm cache, and the paper's framing has to change.

The second missing comparator is ECMP-style multipath: split each demand equally across the
equal-cost shortest-path DAG on free-flow cost. It is congestion-blind and costs one pass, so it is
CHEAPER than the GNN, and it is the baseline any network operator would reach for first. If a blind
equal split already spreads load well enough to close much of the gap, the congestion-aware machinery
is answering a question the network had already solved.

SETUP. A sequence of consecutive slots on the same shell, so warm starting has something to reuse.
Satellite identity is stable across time in a Walker constellation, so last slot's load matrix
indexes the same links. Everything is scored with the paper's own metric,
recovered = (blind - policy) / (blind - ue), on the slot being evaluated.
"""
import csv
import os
import statistics as st
import sys

import numpy as np
import networkx as nx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from constellation import Walker, grid_isl_graph            # noqa: E402
from traffic import (gravity_demands, edge_loads, link_cost,   # noqa: E402
                     _route_on_cost, evaluate)

SHELLS = [("w132", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264", Walker(264, 24, 1, 53.0, 550.0), 1200)]
SEEDS = [0, 1, 2]
CAP = 20.0
SLOT_S = 60.0            # spacing between consecutive slots
N_SLOTS = 4              # slot 0 warms the cache; slots 1..3 are scored
DRIFT_PER_SLOT = 0.10    # hotspot band drift per slot (rad); nho => khe ke nhau giong nhau
WARM_BUDGETS = [1, 2]    # MSA passes spent FROM the warm start
OUT = os.path.join(ROOT, "results", "r2_7_warmstart_ecmp.csv")


def realized_ttt(prop_W, paths, cap):
    n = prop_W.shape[0]
    load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    real = link_cost(prop_W, load, cap)
    return sum(r * sum(real[a, b] for a, b in zip(p[:-1], p[1:]))
               for p, r in paths if p is not None)


def msa_from(A, prop_W, demands, cap, iters, load0=None, k0=1):
    """MSA for `iters` passes, optionally starting from a given load matrix (the warm start).

    k0 IS THE POINT. MSA's step is 1/(k+1), designed to shrink as the iterate settles. Starting a
    WARM run at k0=1 takes a 50% step away from a load that was already near equilibrium, which
    throws the warm start away and then blames it for the result. My first version did exactly
    that, and warm start came out worse than cold start -- a comparator I had crippled myself.
    A warm run continues the sequence, so it resumes at the k the cache was left at.
    """
    n = A.shape[0]
    if load0 is None:
        paths = _route_on_cost(A, link_cost(prop_W, np.zeros_like(prop_W), cap), demands)
        load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    else:
        load = load0.copy()
    for k in range(k0, k0 + iters):
        cost = link_cost(prop_W, load, cap)
        aon = _route_on_cost(A, cost, demands)
        aload = edge_loads([(p, r) for p, r in aon if p is not None], n)
        load = load + (aload - load) / (k + 1)
    final = _route_on_cost(A, link_cost(prop_W, load, cap), demands)
    return realized_ttt(prop_W, final, cap), load


def ecmp_ttt(A, prop_W, demands, cap, eps=0.0):
    """Multipath on free-flow cost: split equally over the (1+eps)-shortest-path DAG.

    eps=0 is textbook ECMP. On this topology that is a NO-OP: propagation delays are continuous,
    so 0/2620 nodes have two out-edges of exactly equal cost and ECMP collapses to blind single
    path. Reporting that as "ECMP recovers 0.0" and stopping would be answering the letter of
    Reviewer 2's request while dodging its intent. Operators deploy near-equal-cost splitting, so
    eps>0 is the comparator that actually tests whether the learned price field beats plain
    congestion-BLIND spreading.
    """
    n = A.shape[0]
    G = nx.DiGraph()
    rows, cols = np.nonzero(A)
    for a, b in zip(rows.tolist(), cols.tolist()):
        G.add_edge(a, b, weight=float(prop_W[a, b]))
    load = np.zeros((n, n))
    by_dst = {}
    for s, d, r in demands:
        by_dst.setdefault(d, []).append((s, r))
    Grev = G.reverse(copy=False)
    for d, srcs in by_dst.items():
        dist = nx.single_source_dijkstra_path_length(Grev, d, weight="weight")
        # out-edges that strictly decrease cost-to-go by exactly their weight are on a shortest path
        nxt = {}
        for u in dist:
            # Hai dieu kien, va dieu kien DAU la bat buoc: khoang cach toi dich phai GIAM NGAT,
            # neu khong thi tap canh "gan ngan nhat" khong con phi chu trinh, luu luong chay vong
            # va ket lai. Assertion ben duoi da bat dung ca do o eps=0,20 truoc khi no kip thanh
            # mot con so sai trong bang.
            outs = [v for v in G.successors(u)
                    if v in dist and dist[v] < dist[u] - 1e-12
                    and (G[u][v]["weight"] + dist[v]) <= dist[u] * (1.0 + eps) + 1e-12]
            if outs:
                nxt[u] = outs
        push = {}
        for s, r in srcs:
            if s in dist:
                push[s] = push.get(s, 0.0) + r
        # Duyet MOI nut theo thu tu xa -> gan dich. Ban dau toi duyet `sorted(push, ...)`, tuc mot
        # ANH CHUP khoa luc bat dau vong lap; nhung nut duoc day vao TRONG vong lap khong bao gio
        # duoc tham, nen luu luong di duoc mot chang roi bi bo roi. Hau qua la tai be xiu va TTT
        # thap gia tao, den muc ECMP "thang" ca system optimum. Chinh dieu bat kha do lam lo bug.
        for u in sorted(dist, key=lambda x: -dist[x]):
            amt = push.pop(u, 0.0)
            if amt <= 0 or u == d:
                continue
            outs = nxt.get(u)
            if not outs:
                continue
            share = amt / len(outs)
            for v in outs:
                load[u, v] += share
                push[v] = push.get(v, 0.0) + share
        leftover = sum(v for kk, v in push.items() if kk != d)
        assert leftover < 1e-6, f"ECMP bo roi {leftover:.4g} luu luong -- duyet DAG sai"
    real = link_cost(prop_W, load, cap)
    # Tong thoi gian di chuyen cua mot phan bo CO CHIA LUONG la  sum_e x_e * t_e(x_e).
    # Ban dau toi lay dijkstra tren `real` cho tung luong, tuc phat cho moi luong duong TOT NHAT
    # sau khi da tac nghen, chu khong phai duong no thuc su di. Sai do lam ECMP dep len,
    # va no lo ra vi ket qua qua deu: 1.011-1.174 o moi dong.
    return float((load * real).sum())


def main():
    rows = []
    print("R2.7b -- WARM-STARTED MSA va ECMP, hai comparator con thieu\n")
    print("recovered = (blind - policy) / (blind - ue) tren khe dang cham\n")
    print(f"{'shell':6s} {'sd':>2} {'khe':>3} | {'coldT2':>7} {'warmT1':>7} {'warmT2':>7} "
          f"{'ecmp.05':>7} {'ecmp.20':>7}")
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            warm = None
            for k in range(N_SLOTS):
                t = k * SLOT_S
                A, W = grid_isl_graph(w, t, seam=False)
                pos = w.positions(t)
                # CUNG seed, chi TROI dai hotspot -- dung cach p7_proactive.py lam. Ban dau toi
                # sinh nhu cau doc lap moi khe, tuc khe truoc khong lien quan gi khe sau, va warm
                # start bi tuoc mat dung cai lam no manh. Do la lam yeu comparator cua doi phuong.
                band = k * DRIFT_PER_SLOT
                dem = gravity_demands(pos, npairs, np.random.default_rng(seed),
                                      hotspot_shift=band)
                blind = evaluate(A, W, dem, CAP, policy="blind")["total_ttt"]
                ue_res = evaluate(A, W, dem, CAP, policy="ue")
                ue = ue_res["total_ttt"]
                span = blind - ue
                _, conv = msa_from(A, W, dem, CAP, 20)      # cache cho khe sau
                if k == 0:
                    warm = conv
                    continue
                rec = lambda x: (blind - x) / span if span > 0 else float("nan")
                cold2, _ = msa_from(A, W, dem, CAP, 2)
                w1, _ = msa_from(A, W, dem, CAP, 1, load0=warm, k0=20)
                w2, _ = msa_from(A, W, dem, CAP, 2, load0=warm, k0=20)
                e = ecmp_ttt(A, W, dem, CAP, eps=0.0)
                e05 = ecmp_ttt(A, W, dem, CAP, eps=0.05)
                e20 = ecmp_ttt(A, W, dem, CAP, eps=0.20)
                # CHAN CUNG: system optimum la gia tri NHO NHAT cua tong thoi gian di chuyen.
                # Bat ky chinh sach nao xuong duoi no la BUG chu khong phai phat hien. Phep kiem
                # nay da bat dung mot loi duyet DAG lam ECMP thap hon SO toi 5,5 lan.
                so_ttt = evaluate(A, W, dem, CAP, policy="so")["total_ttt"]
                assert e >= so_ttt - 1e-6, (f"ECMP {e:.3f} < system optimum {so_ttt:.3f}: vi pham "
                                            f"chan, phai sua truoc khi doc bat ky con so nao")
                row = {"shell": name, "seed": seed, "slot": k,
                       "recovered_cold_T2": round(rec(cold2), 4),
                       "recovered_warm_T1": round(rec(w1), 4),
                       "recovered_warm_T2": round(rec(w2), 4),
                       "recovered_ecmp": round(rec(e), 4),
                       "recovered_ecmp_eps05": round(rec(e05), 4),
                       "recovered_ecmp_eps20": round(rec(e20), 4),
                       "unit_of_analysis": "shell-x-seed-x-slot"}
                rows.append(row)
                print(f"{name:6s} {seed:>2} {k:>3} | {rec(cold2):>7.3f} {rec(w1):>7.3f} "
                      f"{rec(w2):>7.3f} {rec(e05):>7.3f} {rec(e20):>7.3f}")
                warm = conv

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    keys = [("recovered_cold_T2", "MSA lanh T=2   (2 luot)"),
            ("recovered_warm_T1", "MSA NONG  T=1   (1 luot)"),
            ("recovered_warm_T2", "MSA NONG  T=2   (2 luot)"),
            ("recovered_ecmp", "ECMP eps=0     (1 luot)"),
            ("recovered_ecmp_eps05", "ECMP eps=0.05  (1 luot)"),
            ("recovered_ecmp_eps20", "ECMP eps=0.20  (1 luot)")]
    print("=== TRUNG VI ===")
    for k, lbl in keys:
        print(f"  {lbl:26s} recovered = {st.median(r[k] for r in rows):>7.3f}")

    gnn = None
    p6 = os.path.join(ROOT, "results", "p6_baselines.csv")
    if os.path.exists(p6):
        v = [(float(r["blind"]) - float(r["gnn"])) / (float(r["blind"]) - float(r["ue"]))
             for r in csv.DictReader(open(p6)) if float(r["blind"]) - float(r["ue"]) > 0]
        gnn = st.median(v) if v else None
    print(f"  {'GNN (2 luot + forward)':26s} recovered = {gnn:>7.3f}" if gnn else "  GNN: ?")

    print("\n=== PHAN QUYET R2.7 ===")
    best_lbl, best = max(((lbl, st.median(r[k] for r in rows)) for k, lbl in keys),
                         key=lambda x: x[1])
    print(f"  Baseline manh nhat o ngan sach <= GNN: {best_lbl.strip()} = {best:.3f}")
    if gnn is None:
        return 2
    d = gnn - best
    if d > 0.05:
        print(f"  GNN hon {d:+.3f} => R2.7 TRA LOI DUOC. Bon comparator ho neu ten thi da co ba.")
    elif d < -0.05:
        print(f"  ⛔ GNN THUA {d:+.3f}. Loi the o ngan sach khop KHONG dung nhu bai tuyen bo.")
    else:
        print(f"  HOA ({d:+.3f}). Phai chuyen truc tuyen bo, dung giu truc chat-luong-tren-ngan-sach.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
