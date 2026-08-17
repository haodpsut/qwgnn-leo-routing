"""R1.1: how is the softmin temperature chosen, and how much does the answer depend on it?

REVIEWER 1, COMMENT 1:
    "In Section V-E, the softmin temperature controls the flow splitting, but the paper does not
     specify how this value is chosen across experiments. Is it fixed, tuned on a validation set,
     or adapted per scenario? Adding a brief note on the selection rationale and its sensitivity
     would improve reproducibility."

The factual half is easy and was simply never written down: tau is FIXED at 0.2 for every
experiment, hardcoded in p8_decoder.py and p9_bound.py and read from an environment variable
defaulting to 0.2 in p5_gnn_router.py. It was never tuned on a validation set and never varied per
scenario.

The half that matters is the second one. A knob fixed by hand is only defensible if the result does
not hinge on where it was fixed, and that has to be shown rather than asserted. This sweeps tau
across an order of magnitude on both the training shell and an unseen one, and reports the decoded
travel time relative to blind at each setting, so a reader can see the shape of the dependence and
where 0.2 sits on it.

Reporting the curve rather than a single sensitivity number is deliberate. tau -> 0 recovers
single-path decoding and large tau spreads flow indiscriminately, so the interesting question is
not "how big is the derivative at 0.2" but "is 0.2 on a flat stretch or on a slope", and only the
curve answers that.
"""
import csv
import os
import statistics as st
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                   # noqa: E402
from traffic import evaluate, multipath_route, route_and_measure    # noqa: E402
from p5_gnn_router import (make_instance, train, TRAIN_WALKER,      # noqa: E402
                           TRAIN_PAIRS, CAP)

TAUS = [0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 1.00]
DEFAULT_TAU = 0.20
SHELLS = [("w132 (trained)", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264 (unseen)", Walker(264, 24, 1, 53.0, 550.0), 1200)]
SEEDS = [0, 1, 2]
OUT = os.path.join(ROOT, "results", "r1_1_tau_sweep.csv")


def main():
    print("R1.1 -- do nhay cua nhiet do softmin\n", flush=True)
    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False) for i in range(10)]
    model = train("GCN", tr, seed=0)
    rows = []
    print(f"{'vo':16s} {'sd':>2} | " + " ".join(f"t={t:<4g}".rjust(8) for t in TAUS), flush=True)
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            ins = make_instance(w, npairs, 900 + seed, need_eig=False)
            A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]
            with torch.no_grad():
                g = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()
            rc = W.copy()
            rc[ins["rows"], ins["cols"]] = W[ins["rows"], ins["cols"]] * (1 + g)
            blind = route_and_measure(A, W, dem, CAP, W)["total_ttt"]
            ue = evaluate(A, W, dem, CAP, policy="ue")["total_ttt"]
            so = evaluate(A, W, dem, CAP, policy="so")["total_ttt"]
            span = blind - ue
            row = {"shell": name, "seed": seed, "unit_of_analysis": "vo-x-seed"}
            cells = []
            for t in TAUS:
                v = multipath_route(A, W, rc, dem, CAP, tau=t)["total_ttt"]
                assert v >= so - 1e-6, f"tau={t}: {v:.3f} < system optimum {so:.3f}"
                rec = (blind - v) / span if span > 0 else float("nan")
                row[f"recovered_tau{t}"] = round(rec, 4)
                cells.append(f"{rec:>8.3f}")
            rows.append(row)
            print(f"{name:16s} {seed:>2} | " + " ".join(cells), flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== TRUNG VI theo vo ===")
    print(f"{'vo':16s} " + " ".join(f"t={t:<4g}".rjust(8) for t in TAUS))
    for name, _, _ in SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        m = {t: st.median(r[f"recovered_tau{t}"] for r in sel) for t in TAUS}
        print(f"{name:16s} " + " ".join(f"{m[t]:>8.3f}" for t in TAUS))
        best = max(TAUS, key=lambda t: m[t])
        d = m[best] - m[DEFAULT_TAU]
        print(f"  tot nhat tai tau={best:g} ({m[best]:.3f}); tau={DEFAULT_TAU:g} dung trong bai "
              f"cho {m[DEFAULT_TAU]:.3f}, kem {d:+.3f}")
        flat = [t for t in TAUS if abs(m[t] - m[DEFAULT_TAU]) <= 0.02]
        print(f"  doan PHANG quanh gia tri dang dung (lech <= 0.02): tau in {flat}\n")

    print("=== KET LUAN ===")
    ok = True
    for name, _, _ in SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        m = {t: st.median(r[f"recovered_tau{t}"] for r in sel) for t in TAUS}
        ok &= (max(m.values()) - m[DEFAULT_TAU]) <= 0.05
    print("  Ket qua KHONG phu thuoc manh vao tau: gia tri co dinh 0.2 nam trong 0.05 cua muc tot"
          "\n  nhat tren ca hai vo." if ok else
          "  ⚠ Ket qua PHU THUOC vao tau: phai khai la mot sieu tham so da chon, va bao ca duong"
          "\n  cong chu khong chi mot diem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
