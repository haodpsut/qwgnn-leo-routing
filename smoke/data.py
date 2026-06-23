"""
Synthetic LEO +Grid (Manhattan/torus) constellations and the distributed
routing-potential regression task used to probe long-range propagation.

A LEO walker constellation with inter-satellite links forms a 2D torus grid:
each satellite links to 2 in-plane neighbors (up/down) and 2 cross-plane
neighbors (left/right). Graph diameter scales with the grid side length, which
is exactly the knob we need to test whether an operator's effective receptive
field keeps up with constellation scale.

Task: given a one-hot destination indicator on the nodes (and NO coordinates,
so the model cannot shortcut via absolute position), predict each node's
shortest-path hop distance to the destination, normalized by the diameter.
This scalar field IS the routing potential: greedy descent on it yields the
next hop. Resolving it at large distance requires genuine long-range reach.
"""

import networkx as nx
import numpy as np
import torch


def make_torus(side: int):
    """Return (A, G, coords) for a side x side 4-regular torus grid."""
    G = nx.grid_2d_graph(side, side, periodic=True)
    nodes = sorted(G.nodes())
    idx = {nd: i for i, nd in enumerate(nodes)}
    n = len(nodes)
    A = torch.zeros((n, n), dtype=torch.float64)
    for u, v in G.edges():
        A[idx[u], idx[v]] = 1.0
        A[idx[v], idx[u]] = 1.0
    coords = np.array(nodes, dtype=np.int64)  # (n, 2), only for labeling/debug
    # relabel G with integer ids so BFS distances align with A indexing
    Gi = nx.relabel_nodes(G, idx)
    return A, Gi, coords


def all_pairs_dist(Gi, n: int) -> np.ndarray:
    """Unweighted shortest-path hop distance matrix (n x n)."""
    D = np.zeros((n, n), dtype=np.float64)
    for src, dist in nx.all_pairs_shortest_path_length(Gi):
        for dst, d in dist.items():
            D[src, dst] = d
    return D


def make_samples(side: int, n_dest: int, rng: np.random.Generator):
    """
    Build a routing dataset for one torus.

    Returns dict with:
      A        : (n,n) adjacency (float64 torch)
      X        : (n_dest, n, 1) one-hot destination indicators
      Y        : (n_dest, n) normalized hop distance (target potential)
      Dhop     : (n_dest, n) raw integer hop distance (for stratified eval)
      diameter : int
    """
    A, Gi, _ = make_torus(side)
    n = A.shape[0]
    Dmat = all_pairs_dist(Gi, n)
    diameter = int(Dmat.max())

    dests = rng.choice(n, size=min(n_dest, n), replace=False)
    X = torch.zeros((len(dests), n, 1), dtype=torch.float64)
    Y = torch.zeros((len(dests), n), dtype=torch.float64)
    Dhop = torch.zeros((len(dests), n), dtype=torch.float64)
    for k, d in enumerate(dests):
        X[k, d, 0] = 1.0
        Dhop[k] = torch.from_numpy(Dmat[d])
        Y[k] = torch.from_numpy(Dmat[d] / max(diameter, 1))
    return {"A": A, "X": X, "Y": Y, "Dhop": Dhop, "diameter": diameter, "n": n}
