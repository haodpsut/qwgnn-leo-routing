#!/usr/bin/env bash
# Full-scale validation on the RTX 4090 server (CPU-bound: MSA/Dijkstra).
# Run from the repo root inside the activated conda env `qwgnn`, under tmux.
#   conda activate qwgnn && bash scripts/server_full.sh
#
# Produces, in results/:
#   p5_router.csv      -- C2: inductive zero-shot quality on the 1584-sat shell
#   p6_baselines.csv   -- C3: inference time incl. 1584 + system-optimal (SO) row
#   *.log              -- console logs
#
# Env knobs (defaults in parentheses): QWGNN_SEEDS (0,1) QWGNN_TRAIN (8)
# QWGNN_EVAL (2). Raise them for tighter error bars at higher cost.

set -euo pipefail
mkdir -p results

export QWGNN_SEEDS="${QWGNN_SEEDS:-0,1}"
export QWGNN_TRAIN="${QWGNN_TRAIN:-8}"
export QWGNN_EVAL="${QWGNN_EVAL:-2}"

echo "=== [1/2] C2: inductive zero-shot on the 1584-sat shell (GCN, no eig) ==="
QWGNN_FULL=1 QWGNN_OPS=GCN \
  python experiments/p5_gnn_router.py 2>&1 | tee results/p5_full_1584.log

echo "=== [2/2] C3: inference time on 1584 + system-optimal reference ==="
QWGNN_FULL=1 \
  python experiments/p6_baselines.py 2>&1 | tee results/p6_full_1584.log

echo "=== done. Key numbers:"
tail -n 12 results/p5_full_1584.log
echo "---"
tail -n 12 results/p6_full_1584.log
