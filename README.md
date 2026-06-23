# ntn-paper-01 — Quantum-Walk GNN for Proactive LEO Routing

IEEE Transactions paper (primary: TNSM; stretch: TWC). Core idea: a
quantum-walk (ballistic, interfering) graph propagation operator for learning the
routing potential field on **ephemeris-known, time-varying** LEO constellation
graphs, giving proactive and scale-invariant routing.

## Status
- **P0 smoke kill-test (Pillar 1): PASSED.** Quantum-walk propagation beats
  classical diffusion on long-range routing-potential resolution in 12/12
  param-matched cells (~52% mean far-node error reduction; absolute advantage
  widens with diameter). See `smoke/`.
- Next: `sim/` Hypatia pipeline to replicate Pillar 1 on real Starlink topology
  (kill gate P1), then complex-diffusion control (kill gate P2).

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
