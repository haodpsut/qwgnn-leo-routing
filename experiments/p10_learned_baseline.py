"""
P10: a learned-routing baseline (GNN-NextHop) for a fair comparison.

Reviewers of learned traffic engineering expect a comparison to a learned method, not
only to blind / geographic / one-step / UE. We add the canonical alternative to our
edge-price approach: instead of predicting one congestion-price FIELD decoded by a
classical router, GNN-NextHop predicts, PER DESTINATION, the routing potential
(cost-to-go under the equilibrium cost) and routes by greedy descent. It sees the same
observable features as our method (demand + blind load) plus a destination indicator.

This exposes two costs of the direct-routing approach: (i) greedy descent on a regressed
potential can stall in false local minima (we add a shortest-path fallback so travel
time stays comparable, and report the greedy delivery rate separately); and (ii) it needs
one forward pass PER DESTINATION, versus one forward total for the edge-price field.

Reports, on the same instances as the baseline table: TTT relative to blind, greedy
delivery rate, and the number of forward passes.
"""
import csv
import os
import sys

import networkx as nx
import numpy as np
import torch
import torch.nn as nn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "smoke"))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from models import normalized_adj
from constellation import Walker
from traffic import link_cost, edge_loads, _realized, _route_on_cost, route_and_measure, evaluate
from p5_gnn_router import make_instance, build_features, TRAIN_WALKER, TRAIN_PAIRS, CAP

SEEDS = [0, 1, 2]
N_TRAIN_INST = 8
N_EVAL = 3
N_DEST_TRAIN = 16          # destinations sampled per train instance
DEPTH, HIDDEN, EPOCHS, LR = 3, 32, 300, 1e-2
OOD = (Walker(264, 24, 1, 53.0, 550.0), 1200)
OUT = os.path.join(ROOT, "results", "p10_learned.csv")


class PotentialGNN(nn.Module):
    """Node features (+dest indicator) -> per-node routing potential (cost-to-go)."""
    def __init__(self, in_dim, hidden=HIDDEN, layers=DEPTH):
        super().__init__()
        self.inp = nn.Linear(in_dim, hidden).double()
        self.mix = nn.ModuleList([nn.Linear(hidden, hidden).double() for _ in range(layers)])
        self.out = nn.Linear(hidden, 1).double()
        self.act = nn.ReLU()
        self.layers = layers

    def forward(self, X, Ahat):
        h = self.act(self.inp(X))
        for li in range(self.layers):
            h = self.act(self.mix[li](Ahat @ h))
        return self.out(h).squeeze(-1)


def ue_cost_matrix(ins):
    W = ins["W_np"].copy()
    g = np.zeros_like(W)
    g[ins["rows"], ins["cols"]] = ins["g_star"].numpy()
    return W * (1 + g)


def potential_to(d, ue_cost, A_np):
    """Cost-to-go to d under ue_cost (one Dijkstra on the reversed graph)."""
    G = nx.DiGraph()
    r, c = np.nonzero(A_np)
    for a, b in zip(r.tolist(), c.tolist()):
        G.add_edge(a, b, weight=float(ue_cost[a, b]))
    dist = nx.single_source_dijkstra_path_length(G.reverse(copy=False), int(d), weight="weight")
    n = A_np.shape[0]
    phi = np.array([dist.get(i, 1e6) for i in range(n)], dtype=np.float64)
    return phi


def node_feats(ins):
    """Same demand + blind-load node features as our method (without the dest indicator)."""
    X, _, _, _, _ = build_features(ins["A_np"], ins["W_np"], ins["dem"], need_eig=False)
    return X.numpy()                                  # (n, 4)


def make_train_samples(insts):
    samples = []
    for ins in insts:
        Ahat = torch.from_numpy(normalized_adj(
            torch.from_numpy(ins["A_np"].astype(np.float64))).numpy())
        base = node_feats(ins)
        uec = ue_cost_matrix(ins)
        n = ins["n"]
        rng = np.random.default_rng(ins["n"])
        dests = rng.choice(n, size=min(N_DEST_TRAIN, n), replace=False)
        for d in dests:
            phi = potential_to(d, uec, ins["A_np"])
            phi = phi / (phi[phi < 1e5].max() + 1e-9)
            ind = np.zeros((n, 1)); ind[d, 0] = 1.0
            X = torch.from_numpy(np.concatenate([ind, base], axis=1))
            samples.append((X, Ahat, torch.from_numpy(phi)))
    return samples


