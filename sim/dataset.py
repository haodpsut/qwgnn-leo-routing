"""
Turn a constellation snapshot into a routing-potential regression dataset.

For a given shell and time slot we build, for several destinations d:
  input  X[d] : one-hot destination indicator on the nodes (no coordinates)
  target Y[d] : normalized weighted shortest-path delay from each node to d
  Dhop[d]     : raw hop distance to d (for stratified far-node evaluation)

The GNN operators propagate on the UNWEIGHTED structure (0/1 adjacency); only the
regression target uses the delay weights. This keeps the operator comparison
identical in spirit to the synthetic smoke while the label is the real, delay-
weighted routing potential the network would actually descend.
"""

import networkx as nx
import numpy as np
import torch

from constellation import grid_isl_graph


def build_routing_dataset(walker, t_s, n_dest, seed, seam=False):
    A_np, W_np = grid_isl_graph(walker, t_s, seam=seam)
    n = A_np.shape[0]
    G = nx.from_numpy_array(A_np)                 # unweighted, for hop distance
    Gw = nx.from_numpy_array(W_np)                # weighted, for delay potential
    for u, v, dd in Gw.edges(data=True):
        dd["weight"] = W_np[u, v]

    # keep the largest connected component if a snapshot fragments
    if nx.number_connected_components(G) > 1:
        comp = max(nx.connected_components(G), key=len)
        nodes = sorted(comp)
        remap = {old: i for i, old in enumerate(nodes)}
        A_np = A_np[np.ix_(nodes, nodes)]
        W_np = W_np[np.ix_(nodes, nodes)]
        n = len(nodes)
        G = nx.from_numpy_array(A_np)
        Gw = nx.from_numpy_array(W_np)
        for u, v, dd in Gw.edges(data=True):
            dd["weight"] = W_np[u, v]

    diameter = nx.diameter(G)
    rng = np.random.default_rng(seed)
    dests = rng.choice(n, size=min(n_dest, n), replace=False)

    X = torch.zeros((len(dests), n, 1), dtype=torch.float64)
    Y = torch.zeros((len(dests), n), dtype=torch.float64)
    Dhop = torch.zeros((len(dests), n), dtype=torch.float64)
    ecc = torch.zeros(len(dests), dtype=torch.float64)        # per-dest delay scale
    for k, d in enumerate(dests):
        hop = nx.single_source_shortest_path_length(G, int(d))
        delay = nx.single_source_dijkstra_path_length(Gw, int(d), weight="weight")
        hv = np.array([hop[i] for i in range(n)], dtype=np.float64)
        dv = np.array([delay[i] for i in range(n)], dtype=np.float64)
        scale = max(dv.max(), 1e-9)
        X[k, d, 0] = 1.0
        Dhop[k] = torch.from_numpy(hv)
        Y[k] = torch.from_numpy(dv / scale)                   # normalized potential
        ecc[k] = scale
    A = torch.from_numpy(A_np.astype(np.float64))
    W = torch.from_numpy(W_np.astype(np.float64))
    return {"A": A, "W": W, "X": X, "Y": Y, "Dhop": Dhop, "ecc": ecc,
            "dests": torch.tensor(dests),
            "diameter": int(diameter), "n": n,
            "delay_scale": float(W_np.max())}


if __name__ == "__main__":
    from constellation import iridium_like, starlink_mini
    for name, w in [("iridium66", iridium_like()),
                    ("starlink_mini264", starlink_mini())]:
        ds = build_routing_dataset(w, 0.0, n_dest=8, seed=0)
        print(f"{name}: n={ds['n']} diam={ds['diameter']} "
              f"dests={ds['X'].shape[0]} "
              f"Y[min/max]={ds['Y'].min():.2f}/{ds['Y'].max():.2f} "
              f"far(hop>3) frac={float((ds['Dhop']>3).float().mean()):.2f}")
