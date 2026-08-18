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

## Status (18/08/2026)

The numbers below are the ones in the manuscript, and every one of them is an entry in
`paper/claims.json` with the CSV, column, filter and aggregation that produce it. An earlier
version of this file quoted ~88% zero-shot and ~100% in-distribution, from a run superseded
several times over; it drifted because nothing checked it. `code/check_artifact_claims.py` now
does, and it is what caught this.

- **In distribution**, with both sides tuned per shell, the learned price field recovers
  `0.976` of the blind-to-equilibrium gap against `0.668` for a one-pass congestion-blind
  multipath split. Paired per instance the median difference is `0.310`.
- **Out of distribution** the two are level: paired differences of `0.007`, `0.002`, `0.020`
  on three unseen shells, and on the largest shell tested the blind split is **ahead**.
- **Under a hard link capacity** the advantage is a `29.8%` gain in delivered rate, not the
  `80.5%` delay reduction the BPR cost reports.
- **The decoder temperature is not a constant of the method**: holding it fixed costs `0.053`
  to `0.077` per unit on unseen shells.
- **Negative result kept**: the quantum-walk operator earns no place once blind-load features
  are present.

All experiments run with `python3 run_all.py` on a single machine; `results/run_all_timing.csv`
records how long each took and on which host. Numbers from different machines differ in the
third digit, so do not mix them.

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
