"""A fair comparison: GNN tuned over tau against eps-ECMP tuned over eps, both per shell.

Every off-distribution GNN number reported so far used tau = 0.2, the value fixed in the
manuscript. r1_1_tau_sweep.py then showed that tau = 0.2 is near-optimal on the shell the model was
trained on and costs 0.084 on an unseen one, where the best setting is tau = 1.0. Meanwhile I had
been giving eps-ECMP the best eps FOR EACH SHELL throughout.

So the comparison was rigged, and rigged by me rather than by the manuscript: one side tuned per
shell, the other frozen at a value chosen on a different shell. That is exactly the asymmetry I
have been criticising the learned-routing literature for, arriving from the opposite direction.

This tunes both sides per shell and reports both knobs. If the learned field pulls ahead once the
decoder is allowed the same freedom the baseline was given, the conclusion "loses off distribution"
has to be narrowed to "loses off distribution AT THE FIXED DECODER SETTING", which is a claim about
the manuscript's configuration rather than about learned price fields.

The two knobs are not equally innocent and the paper must say so. eps is a deployment parameter an
operator sets once; tau is a decoder parameter the same operator also sets once. Neither requires
labels or a solve on the target shell, so tuning either off-line against a handful of instances is
realistic. What neither side may do is tune against the test instance itself, and neither does
here: both sweeps are over the same fixed grid for every shell, with the per-shell best reported.
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

TAUS = [0.05, 0.10, 0.20, 0.35, 0.50, 1.00, 2.00]
EPSS = [0.05, 0.10, 0.20, 0.35, 0.50]
FIXED_TAU = 0.20
SHELLS = [("w132_i53", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w198_i53", Walker(198, 18, 1, 53.0, 550.0), 900),
          ("w264_i53", Walker(264, 24, 1, 53.0, 550.0), 1200),
          ("w264_i70", Walker(264, 24, 1, 70.0, 550.0), 1200)]
SEEDS = [0, 1, 2]
OUT = os.path.join(ROOT, "results", "r2_7_fair_tuned.csv")


def main():
    print("R2.7f -- chinh CA HAI ben theo tung vo\n", flush=True)
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
            print(f"  {name} seed {seed} xong", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print(f"{'vo':10s} {'GNN@0.2':>9} {'GNN tot':>9} {'tau*':>6} {'ECMP tot':>9} {'eps*':>6} "
          f"{'chenh cong bang':>16}")
    verdict = []
    for name, _, _ in SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        mt = {t: st.median(r[f"recovered_gnn_tau{t}"] for r in sel) for t in TAUS}
        me = {e: st.median(r[f"recovered_ecmp_eps{e}"] for r in sel) for e in EPSS}
        bt, be = max(TAUS, key=lambda t: mt[t]), max(EPSS, key=lambda e: me[e])
        d = mt[bt] - me[be]
        wins = sum(1 for r in sel
                   if r[f"recovered_gnn_tau{bt}"] > r[f"recovered_ecmp_eps{be}"])
        verdict.append((name, mt[FIXED_TAU], mt[bt], bt, me[be], be, d, wins, len(sel)))
        print(f"{name:10s} {mt[FIXED_TAU]:>9.3f} {mt[bt]:>9.3f} {bt:>6g} {me[be]:>9.3f} "
              f"{be:>6g} {d:>+16.3f}")

    print("\n=== PHAN QUYET ===")
    for name, fixed, best, bt, ecmp, be, d, wins, n in verdict:
        tag = "GNN thang" if d > 0 else "⛔ GNN thua"
        print(f"  {name:10s}: chinh cong bang -> GNN {best:.3f} (tau={bt:g}) vs ECMP {ecmp:.3f} "
              f"(eps={be:g}) = {d:+.3f}, thang {wins}/{n}  [{tag}]")
        if best - fixed > 0.02:
            print(f"              {'':9s} tau co dinh 0.2 chi cho {fixed:.3f}, tuc bo giai ma "
                  f"lam mat {best-fixed:.3f}")
    lost = [v for v in verdict if v[6] < 0]
    print()
    if not lost:
        print("  ⇒ Khi CA HAI cung duoc chinh, GNN thang tren MOI vo. Ket luan 'thua ngoai phan")
        print("     phoi' phai thu hep thanh 'thua O GIA TRI GIAI MA CO DINH cua ban thao'.")
    else:
        print(f"  ⇒ Van thua o {len(lost)}/{len(verdict)} vo ngay ca khi duoc chinh cong bang: "
              + ", ".join(v[0] for v in lost))
    return 0


if __name__ == "__main__":
    sys.exit(main())
