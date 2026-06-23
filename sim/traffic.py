"""
Time-varying traffic + congestion model on the constellation graph.

Purpose: quantify the headroom for congestion-aware routing BEFORE building any
GNN. If routing that ignores load already performs close to load-aware routing,
the whole congestion pivot is dead and no GNN can help. This module provides:

  - gravity demands (population-like weights) with moving hotspots over slots;
  - link loads induced by a set of routed paths;
  - an M/M/1 link cost  cost = prop_delay + base_q * util/(1-util)  (util=load/cap),
    which blows up convexly near capacity and drops traffic above capacity;
  - routing policies (load-blind vs load-aware equilibrium) and a realized-delay /
    drop-rate evaluator.

Everything is pure numpy + networkx, deterministic from a seed.
"""

import networkx as nx
import numpy as np

BIG = 1e9


def gravity_demands(pos, n_pairs, rng, hotspot_shift=0):
    """
    Sample n_pairs (src, dst, rate). Hotspots are nodes near a moving longitude
    band (proxy for the sub-solar / dense-population region rotating under the
    constellation); hotspot_shift rotates that band between slots, so congestion
    is predictable but non-stationary.
    """
    n = pos.shape[0]
    lon = np.arctan2(pos[:, 1], pos[:, 0])                  # node "longitude"
    band = (lon + hotspot_shift) % (2 * np.pi)
    weight = np.exp(2.0 * np.cos(band))                     # peaked around band=0
    weight = weight / weight.sum()
    src = rng.choice(n, size=n_pairs, p=weight)
    dst = rng.choice(n, size=n_pairs, p=weight)
    keep = src != dst
    src, dst = src[keep], dst[keep]
    rate = rng.uniform(0.5, 1.5, size=len(src))
    return list(zip(src.tolist(), dst.tolist(), rate.tolist()))


def edge_loads(paths, n):
    """Accumulate directed-edge load from a list of (path_nodes, rate)."""
    load = np.zeros((n, n))
    for nodes, rate in paths:
        for a, b in zip(nodes[:-1], nodes[1:]):
            load[a, b] += rate
    return load


def link_cost(prop_W, load, cap, alpha=0.15, beta=4.0):
    """
    BPR congestion cost (standard traffic assignment, no hard drop):
        cost_ij(load) = prop_ij * (1 + alpha * (load/cap)^beta).
    Smooth and monotone, so user-equilibrium is well defined and MSA converges.
    """
    util = load / cap
    cost = prop_W * (1.0 + alpha * np.power(util, beta))
    cost[prop_W <= 0] = 0.0
    return cost


def _route_on_cost(A, cost, demands):
    """Shortest path per demand on a given cost matrix. Returns list of (nodes,rate)."""
    n = A.shape[0]
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    rows, cols = np.nonzero(A)
    for a, b in zip(rows.tolist(), cols.tolist()):
        G.add_edge(a, b, weight=float(cost[a, b]))
    paths = []
    for s, d, r in demands:
        try:
            paths.append((nx.shortest_path(G, s, d, weight="weight"), r))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            paths.append((None, r))
    return paths


def _realized(prop_W, load, cap, demands, paths):
    """Total and mean realized travel time of paths under the induced load."""
    real = link_cost(prop_W, load, cap)
    total, per = 0.0, []
    for p, r in paths:
        if p is None:
            continue
        d = sum(real[a, b] for a, b in zip(p[:-1], p[1:]))
        total += r * d
        per.append(d)
    return total, (float(np.mean(per)) if per else float("nan"))


def evaluate(A, prop_W, demands, cap, policy="blind", iters=20):
    """
    policy='blind' : all-or-nothing on free-flow (propagation) cost, congestion-blind.
    policy='ue'    : user-equilibrium via MSA on BPR cost (congestion-aware optimum).

    No hard drops (BPR), so every demand is delivered; metrics are survivorship-free.
    Returns dict: total_ttt, mean_delay, max_util, unmet (unroutable pairs).
    """
    n = A.shape[0]
    free = link_cost(prop_W, np.zeros_like(prop_W), cap)

    if policy == "blind":
        paths = _route_on_cost(A, free, demands)
        load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    else:
        # MSA: x_{k+1} = x_k + (1/(k+1)) (aon(cost(x_k)) - x_k)
        paths = _route_on_cost(A, free, demands)
        load = edge_loads([(p, r) for p, r in paths if p is not None], n)
        for k in range(1, iters + 1):
            cost = link_cost(prop_W, load, cap)
            aon = _route_on_cost(A, cost, demands)
            yload = edge_loads([(p, r) for p, r in aon if p is not None], n)
            load = load + (yload - load) / (k + 1)
            paths = aon
        # final paths consistent with the equilibrium load
        paths = _route_on_cost(A, link_cost(prop_W, load, cap), demands)
        load = edge_loads([(p, r) for p, r in paths if p is not None], n)

    total, mean = _realized(prop_W, load, cap, demands, paths)
    unmet = sum(1 for p, _ in paths if p is None)
    return {"total_ttt": total, "mean_delay": mean,
            "max_util": float((load / cap).max()), "unmet": unmet}


def ue_loads(A, prop_W, demands, cap, iters=20):
    """Equilibrium edge-load matrix and congestion multiplier g = cost/prop - 1."""
    n = A.shape[0]
    free = link_cost(prop_W, np.zeros_like(prop_W), cap)
    paths = _route_on_cost(A, free, demands)
    load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    for k in range(1, iters + 1):
        cost = link_cost(prop_W, load, cap)
        aon = _route_on_cost(A, cost, demands)
        yload = edge_loads([(p, r) for p, r in aon if p is not None], n)
        load = load + (yload - load) / (k + 1)
    cost = link_cost(prop_W, load, cap)
    g = np.zeros_like(prop_W)
    m = prop_W > 0
    g[m] = cost[m] / prop_W[m] - 1.0          # >= 0, the UE congestion price
    return load, g


def route_and_measure(A, prop_W, demands, cap, route_cost):
    """Route every demand on route_cost, then measure realized TTT under BPR."""
    n = A.shape[0]
    paths = _route_on_cost(A, route_cost, demands)
    load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    total, mean = _realized(prop_W, load, cap, demands, paths)
    return {"total_ttt": total, "mean_delay": mean,
            "max_util": float((load / cap).max())}


def blind_loads(A, prop_W, demands):
    """Edge load if every demand takes the free-flow (propagation) shortest path.

    One all-or-nothing pass: cheap (no equilibration). This first-pass load is the
    single most informative input for predicting the equilibrium congestion price,
    and is exactly what the GNN is meant to correct in one shot instead of MSA.
    """
    n = A.shape[0]
    free = link_cost(prop_W, np.zeros_like(prop_W), 1.0)   # cap irrelevant at zero load
    paths = _route_on_cost(A, free, demands)
    return edge_loads([(p, r) for p, r in paths if p is not None], n)


def demand_node_features(demands, n):
    """Per-node [outgoing rate, incoming rate] -- the observable traffic intensity."""
    out = np.zeros(n)
    inc = np.zeros(n)
    for s, d, r in demands:
        out[s] += r
        inc[d] += r
    return np.stack([out, inc], axis=1)        # (n, 2)
