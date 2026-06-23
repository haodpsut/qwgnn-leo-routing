# FORMULATION — Inductive GNN for Amortized Congestion-Aware LEO Routing

Working title: *Learning to Route Under Load: an Inductive Graph Network that
Amortizes Congestion-Aware Traffic Engineering for LEO Mega-Constellations.*

Target: IEEE TNSM (stretch TWC). House style: hardened formulation, deep honest
experiments, param-matched ablations, multi-seed with error bars.

> Framing note (2026-06-23): this project began as a quantum-walk GNN for static
> routing. The kill-gates refuted that line (see sec 6). The evidenced contribution
> is the one below: a plain GNN that predicts congestion-aware routing in one
> forward pass. The quantum-walk operator is kept only as a reported negative
> ablation.

---

## 1. System model

LEO constellation = `S` satellites with +Grid ISLs; topology over a horizon is a
known sequence of graphs `G_t=(V,E_t)` from ephemeris (Walker parameters). Each ISL
`(u,v)` has a propagation delay `prop_{uv}` (distance / c) and a finite capacity
`cap`. A traffic demand set `D_t = {(s,d,r)}` (gravity model with population-like,
time-shifting hotspots) loads the network.

Link cost under load follows the standard BPR function:
```
cost_{uv}(x) = prop_{uv} * (1 + alpha * (x_{uv}/cap)^beta),   alpha=0.15, beta=4
```
where `x_{uv}` is the load on the link. Routing all demands induces loads, which
change costs: the consistent operating point is the user equilibrium (UE).

## 2. The problem: amortize traffic engineering

Two reference policies bound the design:
- **Blind shortest-path** (route on `prop` only): cheap (one all-or-nothing pass)
  but congestion-blind; it concentrates traffic on bottleneck ISLs while alternates
  idle. Wastes 8/50/80/90% of total travel time as load grows (measured, sec 6).
- **User equilibrium** (UE, via MSA iteration on BPR cost): the congestion-aware
  optimum, but needs the full demand matrix and many shortest-path rounds per slot,
  which does not scale to 1584+ satellites under fast topology change.

Goal: a model `f_theta` that maps the cheap, observable state to the congestion-
aware routing in ONE forward pass, generalizing across constellation scale.

Target: the UE congestion price `g*_{uv} = cost^{UE}_{uv}/prop_{uv} - 1`. The GNN
predicts `g_hat`; we route every demand on `prop*(1+g_hat)`. Inputs are cheap and
observable: per-node `[out-demand, in-demand]` plus the **blind first-pass load**
(node and edge level). The blind load is the single most informative feature -- the
GNN learns to turn a one-pass load snapshot into the equilibrium prices, replacing
the MSA iteration.

## 3. Model

`EdgePriceGNN`: node features -> K message-passing layers -> per-edge readout
`g_hat_{uv} = softplus(MLP([h_u, h_v, prop_{uv}, blindload_{uv}]))`, trained by
regression to `log1p(g*)` pooled over many (shell, demand) instances. The
propagation operator is a plain normalized-adjacency GCN; this is the operator
choice the evidence selected (sec 6).

## 4. Claims (falsifiable)

- **C1 — Amortization quality.** One forward pass recovers most of the blind->UE
  travel-time gain. *Status: PASS* -- in-distribution ~94-103% (matches/beats UE,
  legitimate since UE != system-optimal), see sec 6.
- **C2 — Inductive scale generalization.** A model trained on small shells recovers
  the gain ZERO-SHOT on a larger shell. *Status: PASS* -- GCN 88+/-17% recovered on
  a 2x shell, one forward pass. Confirm on the 1584 shell (server).
- **C3 — Cheap inference.** GNN one-shot inference is far cheaper than MSA's
  iterated all-pairs routing, and the gap grows with constellation size. *Status:
  TO MEASURE* (next: wall-clock GNN vs MSA across shell sizes).
- **C4 — Proactive gain.** Feeding predicted near-future demand (known topology +
  drifting hotspots) lets the router pre-empt congestion vs a reactive (lag-1)
  router. *Status: TO BUILD.*

Baselines to add: reactive-congestion shortest-path (route on previous slot's
load), geographic greedy, oblivious/ECMP-style; references blind (effort floor) and
UE / system-optimal (quality ceiling).

## 5. Verification protocol (non-negotiable)

- Param-matched operator ablation (GCN vs Heat vs QW), multi-seed, multi-instance,
  report mean +/- std. No single-seed/single-instance claims.
- Recovered fraction = `(blind_ttt - gnn_ttt)/(blind_ttt - ue_ttt)`; also report
  raw TTT and per-demand mean delay.
- Inference-time measured as wall-clock and as shortest-path-call count.
- Shortcut audit: scale-normalize features; confirm the model uses load+structure,
  not absolute coordinates.

## 6. What the kill-gates showed (honest record)

- **Static routing (potential regression).** QW propagation beat classical
  diffusion on far-node potential, but the "advantage grows with diameter" claim was
  a smoke-normalization artifact and FAILED on real topology. Inductive greedy
  delivery stalled (~0.67) on local minima; a Bellman-consistency loss did not fix
  it. Conclusion: on STATIC delay-only LEO, Dijkstra/geographic already route well,
  so a GNN has no real job. (experiments/p1, p3, p3b.)
- **Congestion headroom (no GNN).** With BPR + UE(MSA) + total-travel-time, blind
  shortest-path wastes 8/50/80/90% of TTT as load grows (0% at light load). Genuine,
  load-induced headroom -> the congestion task is where a GNN belongs. (p4.)
- **The router (core).** A one-shot GNN with blind-load features recovers ~88% of
  that gain zero-shot on a larger shell. (p5.)
- **Operator choice.** Once load features are present, predicting the price is
  largely LOCAL, so a plain GCN wins; the global quantum-walk operator gives no
  benefit and higher variance. Quantum is dropped from the contribution and reported
  as a negative ablation. (p5 hardened.)
- **Verdict hygiene.** Automated pass/fail printouts were wrong three times
  (relative-% slope; overload survivorship; filtering on blind max-util). Every
  metric is sanity-checked by hand; printed verdicts are not trusted blindly.
