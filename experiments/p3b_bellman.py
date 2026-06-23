"""
P3b: make the inductive potential greedy-routable with a Bellman-consistency loss.

P3 showed the regressed potential transfers in SHAPE (stretch ~1.03 when delivered)
but naive greedy descent is trapped by false local minima (delivery ~0.67). A
potential that satisfies the Bellman optimality recursion has NO false local
minima, so greedy descent is guaranteed to reach the destination. We therefore add
to the MSE target loss a penalty on the PREDICTED field:

    L_bell = mean_{v != d} ( phi_d(v) - min_{u in N(v)} [ w_norm_d(v,u) + phi_d(u) ] )^2

with w_norm_d = W / ecc_d (the same per-destination scale used to normalize the
target), and phi pinned to 0 at the destination. This trains the GNN to emit a
routable potential, not merely a low-MSE one -- tying the learned field to
classical shortest-path theory.

Compares lambda=0 (pure MSE, = P3) vs lambda>0 (Bellman) on zero-shot delivery.
Server full shell:  QWGNN_FULL=1 python experiments/p3b_bellman.py
"""

import csv
import os
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "smoke"))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from models import GCN, HeatGNN, QWGNN, build_ctx, count_params
from constellation import Walker
from dataset import build_routing_dataset
from p3_inductive import eval_routing            # reuse routing eval + greedy_route

TRAIN_SHELLS = [
    ("iridium66",        Walker(66,  6, 1, 86.4, 780.0)),
    ("starlink_mini132", Walker(132, 12, 1, 53.0, 550.0)),
]
TEST_SHELLS = [("starlink_mini264", Walker(264, 24, 1, 53.0, 550.0))]
if os.environ.get("QWGNN_FULL") == "1":
    TEST_SHELLS.append(("starlink_shell1", Walker(1584, 72, 1, 53.0, 550.0)))

SEEDS = [0, 1, 2]
DEPTH = 3
HIDDEN = 32
N_DEST_TRAIN = 24
EPOCHS = 500
LR = 1e-2
LAMBDAS = [0.0, 1.0]          # 0 = pure MSE (P3 baseline), 1.0 = Bellman-trained
OUT = os.path.join(ROOT, "results", "p3b_results.csv")


def bellman_residual(phi, ds):
    """
    Mean squared Bellman residual of predicted phi (B,n) for a graph.
    phi_d(v) should equal min_{u~v} [ W(v,u)/ecc_d + phi_d(u) ], v != d, phi_d(d)=0.
    """
    A, W = ds["ctx"]["A"], ds["W"]
    n = A.shape[0]
    big = 1e6
    # neighbor mask: where A==0 set additive +inf so it never wins the min
    mask = torch.where(A > 0, torch.zeros_like(A), torch.full_like(A, big))
    dests = ds["dests"]
    ecc = ds["ecc"]                                   # (B,)
    # cand[b,v,u] = W[v,u]/ecc[b] + phi[b,u] + mask[v,u]
    Wn = W.unsqueeze(0) / ecc.view(-1, 1, 1)          # (B,n,n)
    cand = Wn + phi.unsqueeze(1) + mask.unsqueeze(0)  # broadcast phi over v (dim1)
    rhs, _ = cand.min(dim=2)                          # (B,n)
    res = phi - rhs
    # exclude the destination node of each sample
    keep = torch.ones_like(phi, dtype=torch.bool)
    keep[torch.arange(phi.shape[0]), dests] = False
    return (res[keep] ** 2).mean()


def train(ModelCls, train_set, lam, seed):
    torch.manual_seed(seed)
    model = ModelCls(hidden=HIDDEN, layers=DEPTH, in_dim=1)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    mse = torch.nn.MSELoss()
    for _ in range(EPOCHS):
        opt.zero_grad()
        loss = 0.0
        for ds in train_set:
            phi = model(ds["X"], ds["ctx"])
            loss = loss + mse(phi, ds["Y"])
            if lam > 0:
                loss = loss + lam * bellman_residual(phi, ds)
        loss.backward()
        opt.step()
    return model


def make_train_set(seed):
    out = []
    for _, w in TRAIN_SHELLS:
        ds = build_routing_dataset(w, 0.0, N_DEST_TRAIN, seed=seed, seam=False)
        ds["ctx"] = build_ctx(ds["A"])
        out.append(ds)
    return out


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    print(f"{'model':5s} {'lam':>4} {'test_shell':18s} {'seed':>4} | "
          f"{'delivery':>9} {'stretch_med':>11}")
    for seed in SEEDS:
        train_set = make_train_set(seed)
        for M in (HeatGNN, QWGNN):           # GCN already shown to fail P3
            for lam in LAMBDAS:
                model = train(M, train_set, lam, seed)
                for name, w in TEST_SHELLS:
                    ds = build_routing_dataset(w, 0.0, 1, seed=seed, seam=False)
                    r = eval_routing(model, ds, seed)
                    rows.append({"model": M.name, "lam": lam, "test_shell": name,
                                 "diameter": ds["diameter"], "seed": seed,
                                 "params": count_params(model), **r})
                    print(f"{M.name:5s} {lam:>4.1f} {name:18s} {seed:>4} | "
                          f"{r['delivery']:>9.3f} {r['stretch_med']:>11.3f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    verdict(rows)


def verdict(rows):
    print("\n" + "=" * 72)
    print(f"{'model':5s} {'lam':>4} {'test_shell':18s} | {'delivery':>9} {'stretch_med':>11}")
    best = 0.0
    for M in ("Heat", "QW"):
        for lam in LAMBDAS:
            for name in sorted({r["test_shell"] for r in rows}):
                rs = [r for r in rows if r["model"] == M and r["lam"] == lam
                      and r["test_shell"] == name]
                if not rs:
                    continue
                dlv = np.mean([r["delivery"] for r in rs])
                st = np.nanmean([r["stretch_med"] for r in rs])
                best = max(best, dlv if st <= 1.10 else 0.0)
                print(f"{M:5s} {lam:>4.1f} {name:18s} | {dlv:>9.3f} {st:>11.3f}")
    print("\nP3b VERDICT")
    print("  Compare lam=0 (pure MSE) vs lam=1 (Bellman) delivery at matched stretch.")
    if best >= 0.95:
        print(f"  => PASS: Bellman-consistent potential routes zero-shot at "
              f"delivery>=0.95, stretch<=1.10. P3 cleared. Build P2 next.")
    else:
        print(f"  => best deliverable={best:.3f}. If Bellman >> MSE but <0.95, add "
              f"bounded-backtrack decode or stronger lambda/anneal.")
    print("=" * 72)


if __name__ == "__main__":
    main()
