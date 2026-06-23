"""
P5 (core contribution): a GNN that AMORTIZES congestion-aware traffic engineering.

P4 showed load-blind shortest-path wastes tens of % of travel time by piling onto
bottleneck ISLs, and user-equilibrium (UE) routing recovers it -- but UE needs the
full demand matrix and an iterative MSA solve every slot, which does not scale to
1584+ satellites under fast topology change.

Idea: train a GNN to predict, in ONE forward pass, the UE congestion price on each
ISL from observable per-node traffic intensity. Route every demand on
cost = prop * (1 + g_hat). This skips the iteration, generalizes inductively to
larger shells, and (later) can be made proactive by feeding predicted near-future
demand. Here we test whether it recovers the blind->UE gain, in-distribution and
zero-shot to a larger shell, comparing GCN / Heat / QW propagation.

Metric: recovered fraction = (blind_ttt - gnn_ttt) / (blind_ttt - ue_ttt).
  1.0 = matches the UE optimum,  0.0 = no better than blind.
"""

import csv
import os
import sys

import numpy as np
import torch
import torch.nn as nn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "smoke"))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from models import build_ctx                                   # smoke/ (ctx + ops)
from constellation import Walker, grid_isl_graph              # sim/
from traffic import (gravity_demands, ue_loads, route_and_measure,
                     evaluate, demand_node_features, blind_loads)

DEPTH = 3
HIDDEN = 32
EPOCHS = 300
LR = 5e-3


# ---- propagation operators (param-light, same as the smoke study) ----------
def prop_gcn(H, ctx, t):
    return torch.einsum("nm,md->nd", ctx["A_hat"], H)


def prop_heat(H, ctx, t):
    filt = torch.exp(-t * ctx["evals"])
    V = ctx["evecs"]
    return V @ (filt.unsqueeze(1) * (V.T @ H))


def prop_qw(H, ctx, t):
    phase = torch.exp(-1j * t * ctx["evals"].to(torch.complex128))
    V = ctx["evecs"].to(torch.complex128)
    out = V @ (phase.unsqueeze(1) * (V.conj().T @ H.to(torch.complex128)))
    return out.abs()


PROPS = {"GCN": prop_gcn, "Heat": prop_heat, "QW": prop_qw}


class EdgePriceGNN(nn.Module):
    """Node-feature -> per-edge UE congestion price (predicts log1p(g))."""

    def __init__(self, prop_name, hidden=HIDDEN, layers=DEPTH, in_dim=4):
        super().__init__()
        self.prop = PROPS[prop_name]
        self.layers = layers
        self.inp = nn.Linear(in_dim, hidden).double()
        self.mix = nn.ModuleList([nn.Linear(hidden, hidden).double()
                                  for _ in range(layers)])
        self.t = nn.Parameter(torch.ones(layers, dtype=torch.float64))
        # edge readout: [h_u, h_v, prop_uv, blind_load_uv] -> scalar
        self.edge = nn.Sequential(
            nn.Linear(2 * hidden + 2, hidden).double(), nn.ReLU(),
            nn.Linear(hidden, 1).double())
        self.act = nn.ReLU()

    def forward(self, X, ctx):
        H = self.act(self.inp(X))
        for li in range(self.layers):
            tl = torch.nn.functional.softplus(self.t[li]) + 1e-3
            H = self.act(self.mix[li](self.prop(H, ctx, tl)))
        src, dst = ctx["eidx"]                          # (E,)
        feat = torch.cat([H[src], H[dst],
                          ctx["eprop"].unsqueeze(1), ctx["eload"].unsqueeze(1)], dim=1)
        return self.edge(feat).squeeze(-1)              # (E,) = log1p(g) prediction


# ---- instance construction -------------------------------------------------
def make_instance(walker, npairs, seed):
    A_np, W_np = grid_isl_graph(walker, 0.0, seam=False)
    n = A_np.shape[0]
    rng = np.random.default_rng(seed)
    pos = walker.positions(0.0)
    dem = gravity_demands(pos, npairs, rng)
    cap = CAP
    _, g_star = ue_loads(A_np, W_np, dem, cap)          # target multiplier
    bload = blind_loads(A_np, W_np, dem)                # cheap first-pass load

    def _norm(col):
        return col / (col.mean() + 1e-9)
    odf = demand_node_features(dem, n)                  # (n,2) out/in demand
    node_out_load = bload.sum(1)                        # blind load leaving node
    node_in_load = bload.sum(0)                         # blind load entering node
    Xnp = np.stack([_norm(odf[:, 0]), _norm(odf[:, 1]),
                    _norm(node_out_load), _norm(node_in_load)], axis=1)
    A = torch.from_numpy(A_np.astype(np.float64))
    ctx = build_ctx(A)
    rows, cols = np.nonzero(A_np)
    ctx["eidx"] = (torch.from_numpy(rows), torch.from_numpy(cols))
    ctx["eprop"] = torch.from_numpy(W_np[rows, cols] / (W_np[rows, cols].mean() + 1e-9))
    el = bload[rows, cols]
    ctx["eload"] = torch.from_numpy(el / (el.mean() + 1e-9))
    return {
        "A_np": A_np, "W_np": W_np, "dem": dem, "cap": cap, "n": n,
        "X": torch.from_numpy(Xnp), "ctx": ctx,
        "g_star": torch.from_numpy(g_star[rows, cols]),  # (E,)
        "tgt": torch.from_numpy(np.log1p(g_star[rows, cols])),
        "rows": rows, "cols": cols,
    }


