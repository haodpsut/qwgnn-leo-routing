# ntn-paper-01 — Inductive GNN for Amortized Congestion-Aware LEO Routing

IEEE Transactions paper (primary: TNSM; stretch: TWC). Core idea: a GNN that
predicts congestion-aware routing (the user-equilibrium congestion prices) on LEO
constellation graphs in **one forward pass**, from cheap observable load features,
generalizing inductively across constellation scale -- amortizing the iterative
traffic-engineering solve that does not scale to mega-constellations.

> Pivoted from an original quantum-walk angle: the kill-gates refuted it (static
> routing is already solved by Dijkstra/geographic; the quantum operator gives no
> benefit once load features exist). Quantum-walk is kept only as a negative
> ablation. See FORMULATION.md sec 6 for the full honest record.

## Status
- **Core result (P5): solid.** A one-shot GNN with blind-load features recovers
  ~88% (GCN) of the blind->user-equilibrium travel-time gain ZERO-SHOT on a 2x
  larger shell; in-distribution ~100%. Headroom confirmed (P4): blind routing
  wastes 8/50/80/90% of total travel time as load grows.
- Next: baselines (reactive-SP, geographic) + inference-time vs MSA (scalability)
  + proactive variant (predicted demand) + writing. See RESUME.md.

## Layout
- `FORMULATION.md` — system model, operators, three falsifiable pillars, prior-art
  positioning, verification protocol.
- `PLAN.md` — phased plan with kill gates and risks.
- `smoke/` — self-contained Pillar-1 kill-test (torch CPU, no Hypatia needed).

## Run the smoke
```
cd smoke
python run_smoke.py      # trains GCN/Heat/QW across diameters x seeds -> smoke_results.csv
python analyze.py        # corrected verdict (absolute hop-gap + win-rate)
```
