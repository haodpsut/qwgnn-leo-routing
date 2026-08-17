"""R4.3: dat SO CU THE vao Menh de 1. Hang so cua no lon toi muc nao, va o dau?

PHAN BIEN NGOAI 17/08/2026, ba y ve Menh de 1:
  4.2 "The bound's constant c1 = Theta(L*prop_max/prop_bar) diverges in the heavily congested
       regime (c1 grows as the cube of utilization); at the reported 9x peak utilization it
       reaches 437x. Yet Section VI-J claims the method earns its place in the loaded regime,
       where the bound is useless."
  4.3 "Neither c1 nor H is given a numerical value anywhere in the paper. Instantiate them, or
       stop calling Figure 6 a validation."
  4.4 "delta_dec is carried as an additive constant, but Section VI-I proves it is
       shell-dependent by 0.065 to 0.094."

Ho dung ca ba. Va y 4.2 ho tu tinh dung: BPR co cost = prop*(1 + alpha*(x/cap)^beta) voi
alpha=0.15, beta=4, nen dao ham theo tai la prop*alpha*beta*u^3/cap. He so Lipschitz vi the
ti le voi u^3: tai u=9 thi alpha*beta*u^3 = 0.15*4*729 = 437.

Mot chan tren voi he so 437 khong noi gi ve mot dai luong nam trong [0,1]. Do khong phai ly
do de giau, do la ly do de KHAI: menh de co ich o che do tai nhe, con phuong phap co ich o
che do tai nang, va hai mien do KHONG giao nhau. Script nay do cac hang so de bai in duoc
chung ra thay vi de chung o dang Theta().
"""
import csv
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                    # noqa: E402
from traffic import (evaluate, multipath_route, route_and_measure,   # noqa: E402
                     _route_on_cost)
from p5_gnn_router import make_instance, CAP                         # noqa: E402

ALPHA, BETA = 0.15, 4.0
SHELLS = [("w132_i53", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264_i53", Walker(264, 24, 1, 53.0, 550.0), 1200)]
SEEDS = [0, 1, 2]
OUT = os.path.join(ROOT, "results", "r4_3_bound_constants.csv")


def main():
    print("R4.3 -- dat so cu the vao Menh de 1\n", flush=True)
    print(f"  BPR: cost = prop*(1 + {ALPHA}*(x/cap)^{BETA:.0f})")
    print(f"  dcost/dx = prop*{ALPHA}*{BETA:.0f}*u^3/cap, nen he so Lipschitz ~ u^3\n")

    rows = []
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            ins = make_instance(w, npairs, 900 + seed, need_eig=False)
            A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]
            prop = W[A > 0]
            pmax, pbar = float(prop.max()), float(prop.mean())

            blind = route_and_measure(A, W, dem, CAP, W)
            ue = evaluate(A, W, dem, CAP, policy="ue")

            # H: so chang dai nhat cua duong DA GIAI MA, khong phai duong kinh do thi.
            # route_and_measure khong tra ve paths nen dinh tuyen lai o day cho dung dai luong.
            paths = _route_on_cost(A, W, dem)
            H = max((len(p) - 1) for p, _ in paths if p is not None)

            u_blind = float(blind["max_util"])
            u_ue = float(ue["max_util"])
            # c1 ~ L * pmax / pbar, voi L ~ alpha*beta*u^3 (phan phu thuoc tai cua dao ham)
            c1 = lambda u: ALPHA * BETA * (u ** 3) * pmax / pbar
            rows.append({"shell": name, "seed": seed, "unit_of_analysis": "vo-x-seed",
                         "prop_max": round(pmax, 4), "prop_mean": round(pbar, 4),
                         "prop_ratio": round(pmax / pbar, 3), "H_hops": H,
                         "maxutil_blind": round(u_blind, 3), "maxutil_ue": round(u_ue, 3),
                         "c1_at_ue": round(c1(u_ue), 1), "c1_at_blind": round(c1(u_blind), 1),
                         "c1H_at_ue": round(c1(u_ue) * H, 1) if H > 0 else "",
                         "c1H_at_blind": round(c1(u_blind) * H, 1) if H > 0 else ""})
            print(f"  {name} sd{seed}: H={H:>2}  pmax/pbar={pmax/pbar:.2f}  "
                  f"u(UE)={u_ue:.2f} u(blind)={u_blind:.2f}  "
                  f"c1H(UE)={c1(u_ue)*H:>9.1f}  c1H(blind)={c1(u_blind)*H:>11.1f}", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== MENH DE 1 NOI DUOC GI, BANG SO ===")
    H = st.median(r["H_hops"] for r in rows)
    cU = st.median(r["c1H_at_ue"] for r in rows)
    cB = st.median(r["c1H_at_blind"] for r in rows)
    print(f"  H (so chang dai nhat cua duong da giai ma) = {H:.0f}")
    print(f"  c1*H tai tai UE     = {cU:,.0f}")
    print(f"  c1*H tai tai blind  = {cB:,.0f}")
    print()
    print("  Chan la TTT(pi) <= (1 + delta_dec + c1*H*eps) * TTT*.")
    print("  De phan du doan co nghia (vi du dong gop duoi 10%) thi can eps <= 0.1/(c1*H):")
    for lbl, v in (("tai UE", cU), ("tai blind", cB)):
        print(f"    {lbl:10s}: eps <= {0.1/v:.2e}")
    print()
    print("  => Sai so gia tren MOI lien ket phai duoi muc do thi chan moi noi duoc dieu gi.")
    print("     Do la nguong ma khong mo hinh hoc nao trong bai nay dat toi, ke ca tren vo")
    print("     huan luyen. Menh de 1 vi vay la mot phat bieu ve DANG (sai so gia -> sai so")
    print("     dinh tuyen, tuyen tinh, tat dan ve delta_dec), KHONG phai mot chan dung duoc.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