def train(samples, seed):
    torch.manual_seed(seed)
    model = PotentialGNN(in_dim=samples[0][0].shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    mse = nn.MSELoss()
    for _ in range(EPOCHS):
        opt.zero_grad()
        loss = 0.0
        for X, Ahat, phi in samples:
            keep = phi < 1e5
            loss = loss + mse(model(X, Ahat)[keep], phi[keep])
        loss.backward(); opt.step()
    return model


def greedy_route(phi, A_np, src, dst, max_steps):
    cur, seen, path = src, {src}, [src]
    nbrs = [np.nonzero(A_np[i] > 0)[0] for i in range(A_np.shape[0])]
    for _ in range(max_steps):
        if cur == dst:
            return path
        cand = nbrs[cur]
        nxt = int(cand[int(np.argmin(phi[cand]))])
        if phi[nxt] >= phi[cur] or nxt in seen:
            return None                              # stalled
        seen.add(nxt); path.append(nxt); cur = nxt
    return None


def eval_learned(model, ins):
    A_np, W_np, dem, cap = ins["A_np"], ins["W_np"], ins["dem"], ins["cap"]
    n = ins["n"]
    Ahat = torch.from_numpy(normalized_adj(
        torch.from_numpy(A_np.astype(np.float64))).numpy())
    base = node_feats(ins)
    free = link_cost(W_np, np.zeros_like(W_np), cap)
    by_dst = {}
    for s, d, r in dem:
        by_dst.setdefault(int(d), []).append((int(s), r))
    paths, delivered, total = [], 0, 0
    for d, srcs in by_dst.items():
        ind = np.zeros((n, 1)); ind[d, 0] = 1.0
        X = torch.from_numpy(np.concatenate([ind, base], axis=1))
        with torch.no_grad():
            phi = model(X, Ahat).numpy()
        for s, r in srcs:
            total += 1
            p = greedy_route(phi, A_np, s, d, 4 * n)
            if p is not None:
                delivered += 1
                paths.append((p, r))
            else:                                    # SP fallback on free-flow cost
                fb = _route_on_cost(A_np, free, [(s, d, r)])[0][0]
                paths.append((fb, r))
    load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    ttt, _ = _realized(W_np, load, cap, dem, paths)
    return {"ttt": ttt, "delivery": delivered / max(total, 1), "forwards": len(by_dst)}


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    print(f"{'seed':>4} {'split':8s} | {'blind':>6} {'learned':>8} {'GNN(ours)':>9} {'UE':>6} "
          f"| {'deliv':>6} {'fwd':>5}")
    for seed in SEEDS:
        tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 100 + seed * 50 + i, need_eig=False)
              for i in range(N_TRAIN_INST)]
        model = train(make_train_samples(tr), seed)
        for split, (w, npairs) in [("in-dist", (TRAIN_WALKER, TRAIN_PAIRS)), ("ood", OOD)]:
            for j in range(N_EVAL):
                ins = make_instance(w, npairs, 800 + seed * 10 + j, need_eig=False)
                blind = route_and_measure(ins["A_np"], ins["W_np"], ins["dem"], ins["cap"],
                                          ins["W_np"])["total_ttt"]
                ue = evaluate(ins["A_np"], ins["W_np"], ins["dem"], ins["cap"], "ue")["total_ttt"]
                lr = eval_learned(model, ins)
                rows.append({"seed": seed, "split": split, "r_blind": 1.0,
                             "r_learned": lr["ttt"] / blind, "r_ue": ue / blind,
                             "delivery": lr["delivery"], "forwards": lr["forwards"]})
            rs = [r for r in rows if r["seed"] == seed and r["split"] == split]
            m = lambda k: np.mean([r[k] for r in rs])
            print(f"{seed:>4} {split:8s} | {1.0:>6.2f} {m('r_learned'):>8.2f} {'(see p6)':>9} "
                  f"{m('r_ue'):>6.2f} | {m('delivery'):>6.0%} {m('forwards'):>5.0f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader(); wtr.writerows(rows)
    verdict(rows)


def verdict(rows):
    print("\n" + "=" * 64)
    for split in ("in-dist", "ood"):
        rs = [r for r in rows if r["split"] == split]
        g = lambda k: np.mean([r[k] for r in rs])
        print(f"  {split:8s} | learned-NextHop TTT/blind {g('r_learned'):.2f}  "
              f"greedy delivery {g('delivery'):.0%}  forwards/slot {g('forwards'):.0f}  "
              f"(UE {g('r_ue'):.2f})")
    print("  Compare learned TTT/blind to our edge-price+multipath (p6: in-dist 0.42, OOD 0.12),")
    print("  and note our method uses 1 forward/slot vs forwards/slot above.")
    print("=" * 64)


if __name__ == "__main__":
    main()
