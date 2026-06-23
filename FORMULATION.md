# FORMULATION — Quantum-Walk GNN for Proactive LEO Routing

Working title: *Ephemeris-Informed Quantum-Walk Graph Networks for Proactive
and Scale-Invariant Routing in LEO Mega-Constellations.*

Target tier: IEEE Transactions (primary TNSM, stretch TWC). House style: hardened
formulation, deep honest experiments, param-matched ablations, multi-seed.

---

## 1. System model

A LEO constellation is a set of `S` satellites with inter-satellite links (ISLs).
Because orbital motion is deterministic and known from ephemeris (TLE / Walker
parameters), the network topology over a horizon is a **known sequence of graphs**

```
G_t = (V, E_t, W_t),   t = 0, 1, ..., T-1
```

- `V` : satellites (fixed set), |V| = S.
- `E_t` : active ISLs at slot t (in-plane links stable; cross-plane links open and
  close at known times as satellites cross polar/seam regions).
- `W_t` : edge weights = propagation delay (distance / c) plus a congestion term;
  both computable from geometry and a traffic model.

Crucially `{G_t}` for the whole horizon is available **a priori**, not revealed
online. This is the structural fact terrestrial routing GNNs cannot assume and the
lever for *proactive* decisions.

## 2. Task: routing potential field (and next hop)

For a destination `d in V` and slot `t`, define the **routing potential**

```
phi_t^d(v) = shortest-path cost from v to d on (G_t, W_t)
```

The greedy next hop from v is `argmin_{u in N_t(v)} W_t(v,u) + phi_t^d(u)`. Learning
`phi` (a per-node scalar field conditioned on a destination indicator) is therefore
sufficient for routing and is the supervised target. We learn a single inductive
model `f_theta` that maps `(G_t, one-hot(d))` to an estimate `hat phi_t^d`.

Proactive variant: predict `phi_{t+h}^d` from information available at t (the future
topology `G_{t+h}` is known), enabling pre-computation of routes and link
pre-establishment before a handover/seam event.

## 3. Propagation operators (the contribution)

Let `L = I - D^{-1/2} A D^{-1/2}` be the symmetric normalized Laplacian of `G_t`,
with eigendecomposition `L = V diag(lambda) V^T`.

- **Local (GCN baseline):** `P_loc = D^{-1/2}(A+I)D^{-1/2}`. Depth-K stack has a
  K-hop receptive field. Cannot represent `phi` beyond K hops.
- **Classical diffusion (Heat baseline):** `P_heat(t) = exp(-t L) = V e^{-t lambda} V^T`.
  Global but **diffusive**: a point source decays toward the stationary distribution;
  far-field gradient vanishes, so large distances become unresolvable.
- **Quantum walk (ours):** continuous-time quantum walk
  `U(tau) = exp(-i tau L) = V e^{-i tau lambda} V^T`, applied to (complexified) node
  states; the layer emits the amplitude magnitude `|U(tau) H|`. The walk spreads
  **ballistically** (distance ~ tau, vs diffusion's ~ sqrt(tau)) and the phase
  produces interference that preserves distinguishable structure at long range.

A QW-GNN layer (param-matched to the baselines; only the scalar `tau` is extra):

```
H^{(l+1)} = sigma( W^{(l)} * | U(tau_l) H^{(l)} | + b^{(l)} )
```

The decisive isolation is **QW vs Heat**: identical architecture, identical global
reach, identical parameter budget; the sole difference is the imaginary exponent
(ballistic + interfering) vs the real exponent (diffusive + decaying).

Scalability note: `U(tau)` is dense. For deployment we approximate it with a degree-M
Chebyshev expansion in `L` (M localized hops, O(M|E|) cost), recovering a proper
message-passing layer; the exact spectral form is used only for the small-graph
analysis and as the M -> infinity reference.

## 4. Three pillars as falsifiable claims

- **P1 — Ballistic reach.** At matched parameters and depth, QW resolves `phi` at
  long range better than Heat and GCN, and the absolute hop-error gap over Heat
  **grows with graph diameter**.
  *Refutation test:* if QW does not beat Heat on far nodes, or the absolute gap does
  not widen with scale, P1 is dead. **Smoke status: PASSED** (12/12 param-matched
  cells, mean far-node error reduced ~52%, absolute gap slope +0.07 hop/hop on
  synthetic tori). Must replicate on Hypatia.
- **P2 — Proactive gain.** Conditioning on known future topology `G_{t+h}` yields
  lower post-handover delay / loss than a reactive model seeing only `G_t`.
  *Refutation test:* no significant delay/loss reduction across seam events vs
  reactive at matched capacity.
- **P3 — Scale invariance.** A model trained on a small shell generalizes
  zero-shot to a mega-constellation (more planes / satellites-per-plane) better
  than baselines, with the margin tracking the diameter increase.
  *Refutation test:* OOD margin vanishes or QW's inductive transfer is no better
  than GCN/Heat.

## 5. Honest positioning vs prior art

- Quantum-walk neural networks exist in generic ML (Dernbach et al., 2018). We do
  **not** claim to invent QW propagation. Our contribution is (i) adapting it to the
  routing-potential task on **deterministic, ephemeris-known** time-varying LEO
  graphs, (ii) the proactive formulation that exploits future topology, and (iii)
  the scale-invariance result. Positioning will state this explicitly.
- GNN-for-routing and DRL-routing exist; novelty is the operator + the NTN-specific
  proactive/inductive story, validated against those baselines (param-matched).

## 6. Param-matching and verification protocol (non-negotiable)

- Every model: same hidden width, same depth, same readout; report exact param
  counts (smoke: 3265 / 3268 / 3268). Any gap must be attributable to the operator.
- Multi-seed; never report a single-seed win. Stratify error by true distance.
- Controls that must be run on Hypatia before any P1 claim in the paper:
  1. **complex-diffusion control** (global, complex weights, no ballistic phase) to
     rule out "complex capacity" rather than quantum dynamics;
  2. **abs-only control** (Heat followed by `|.|`) to confirm the magnitude
     nonlinearity is inert without complex phase;
  3. **depth-matched-to-diameter GCN** to show QW (shallow) matches deep GCN while
     avoiding over-smoothing.
- Shortcut audit: withhold absolute coordinates; verify the model uses structure,
  not position.
```
```