def train(prop_name, train_insts, seed):
    torch.manual_seed(seed)
    model = EdgePriceGNN(prop_name)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    mse = nn.MSELoss()
    for _ in range(EPOCHS):
        opt.zero_grad()
        loss = 0.0
        for ins in train_insts:
            pred = model(ins["X"], ins["ctx"])
            loss = loss + mse(pred, ins["tgt"])
        loss.backward()
        opt.step()
    return model


def eval_instance(model, ins):
    with torch.no_grad():
        g_pred = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()
    A_np, W_np, dem, cap = ins["A_np"], ins["W_np"], ins["dem"], ins["cap"]
    route_cost = W_np.copy()
    route_cost[ins["rows"], ins["cols"]] = W_np[ins["rows"], ins["cols"]] * (1 + g_pred)
    gnn = route_and_measure(A_np, W_np, dem, cap, route_cost)
    blind = route_and_measure(A_np, W_np, dem, cap, W_np)
    ue = evaluate(A_np, W_np, dem, cap, policy="ue")
    denom = blind["total_ttt"] - ue["total_ttt"]
    rec = (blind["total_ttt"] - gnn["total_ttt"]) / denom if denom > 1e-9 else float("nan")
    return {"blind": blind["total_ttt"], "ue": ue["total_ttt"],
            "gnn": gnn["total_ttt"], "recovered": rec}


# ---- experiment ------------------------------------------------------------
CAP = 20.0
TRAIN_WALKER = Walker(132, 12, 1, 53.0, 550.0)
TRAIN_PAIRS = 600
OOD_WALKER = Walker(264, 24, 1, 53.0, 550.0)
OOD_PAIRS = 1200
if os.environ.get("QWGNN_FULL") == "1":
    OOD_WALKER = Walker(1584, 72, 1, 53.0, 550.0)
    OOD_PAIRS = 7200
SEEDS = [0, 1, 2]
N_TRAIN_INST = 10
N_EVAL_INST = 4
OUT = os.path.join(ROOT, "results", "p5_router.csv")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    print(f"train: Walker132 @ {TRAIN_PAIRS} pairs   OOD: larger shell @ {OOD_PAIRS}")
    print(f"{N_TRAIN_INST} train insts, {N_EVAL_INST} eval insts/split, {len(SEEDS)} seeds\n")
    for seed in SEEDS:
        train_insts = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 100 + seed * 50 + i)
                       for i in range(N_TRAIN_INST)]
        indist = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 900 + seed * 10 + i)
                  for i in range(N_EVAL_INST)]
        ood = [make_instance(OOD_WALKER, OOD_PAIRS, 700 + seed * 10 + i)
               for i in range(N_EVAL_INST)]
        for prop_name in PROPS:
            model = train(prop_name, train_insts, seed)
            for split, insts in [("in-dist", indist), ("ood-largeshell", ood)]:
                for j, ins in enumerate(insts):
                    r = eval_instance(model, ins)
                    rows.append({"prop": prop_name, "seed": seed, "split": split,
                                 "inst": j, **r})
            for split in ("in-dist", "ood-largeshell"):
                rs = [r for r in rows if r["prop"] == prop_name and r["seed"] == seed
                      and r["split"] == split]
                recs = 100 * np.array([r["recovered"] for r in rs])
                print(f"{prop_name:5s} seed{seed} {split:14s} | "
                      f"recovered {recs.mean():>6.1f}% +/- {recs.std():>4.1f}")
    with open(OUT, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    verdict(rows)


def verdict(rows):
    print("\n" + "=" * 72)
    print(f"{'prop':5s} {'split':14s} | {'recovered% mean +/- std (n)':>30}")
    best = {}
    for prop_name in PROPS:
        for split in ("in-dist", "ood-largeshell"):
            rs = [r for r in rows if r["prop"] == prop_name and r["split"] == split]
            recs = 100 * np.array([r["recovered"] for r in rs])
            best[(prop_name, split)] = (float(recs.mean()), float(recs.std()), len(recs))
            print(f"{prop_name:5s} {split:14s} | "
                  f"{recs.mean():>10.1f}% +/- {recs.std():>4.1f}  (n={len(recs)})")
    print("\nP5 VERDICT")
    ood = {p: best[(p, "ood-largeshell")] for p in PROPS}
    bp = max(ood, key=lambda p: ood[p][0])
    m, s, n = ood[bp]
    solid = m - s >= 40.0           # mean minus one std clears a meaningful bar
    if m >= 50.0 and solid:
        print(f"  => PASS (solid): {bp} recovers {m:.0f}% +/-{s:.0f} of the blind->UE")
        print(f"     gain ZERO-SHOT on a larger shell, one forward pass, low variance.")
        print("     Next: proactive (predicted demand) + baselines + paper.")
    elif m >= 50.0:
        print(f"  => PASS (noisy): {bp} mean {m:.0f}% but std {s:.0f}; tighten variance")
        print("     (more instances / features) before the final claim.")
    else:
        print(f"  => best OOD {bp} {m:.0f}% (<50%). Strengthen features/model.")
    print("=" * 72)


if __name__ == "__main__":
    main()
