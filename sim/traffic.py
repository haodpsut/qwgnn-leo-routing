"""
Time-varying traffic + congestion model on the constellation graph.

Purpose: quantify the headroom for congestion-aware routing BEFORE building any
GNN. If routing that ignores load already performs close to load-aware routing,
the whole congestion pivot is dead and no GNN can help. This module provides:

  - gravity demands (population-like weights) with moving hotspots over slots;
  - link loads induced by a set of routed paths;
  - a BPR link cost  cost = prop * (1 + alpha*(load/cap)^beta)  (alpha=0.15, beta=4),
    smooth and monotone with no hard drop, so the user equilibrium is well defined;
  - routing policies: blind, user equilibrium (MSA), and system optimum (marginal
    cost), with a survivorship-free total-travel-time evaluator.

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


def link_marginal_cost(prop_W, load, cap, alpha=0.15, beta=4.0):
    """
    Marginal link cost d/dx[x*cost(x)] for the BPR form, used to route the system
    optimum (where each flow is charged its externality):
        m_uv(x) = prop_uv * (1 + alpha*(beta+1)*(x/cap)^beta).
    """
    util = load / cap
    m = prop_W * (1.0 + alpha * (beta + 1.0) * np.power(util, beta))
    m[prop_W <= 0] = 0.0
    return m


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
    # 'ue' routes on the link cost (user equilibrium); 'so' routes on the marginal
    # cost (system optimum, Frank-Wolfe / MSA). Realized TTT always uses link_cost.
    route_cost_fn = link_marginal_cost if policy == "so" else link_cost

    if policy == "blind":
        paths = _route_on_cost(A, free, demands)
        load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    else:
        # MSA: x_{k+1} = x_k + (1/(k+1)) (aon(cost(x_k)) - x_k)
        paths = _route_on_cost(A, free, demands)
        load = edge_loads([(p, r) for p, r in paths if p is not None], n)
        for k in range(1, iters + 1):
            cost = route_cost_fn(prop_W, load, cap)
            aon = _route_on_cost(A, cost, demands)
            yload = edge_loads([(p, r) for p, r in aon if p is not None], n)
            load = load + (yload - load) / (k + 1)
            paths = aon
        # For equilibria the MSA-averaged load, not a single re-routing, defines the
        # operating point. Measure TTT directly on that load to avoid a path/load
        # mismatch (which can otherwise make SO appear above UE):
        #   TTT = sum_e x_e * cost_e(x_e).
        cost = link_cost(prop_W, load, cap)          # realized (actual) cost
        total = float((load * cost).sum())
        demand_total = sum(r for _, _, r in demands)
        mean = total / demand_total if demand_total > 0 else float("nan")
        return {"total_ttt": total, "mean_delay": mean,
                "max_util": float((load / cap).max()), "unmet": 0}

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


def multipath_route(A, prop_W, route_cost, demands, cap, tau=0.25):
    """
    One-shot MULTIPATH decode of a cost field (flow-splitting), to match the
    multi-path nature of the user equilibrium that a single shortest path cannot.

    For each destination we compute the cost-to-go under route_cost (one Dijkstra),
    then push each demand's rate downhill, splitting at every node across the
    distance-decreasing out-edges with a softmin weight exp(-slack/(tau*scale)),
    where slack = c(u,v)+d(v)-d(u) >= 0 is how far an edge is from being on a
    shortest path (slack 0 on the steepest path). tau -> 0 recovers single path;
    larger tau spreads load. The downhill edges form a DAG, so flow is loop free and
    computed in one decreasing-distance sweep. Cost is one Dijkstra per destination,
    the same class as the single-path decode, not the T-iteration equilibrium solve.
    """
    n = A.shape[0]
    G = nx.DiGraph()
    rows, cols = np.nonzero(A)
    for a, b in zip(rows.tolist(), cols.tolist()):
        G.add_edge(a, b, weight=float(route_cost[a, b]))
    Grev = G.reverse(copy=False)
    scale = float(route_cost[rows, cols].mean()) + 1e-9

    by_dst = {}
    for s, d, r in demands:
        by_dst.setdefault(int(d), []).append((int(s), r))

    load = np.zeros((n, n))
    for d, srcs in by_dst.items():
        dist = nx.single_source_dijkstra_path_length(Grev, d, weight="weight")
        inflow = np.zeros(n)
        for s, r in srcs:
            if s in dist:
                inflow[s] += r
        order = sorted((u for u in dist if u != d), key=lambda u: -dist[u])
        for u in order:
            f = inflow[u]
            if f <= 0:
                continue
            nbrs = [v for v in G.successors(u) if v in dist and dist[v] < dist[u]]
            if not nbrs:
                continue
            slack = np.array([route_cost[u, v] + dist[v] - dist[u] for v in nbrs])
            w = np.exp(-slack / (tau * scale))
            w /= w.sum()
            for v, wi in zip(nbrs, w):
                load[u, v] += f * wi
                inflow[v] += f * wi
    cost = link_cost(prop_W, load, cap)
    total = float((load * cost).sum())
    dem_total = sum(r for _, _, r in demands)
    return {"total_ttt": total, "mean_delay": total / dem_total if dem_total else float("nan"),
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


def measure_paths(prop_W, cap, demands, paths):
    """Realized TTT/mean-delay for externally supplied paths (e.g. geographic)."""
    n = prop_W.shape[0]
    load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    total, mean = _realized(prop_W, load, cap, demands, paths)
    unmet = sum(1 for p, _ in paths if p is None)
    return {"total_ttt": total, "mean_delay": mean,
            "max_util": float((load / cap).max()), "unmet": unmet}


def geographic_paths(A, pos, demands, prop_W, max_steps=None):
    """
    Greedy next-hop by reducing 3D distance to the destination (congestion-blind),
    with a free-flow shortest-path FALLBACK for flows that get stuck in a local
    minimum. The fallback guarantees delivery so the realized TTT is survivorship-
    free (no silently dropped flows inflating the metric).
    """
    n = A.shape[0]
    if max_steps is None:
        max_steps = 4 * n
    nbrs = [np.nonzero(A[i] > 0)[0] for i in range(n)]
    paths, stuck = [], []
    for k, (s, d, r) in enumerate(demands):
        cur, seen, path = s, {s}, [s]
        ok = True
        for _ in range(max_steps):
            if cur == d:
                break
            cand = nbrs[cur]
            dist = np.linalg.norm(pos[cand] - pos[d], axis=1)
            nxt = int(cand[int(np.argmin(dist))])
            if nxt in seen:
                ok = False
                break
            seen.add(nxt)
            path.append(nxt)
            cur = nxt
        if ok and cur == d:
            paths.append((path, r))
        else:
            paths.append(None)               # placeholder, fill via fallback
            stuck.append((k, (s, d, r)))
    if stuck:
        free = link_cost(prop_W, np.zeros_like(prop_W), 1.0)
        fb = _route_on_cost(A, free, [sd for _, sd in stuck])
        for (k, _), p in zip(stuck, fb):
            paths[k] = p
    return paths, len(stuck)


def demand_node_features(demands, n):
    """Per-node [outgoing rate, incoming rate] -- the observable traffic intensity."""
    out = np.zeros(n)
    inc = np.zeros(n)
    for s, d, r in demands:
        out[s] += r
        inc[d] += r
    return np.stack([out, inc], axis=1)        # (n, 2)
