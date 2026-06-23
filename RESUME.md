# RESUME — where we are and what's next

Repo: github.com/haodpsut/qwgnn-leo-routing  (run on the RTX 4090 server,
conda env `qwgnn`, tmux). Paper target: IEEE TNSM (stretch TWC).

## One-line status
The paper has PIVOTED from "quantum-walk operator for static LEO routing" to
**a GNN that amortizes congestion-aware traffic engineering on LEO**. The pivot's
headroom is confirmed; the core experiment (P5) was running when we paused.

## Why the pivot (the honest story so far)
- P0 smoke (synthetic torus): QW propagation beat classical diffusion, and the
  advantage looked like it grew with diameter.
- P1 (real LEO topology): QW still wins 9/9 param-matched but the **scaling claim
  FAILED** — the "grows with diameter" signal was a smoke-normalization artifact.
- P3 / P3b (inductive static routing): the learned potential transfers in shape
  (stretch ~1.03) but greedy delivery stalls ~0.67 on local minima; a Bellman-
  consistency loss did NOT fix it.
- Meta-insight: on STATIC delay-only LEO, Dijkstra/geographic routing already win,
  so a GNN has no real job there. A GNN earns its place only where shortest-path is
  blind: **congestion / traffic-aware routing.**
- P4 headroom (no GNN): with a proper BPR + user-equilibrium (MSA) model and a
  total-travel-time metric, load-blind shortest-path wastes **8% / 50% / 80% / 90%**
  of travel time as load grows (0% at light load). Genuine, load-induced headroom.
  Pivot CONFIRMED alive.

QW is now a SUPPORTING ablation (a consistent ~20% far-node edge), not the headline.

## What P5 is (the core contribution under test)
`experiments/p5_gnn_router.py`: a GNN predicts, in ONE forward pass, the UE
congestion price `g_e` on each ISL from observable per-node traffic intensity;
route all demands on `cost = prop*(1+g_hat)`. Compares GCN/Heat/QW propagation,
in-distribution and ZERO-SHOT to a larger shell. Metric:
`recovered = (blind_ttt - gnn_ttt)/(blind_ttt - ue_ttt)` (1.0 = matches UE).

## NEXT STEP ON RESUME (do this first)
1. Re-run P5 (it was mid-run at pause; nothing was committed from its output):
   ```
   cd qwgnn-leo-routing && conda activate qwgnn
   python experiments/p5_gnn_router.py            # local-size shells (132 -> 264)
   QWGNN_FULL=1 python experiments/p5_gnn_router.py   # zero-shot to 1584 shell
   ```
   Read the P5 VERDICT. PASS bar: OOD recovered >= 50% (GNN recovers most of the
   blind->UE gain zero-shot on a bigger shell, one forward pass).
2. If PASS:
   - add the **proactive** variant: feed predicted near-future demand (moving
     hotspots, `hotspot_shift` in sim/traffic.py) so the router pre-empts
     congestion; baseline = reactive (route on last slot's prices).
   - add baselines: reactive-congestion-SP (lagged), geographic greedy; report
     inference time (GNN one-shot vs MSA iterations) to make the scalability case.
   - then write the paper (FORMULATION.md sec re-centered on P2/P3 already).
3. If P5 OOD recovery < 50%: strengthen the model before claiming the contribution
   — richer edge features (current load estimate, betweenness), deeper/attention
   readout, or train across multiple load levels. Only escalate if needed.

## Known caveats to settle before any final claim
- If QW ends up beating Heat/GCN as the router operator, run the **complex-diffusion
  control** + **abs-only-Heat control** (see FORMULATION.md sec 6) so the win is
  attributed to ballistic/interference dynamics, not extra nonlinearity.
- My automated verdicts have been wrong THREE times (relative-% slope; overload
  survivorship; filtering on blind max-util). Always sanity-check the metric by
  hand, never trust the printed verdict blindly.
- UE via MSA is the training target and is slow; that slowness is also the
  motivation (the GNN amortizes it). Keep instance counts modest locally; scale on
  the 4090.

## File map
- `sim/constellation.py` — Walker -> time-varying +Grid ISL graph (numpy, no deps).
- `sim/dataset.py` — routing-potential labels (static task, P1/P3).
- `sim/traffic.py` — BPR cost, gravity demands w/ moving hotspots, UE via MSA,
  `ue_loads` (target prices), `route_and_measure`, `demand_node_features`.
- `experiments/p1_far_resolution.py` — P1 (scaling-claim refuted).
- `experiments/p3_inductive.py`, `p3b_bellman.py` — static inductive (stalls).
- `experiments/p4_congestion_headroom.py` — headroom (confirmed).
- `experiments/p5_gnn_router.py` — CORE: amortized congestion-aware router.
- `results/*.csv` — recorded outputs. `smoke/` — P0.
