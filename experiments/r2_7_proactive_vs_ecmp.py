"""The last untested contribution: does proactivity beat blind spreading under a drifting hotspot?

Everything measured so far says the learned price field does NOT beat eps-ECMP off-distribution at
steady load. But p7_proactive.py only ever compared reactive against proactive against UE. Its CSV
carries three columns, r_ue, r_react, r_proact, and no cheap baseline at all. So the paper's fourth
sub-problem has never faced the comparator that beat the third one.

This is the measurement that decides whether the paper can be lifted or has to be downgraded,
because of a STRUCTURAL asymmetry rather than a numeric one. eps-ECMP spreads according to path
geometry: it looks at where the links are, never at where the load is or will be. A hotspot moving
across the constellation is something it cannot follow no matter how wide eps is opened, because
widening eps spreads more everywhere rather than spreading toward the right place. A predicted
price field can point at the load that is about to arrive.

If proactive routing beats eps-ECMP and the gap GROWS with drift, the paper has a contribution no
cheap baseline can reach, and the honest story becomes sharp: learned price fields do not win at
steady-state load balancing, they win at anticipation. If the gap does not grow, the method has no
axis left that a one-pass blind heuristic does not cover, and resubmitting to TNSM is the wrong
call.

Same drift ladder as p7. Reactive sees last slot's demand, proactive sees this slot's; both route
this slot's demand. eps-ECMP and warm MSA route this slot's demand too, so nobody is handicapped
on information they would actually have.
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

from constellation import Walker, grid_isl_graph                    # noqa: E402
from traffic import (gravity_demands, route_and_measure, evaluate)   # noqa: E402
from p5_gnn_router import (make_instance, train, build_features,     # noqa: E402
                           TRAIN_WALKER, TRAIN_PAIRS, CAP)
from r2_7_warmstart_ecmp import msa_from, ecmp_ttt                   # noqa: E402

SEEDS = [0, 1, 2]
EVAL_SHELLS = [("w132", Walker(132, 12, 1, 53.0, 550.0), 600),       # vo da huan luyen
               ("w264", Walker(264, 24, 1, 53.0, 550.0), 1200)]      # vo NGOAI phan phoi
DRIFTS = [0.0, 0.3, 0.6, 1.0, 1.5]
EPSS = [0.05, 0.20, 0.35, 0.50]
N_TRAIN = 10
OUT = os.path.join(ROOT, "results", "r2_7_proactive_vs_ecmp.csv")


def route_prices(model, A, W, obs_dem, route_dem, cap):
    X, ctx, rows, cols, _ = build_features(A, W, obs_dem, need_eig=False)
    with torch.no_grad():
        g = torch.expm1(model(X, ctx)).clamp(min=0).numpy()
    rc = W.copy()
    rc[rows, cols] = W[rows, cols] * (1 + g)
    return route_and_measure(A, W, route_dem, cap, rc)["total_ttt"]


def main():
    print("R2.7e -- CHU DONG vs TRAI TAI MU duoi hotspot TROI\n", flush=True)
    rows = []
    for name, walker, npairs in EVAL_SHELLS:
        A, W = grid_isl_graph(walker, 0.0, seam=False)
        pos = walker.positions(0.0)
        print(f"--- {name} ({walker.T} sat, {npairs} cap)", flush=True)
        print(f"{'sd':>2} {'troi':>5} {'react':>7} {'proact':>7} {'warmT2':>7} | "
              + " ".join(f"e={e:<4g}".rjust(7) for e in EPSS), flush=True)
        for seed in SEEDS:
            tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 100 + seed * 50 + i, need_eig=False)
                  for i in range(N_TRAIN)]
            model = train("GCN", tr, seed)
            for drift in DRIFTS:
                D_prev = gravity_demands(pos, npairs, np.random.default_rng(1234 + seed),
                                         hotspot_shift=0.0)
                D_now = gravity_demands(pos, npairs, np.random.default_rng(1234 + seed),
                                        hotspot_shift=drift)
                blind = route_and_measure(A, W, D_now, CAP, W)["total_ttt"]
                ue = evaluate(A, W, D_now, CAP, policy="ue")["total_ttt"]
                so = evaluate(A, W, D_now, CAP, policy="so")["total_ttt"]
                span = blind - ue
                rec = lambda x: (blind - x) / span if span > 0 else float("nan")
                _, warm_prev = msa_from(A, W, D_prev, CAP, 20)
                vals = {
                    "react": route_prices(model, A, W, D_prev, D_now, CAP),
                    "proact": route_prices(model, A, W, D_now, D_now, CAP),
                    "warmT2": msa_from(A, W, D_now, CAP, 2, load0=warm_prev, k0=20)[0],
                }
                for e in EPSS:
                    vals[f"ecmp{e}"] = ecmp_ttt(A, W, D_now, CAP, eps=e)
                for k, v in vals.items():
                    assert v >= so - 1e-6, f"{k} {v:.3f} < SO {so:.3f}"
                row = {"shell": name, "seed": seed, "drift": drift,
                       "unit_of_analysis": "vo-x-seed-x-troi"}
                row.update({f"recovered_{k}": round(rec(v), 4) for k, v in vals.items()})
                rows.append(row)
                print(f"{seed:>2} {drift:>5.2f} {row['recovered_react']:>7.3f} "
                      f"{row['recovered_proact']:>7.3f} {row['recovered_warmT2']:>7.3f} | "
                      + " ".join(f"{row[f'recovered_ecmp{e}']:>7.3f}" for e in EPSS), flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    for name, _, _ in EVAL_SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        print(f"=== {name}: trung vi theo muc TROI ===")
        print(f"{'troi':>5} {'proact':>8} {'react':>8} {'ecmp tot':>9} {'eps':>5} "
              f"{'proact - ecmp':>14}")
        gaps = []
        for d in DRIFTS:
            s2 = [r for r in sel if r["drift"] == d]
            p = st.median(r["recovered_proact"] for r in s2)
            rr = st.median(r["recovered_react"] for r in s2)
            me = {e: st.median(r[f"recovered_ecmp{e}"] for r in s2) for e in EPSS}
            be = max(EPSS, key=lambda e: me[e])
            gaps.append(p - me[be])
            print(f"{d:>5.2f} {p:>8.3f} {rr:>8.3f} {me[be]:>9.3f} {be:>5g} {p - me[be]:>+14.3f}")
        print(f"  khoang cach chu-dong tru ecmp theo troi: "
              f"{[f'{g:+.3f}' for g in gaps]}")
        grows = gaps[-1] > gaps[0] + 0.02
        wins = gaps[-1] > 0
        print(f"  => {'NO RONG ra theo troi' if grows else 'KHONG no ra theo troi'}; "
              f"o troi lon nhat chu dong {'THANG' if wins else 'THUA'} ecmp\n")

    print("=== PHAN QUYET ===")
    ok = []
    for name, _, _ in EVAL_SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        hi = [r for r in sel if r["drift"] == DRIFTS[-1]]
        p = st.median(r["recovered_proact"] for r in hi)
        me = max(st.median(r[f"recovered_ecmp{e}"] for r in hi) for e in EPSS)
        ok.append(p > me)
        print(f"  {name}: o troi {DRIFTS[-1]}, chu dong {p:.3f} vs ecmp tot nhat {me:.3f} "
              f"= {p - me:+.3f}")
    if all(ok):
        print("\n  ✅ Chu dong THANG trai tai mu tren CA HAI vo o muc troi lon nhat.")
        print("     Day la truc ecmp khong voi toi duoc, va la cho de dat dong gop dau bai.")
    elif any(ok):
        print("\n  Chu dong chi thang tren MOT vo. Yeu, phai khai ro dieu kien.")
    else:
        print("\n  ⛔ Chu dong KHONG thang trai tai mu o bat ky vo nao.")
        print("     Bai khong con truc nao mot heuristic mu mot luot khong phu duoc.")
        print("     Khuyen nghi: DUNG nop lai TNSM, doi venue hoac viet lai thanh bai khac.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
