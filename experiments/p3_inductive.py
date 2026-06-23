"""
P3 kill-gate: inductive scale generalization (the "why a GNN at all").

Train ONE model on small shells only, then ZERO-SHOT it on a much larger unseen
shell with no retraining. The learned weights are graph-size-agnostic (the
propagation operator is recomputed per graph; only the Linear maps transfer), so
this directly tests whether a small-constellation-trained router generalizes to a
mega-constellation.

We judge ROUTING quality, not just regression error: from the predicted potential
we do greedy next-hop descent and measure
  - delivery rate : fraction of (source,dest) pairs that reach the destination
                    without getting stuck in a false local minimum or looping;
  - path stretch  : delivered-path delay / Dijkstra-optimal delay  (>= 1.0).
Dijkstra-optimal is the reference (stretch 1.0, delivery 1.0). A model that routes
near-optimally zero-shot on a 1584-sat shell after training on <=132-sat shells is
a genuine, GNN-justifying result.

Local run trains on iridium66 + starlink_mini132 and tests on starlink_mini264.
On the server add the full shell:  QWGNN_FULL=1 python experiments/p3_inductive.py
"""

import csv
import os
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "smoke"))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from models import GCN, HeatGNN, QWGNN, build_ctx, count_params   # smoke/
from constellation import Walker                                   # sim/
from dataset import build_routing_dataset                          # sim/

TRAIN_SHELLS = [
    ("iridium66",        Walker(66,  6, 1, 86.4, 780.0)),
    ("starlink_mini132", Walker(132, 12, 1, 53.0, 550.0)),
]
TEST_SHELLS = [
    ("starlink_mini264", Walker(264, 24, 1, 53.0, 550.0)),
]
if os.environ.get("QWGNN_FULL") == "1":
    TEST_SHELLS.append(("starlink_shell1", Walker(1584, 72, 1, 53.0, 550.0)))

SEEDS = [0, 1, 2]
DEPTH = 3
HIDDEN = 32
N_DEST_TRAIN = 24
N_DEST_TEST = 12
N_ROUTE_PAIRS = 400          # (source, dest) pairs sampled for routing eval
EPOCHS = 400
LR = 1e-2
OUT = os.path.join(ROOT, "results", "p3_results.csv")


def make_train_set(seed):
    data = []
    for name, w in TRAIN_SHELLS:
        ds = build_routing_dataset(w, 0.0, N_DEST_TRAIN, seed=seed, seam=False)
        ds["ctx"] = build_ctx(ds["A"])
        data.append(ds)
    return data


def train_inductive(ModelCls, train_set, seed):
    torch.manual_seed(seed)
    model = ModelCls(hidden=HIDDEN, layers=DEPTH, in_dim=1)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    lossf = torch.nn.MSELoss()
    for _ in range(EPOCHS):
        opt.zero_grad()
        loss = 0.0
        for ds in train_set:
            loss = loss + lossf(model(ds["X"], ds["ctx"]), ds["Y"])
        loss.backward()
        opt.step()
    return model


def greedy_route(phi, A, W, src, dst, max_steps):
    """Greedy descent on predicted potential phi. Returns (delivered, delay)."""
    cur = src
    visited = {cur}
    delay = 0.0
    for _ in range(max_steps):
        if cur == dst:
            return True, delay
        nbrs = torch.nonzero(A[cur] > 0, as_tuple=False).flatten().tolist()
        # pick neighbor with lowest predicted potential
        nbrs.sort(key=lambda j: phi[j].item())
        nxt = nbrs[0]
        if phi[nxt].item() >= phi[cur].item() or nxt in visited:
            return False, delay              # stuck in local min / loop
        delay += W[cur, nxt].item()
        visited.add(nxt)
        cur = nxt
    return False, delay


