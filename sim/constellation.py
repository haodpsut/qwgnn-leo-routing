"""
Walker-delta LEO constellation -> time-varying +Grid ISL graph sequence.

Pure NumPy circular-orbit propagation: no skyfield / ns-3 dependency, so the
whole pipeline is reproducible from parameters alone. Precision is sufficient
for a methods paper because what matters is realistic time-varying topology
(plane structure, polar ISL cutoff, seam) and geometry-driven propagation delay,
not ephemeris-grade positions.

Convention: ECI frame, circular orbits, Earth assumed non-rotating over the short
analysis horizon (the relative geometry that drives ISL delay is captured; an
Earth-rotation term can be added later without changing the interface).
"""

import numpy as np

RE_KM = 6371.0          # Earth radius
MU = 398600.4418        # km^3 / s^2, Earth gravitational parameter
C_KM_S = 299792.458     # speed of light


class Walker:
    """Walker-delta constellation: T sats, P planes, phasing F, inc, altitude."""

    def __init__(self, total, planes, phasing_f, inclination_deg, altitude_km):
        assert total % planes == 0, "total must be divisible by planes"
        self.T = total
        self.P = planes
        self.S = total // planes            # sats per plane
        self.F = phasing_f
        self.inc = np.deg2rad(inclination_deg)
        self.r = RE_KM + altitude_km
        self.n_mean = np.sqrt(MU / self.r ** 3)   # mean motion, rad/s
        self.period_s = 2 * np.pi / self.n_mean
        # static per-sat orbital angles
        p_idx = np.repeat(np.arange(self.P), self.S)          # plane of each sat
        s_idx = np.tile(np.arange(self.S), self.P)            # slot in plane
        self.raan = 2 * np.pi * p_idx / self.P                # ascending node
        self.u0 = (2 * np.pi * s_idx / self.S
                   + 2 * np.pi * self.F * p_idx / self.T)     # init arg of latitude
        self.p_idx = p_idx
        self.s_idx = s_idx

    def positions(self, t_s):
        """ECI positions (T,3) km at time t seconds."""
        u = self.u0 + self.n_mean * t_s                       # arg of latitude(t)
        # position in orbital plane then rotate by inclination and RAAN
        cu, su = np.cos(u), np.sin(u)
        ci, si = np.cos(self.inc), np.sin(self.inc)
        cO, sO = np.cos(self.raan), np.sin(self.raan)
        x = self.r * (cO * cu - sO * su * ci)
        y = self.r * (sO * cu + cO * su * ci)
        z = self.r * (su * si)
        return np.stack([x, y, z], axis=1)

    def latitudes(self, t_s):
        """Geocentric latitude (rad) of each sat at time t (for polar cutoff)."""
        u = self.u0 + self.n_mean * t_s
        return np.arcsin(np.sin(u) * np.sin(self.inc))


def grid_isl_graph(walker: Walker, t_s, polar_cutoff_deg=70.0, seam=True):
    """
    Build the +Grid ISL adjacency at time t.

      - intra-plane: link to s+1 (mod S) in same plane  (always on)
      - inter-plane: link to the geometrically-nearest sat in plane p+1 (mod P)
        unless either endpoint is above the polar cutoff latitude
      - seam=True keeps the wrap-around plane pair (P-1, 0); set False to cut it
        (counter-rotating seam, the usual real-world choice)

    Returns (A, W): A int adjacency (T,T), W delay weights in seconds (T,T).
    """
    T, P, S = walker.T, walker.P, walker.S
    pos = walker.positions(t_s)
    lat = np.abs(walker.latitudes(t_s))
    polar = lat > np.deg2rad(polar_cutoff_deg)

    A = np.zeros((T, T), dtype=np.int64)
    W = np.zeros((T, T), dtype=np.float64)

    def add(i, j):
        d = np.linalg.norm(pos[i] - pos[j]) / C_KM_S
        A[i, j] = A[j, i] = 1
        W[i, j] = W[j, i] = d

    idx = np.arange(T).reshape(P, S)        # idx[p, s] = global sat id

    # intra-plane ring
    for p in range(P):
        for s in range(S):
            add(idx[p, s], idx[p, (s + 1) % S])

    # inter-plane: nearest neighbor in the next plane
    for p in range(P):
        q = (p + 1) % P
        if not seam and q == 0 and p == P - 1:
            continue
        for s in range(S):
            i = idx[p, s]
            if polar[i]:
                continue
            cand = idx[q]                              # all sats in plane q
            # nearest by 3D distance among non-polar candidates
            mask = ~polar[cand]
            if not mask.any():
                continue
            dists = np.linalg.norm(pos[cand] - pos[i], axis=1)
            dists[~mask] = np.inf
            j = cand[int(np.argmin(dists))]
            if A[i, j] == 0:
                add(i, j)
    return A, W


def graph_sequence(walker: Walker, horizon_s, slot_s, **kw):
    """Yield (t, A, W) snapshots over [0, horizon_s) at slot_s spacing."""
    n_slots = int(horizon_s // slot_s)
    for k in range(n_slots):
        t = k * slot_s
        A, W = grid_isl_graph(walker, t, **kw)
        yield t, A, W


# ---- preset shells -------------------------------------------------------
def iridium_like():
    # 66 sats, 6 planes x 11, ~86.4 deg, 780 km  (OOD small shell)
    return Walker(66, 6, 1, 86.4, 780.0)


def starlink_shell1():
    # Starlink shell 1: 1584 sats, 72 planes x 22, 53 deg, 550 km
    return Walker(1584, 72, 1, 53.0, 550.0)


def starlink_mini():
    # smaller 53-deg shell for fast iteration: 264 sats, 24 x 11
    return Walker(264, 24, 1, 53.0, 550.0)


if __name__ == "__main__":
    import networkx as nx

    for name, w in [("iridium66", iridium_like()),
                    ("starlink_mini264", starlink_mini())]:
        A, W = grid_isl_graph(w, 0.0, seam=False)
        G = nx.from_numpy_array(A)
        deg = A.sum(1)
        comp = nx.number_connected_components(G)
        if comp == 1:
            diam = nx.diameter(G)
        else:
            diam = max(nx.diameter(G.subgraph(c))
                       for c in nx.connected_components(G))
        # link churn vs one slot later
        A2, _ = grid_isl_graph(w, 60.0, seam=False)
        churn = int(np.abs(A - A2).sum() // 2)
        print(f"{name:18s} T={w.T:4d} P={w.P:2d} S={w.S:2d} "
              f"period={w.period_s/60:.1f}min | deg[min/mean/max]="
              f"{deg.min()}/{deg.mean():.2f}/{deg.max()} comps={comp} "
              f"diam~{diam} churn@60s={churn} "
              f"delay[ms] max={W.max()*1000:.1f}")
