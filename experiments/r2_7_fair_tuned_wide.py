"""The fair comparison again, with enough units to trust it and a grid that is not truncated.

r2_7_fair_tuned.py tuned both sides per shell and reversed the earlier verdict: off distribution
the learned field and blind spreading came out level rather than the field losing. Two things made
that result too weak to write down.

  n = 3 seeds per shell. With per-shell gaps of +0.008, +0.001 and +0.020, three units cannot tell
  a small advantage from a coin flip, and reporting a median over three numbers as though it
  settled the question would be the same overreach this paper is about.

  tau = 2.0 was the top of the grid and won on three shells of four. When the optimum sits on the
  boundary of the search, the search has not found the optimum, it has run out of room. Any
  "best tau" read off that grid is a lower bound on the tuning available to the method, so the
  comparison still leaned against it.

This run fixes both: eight seeds per shell, and a tau grid extended until the curve turns over
rather than until I stop looking. It also reports the paired outcome per unit alongside the median,
because with differences this small the count of units where one side wins says more than the
central value does.
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

from constellation import Walker                                    # noqa: E402
from traffic import evaluate, multipath_route, route_and_measure     # noqa: E402
from p5_gnn_router import (make_instance, train, TRAIN_WALKER,       # noqa: E402
                           TRAIN_PAIRS, CAP)
from r2_7_warmstart_ecmp import ecmp_ttt                             # noqa: E402

TAUS = [0.05, 0.10, 0.20, 0.35, 0.50, 1.00, 2.00, 3.50, 5.00, 8.00]
EPSS = [0.05, 0.10, 0.20, 0.35, 0.50, 0.75]
FIXED_TAU = 0.20
SHELLS = [("w132_i53", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w198_i53", Walker(198, 18, 1, 53.0, 550.0), 900),
          ("w264_i53", Walker(264, 24, 1, 53.0, 550.0), 1200),
          ("w264_i70", Walker(264, 24, 1, 70.0, 550.0), 1200)]
SEEDS = list(range(8))
OUT = os.path.join(ROOT, "results", "r2_7_fair_tuned_wide.csv")


def main():
    print(f"R2.7g -- {len(SEEDS)} seed/vo, luoi tau den {max(TAUS):g}\n", flush=True)
    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False) for i in range(10)]
    model = train("GCN", tr, seed=0)
    rows = []
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
            rec = lambda x: (blind - x) / span if span > 0 else float("nan")
            row = {"shell": name, "seed": seed, "unit_of_analysis": "vo-x-seed"}
            for t in TAUS:
                v = multipath_route(A, W, rc, dem, CAP, tau=t)["total_ttt"]
                assert v >= so - 1e-6, f"gnn tau={t} duoi system optimum"
                row[f"recovered_gnn_tau{t}"] = round(rec(v), 4)
            for e in EPSS:
                v = ecmp_ttt(A, W, dem, CAP, eps=e)
                assert v >= so - 1e-6, f"ecmp eps={e} duoi system optimum"
                row[f"recovered_ecmp_eps{e}"] = round(rec(v), 4)
            rows.append(row)
        print(f"  {name}: {len(SEEDS)} seed xong", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== duong cong tau theo vo (trung vi) -- co quay dau chua? ===")
    print(f"{'vo':10s} " + " ".join(f"{t:g}".rjust(7) for t in TAUS))
    truncated = []
    for name, _, _ in SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        m = {t: st.median(r[f"recovered_gnn_tau{t}"] for r in sel) for t in TAUS}
        bt = max(TAUS, key=lambda t: m[t])
        if bt == TAUS[-1]:
            truncated.append(name)
        print(f"{name:10s} " + " ".join(f"{m[t]:>7.3f}" for t in TAUS) + f"   tot nhat tau={bt:g}")
    print("  luoi con bi cat cut o: " + (", ".join(truncated) if truncated else "khong vo nao"))

    print(f"\n=== SO CONG BANG, {len(SEEDS)} don vi moi vo ===")
    print(f"{'vo':10s} {'GNN@0.2':>8} {'GNN tot':>8} {'tau*':>5} {'ECMP tot':>9} {'eps*':>5} "
          f"{'chenh':>8} {'GNN thang':>10}")
    verd = []
    for name, _, _ in SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        mt = {t: st.median(r[f"recovered_gnn_tau{t}"] for r in sel) for t in TAUS}
        me = {e: st.median(r[f"recovered_ecmp_eps{e}"] for r in sel) for e in EPSS}
        bt, be = max(TAUS, key=lambda t: mt[t]), max(EPSS, key=lambda e: me[e])
        d = mt[bt] - me[be]
        wins = sum(1 for r in sel if r[f"recovered_gnn_tau{bt}"] > r[f"recovered_ecmp_eps{be}"])
        verd.append((name, mt[FIXED_TAU], mt[bt], bt, me[be], be, d, wins, len(sel)))
        print(f"{name:10s} {mt[FIXED_TAU]:>8.3f} {mt[bt]:>8.3f} {bt:>5g} {me[be]:>9.3f} "
              f"{be:>5g} {d:>+8.3f} {wins:>7d}/{len(sel)}")

    print("\n=== PHAN QUYET ===")
    for name, fx, bv, bt, ev, be, d, wins, n in verd:
        # voi chenh lech nho, DEM DON VI moi la thu doc duoc, khong phai trung vi
        if wins >= n - 1:
            tag = "GNN thang gan nhu moi don vi"
        elif wins <= 1:
            tag = "ECMP thang gan nhu moi don vi"
        else:
            tag = f"HOA ({wins}/{n})"
        print(f"  {name:10s} chenh {d:+.3f}, GNN thang {wins}/{n}  [{tag}]")
        if bv - fx > 0.02:
            print(f"             tau co dinh 0.2 lam mat {bv-fx:.3f}")
    close = [v for v in verd if 2 <= v[7] <= v[8] - 2]
    print()
    print(f"  {len(close)}/{len(verd)} vo la HOA theo dem don vi." if close else
          "  Khong vo nao hoa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