def eval_routing(model, ds, seed):
    import networkx as nx
    A, W = ds["A"], ds["W"]
    n = ds["n"]
    Gw = nx.from_numpy_array(W.numpy())
    for u, v, dd in Gw.edges(data=True):
        dd["weight"] = W[u, v].item()

    rng = np.random.default_rng(10_000 + seed)
    # destinations to evaluate (fresh indicators, zero-shot)
    dests = rng.choice(n, size=min(N_DEST_TEST, n), replace=False)
    X = torch.zeros((len(dests), n, 1), dtype=torch.float64)
    for k, d in enumerate(dests):
        X[k, d, 0] = 1.0
    with torch.no_grad():
        phi_all = model(X, build_ctx(A))         # (len(dests), n)

    max_steps = 4 * ds["diameter"]
    delivered, stretches, mae_far = 0, [], []
    pairs = 0
    for k, d in enumerate(dests):
        opt_delay = nx.single_source_dijkstra_path_length(Gw, int(d), weight="weight")
        srcs = rng.choice([s for s in range(n) if s != d],
                          size=min(N_ROUTE_PAIRS // len(dests), n - 1),
                          replace=False)
        for s in srcs:
            pairs += 1
            ok, dly = greedy_route(phi_all[k], A, W, int(s), int(d), max_steps)
            if ok and opt_delay.get(int(s), 0) > 0:
                delivered += 1
                stretches.append(dly / opt_delay[int(s)])
    return {
        "delivery": delivered / max(pairs, 1),
        "stretch_med": float(np.median(stretches)) if stretches else float("nan"),
        "stretch_p90": float(np.percentile(stretches, 90)) if stretches else float("nan"),
        "pairs": pairs,
    }


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    print(f"train on: {[s[0] for s in TRAIN_SHELLS]}  ->  zero-shot test\n")
    print(f"{'model':5s} {'test_shell':18s} {'diam':>4} {'seed':>4} | "
          f"{'delivery':>9} {'stretch_med':>11} {'stretch_p90':>11}")
    for seed in SEEDS:
        train_set = make_train_set(seed)
        for M in (GCN, HeatGNN, QWGNN):
            model = train_inductive(M, train_set, seed)
            for name, w in TEST_SHELLS:
                ds = build_routing_dataset(w, 0.0, 1, seed=seed, seam=False)
                r = eval_routing(model, ds, seed)
                rows.append({"model": M.name, "test_shell": name,
                             "diameter": ds["diameter"], "seed": seed,
                             "params": count_params(model), **r})
                print(f"{M.name:5s} {name:18s} {ds['diameter']:>4} {seed:>4} | "
                      f"{r['delivery']:>9.3f} {r['stretch_med']:>11.3f} "
                      f"{r['stretch_p90']:>11.3f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    verdict(rows)


def verdict(rows):
    print("\n" + "=" * 72)
    shells = sorted({(r["test_shell"], r["diameter"]) for r in rows},
                    key=lambda x: x[1])
    print(f"{'model':5s} {'test_shell':18s} | {'delivery':>9} {'stretch_med':>11}")
    best = {}
    for M in ("GCN", "Heat", "QW"):
        for name, diam in shells:
            rs = [r for r in rows if r["model"] == M and r["test_shell"] == name]
            dlv = np.mean([r["delivery"] for r in rs])
            st = np.nanmean([r["stretch_med"] for r in rs])
            best[(M, name)] = (dlv, st)
            print(f"{M:5s} {name:18s} | {dlv:>9.3f} {st:>11.3f}")
    print("\nP3 VERDICT (zero-shot routing on unseen larger shells)")
    # PASS if some model delivers near-everything at low stretch zero-shot
    ok = False
    for (M, name), (dlv, st) in best.items():
        if dlv >= 0.95 and st <= 1.10:
            ok = True
    if ok:
        print("  => PASS: a small-shell-trained GNN routes near-optimally zero-shot")
        print("           (delivery >=0.95, median stretch <=1.10) on a larger shell.")
        print("           This is the GNN-justifying contribution. Build P2 next.")
    else:
        print("  => NOT YET: no model hits delivery>=0.95 & stretch<=1.10 zero-shot.")
        print("           Inspect failure modes (local minima) before claiming P3.")
    print("=" * 72)


if __name__ == "__main__":
    main()
