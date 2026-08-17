"""R4.2: tuyen bo TANG TOC 29x do voi cai gi? Dem SO VONG MSA can de hoi tu, lanh vs am.

PHAN BIEN NGOAI, 17/08/2026, y 2.2:
    "The speedup is measured against a cold-start 20-iteration MSA. The topology is near static
     with known small demand drift, yet the previous slot's equilibrium is never used as a warm
     start. Run a warm-started MSA/Frank-Wolfe and report the iteration count."

Y nay dung va chua ai do. `r2_7_warmstart_ecmp.py` co khoi dong am, nhung no do CHAT LUONG o
ngan sach bi CAT CUT (T=1, T=2), khong do so vong can de HOI TU. Bang II cua bai ghi
"UE, SO (MSA) T ~ 20" khong kem dieu kien, va 20 la con so cua khoi dong LANH.

Neu MSA am hoi tu sau 3 vong thay vi 20 thi 29x sap con ~4x, va "chi phi giam theo quy mo"
khong con la mot dong gop. Do la ket qua phai bao, khong phai ket qua phai tranh.

CACH DO. Voi moi lat cat: chay MSA rat dai (REF_ITERS) de lay TTT quy chieu, roi dem so vong
nho nhat de mot lan chay chay toi trong TOL tuong doi cua quy chieu do. Lam vay cho:
  - lanh: bat dau tu luot all-or-nothing;
  - am : bat dau tu tai can bang cua lat cat TRUOC, tiep tuc day so buoc tai dung k.
Nhung k0 la cai bay: buoc MSA la 1/(k+1). Bat dau lai mot lan chay AM tai k0=1 la nem di
chinh cai khoi dong am roi do loi cho no. Toi da mac dung loi nay mot lan.
"""
import csv
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                     # noqa: E402
from constellation import grid_isl_graph                              # noqa: E402
from traffic import (gravity_demands, edge_loads, link_cost,          # noqa: E402
                     _route_on_cost)
from r2_7_warmstart_ecmp import (SHELLS, SEEDS, CAP, SLOT_S,          # noqa: E402
                                 DRIFT_PER_SLOT, realized_ttt, msa_from)

REF_ITERS = 80          # quy chieu: du dai de coi la da hoi tu
TOL = 0.005             # trong 0.5% TTT cua quy chieu thi coi la hoi tu
MAX_ITERS = 40
N_SLOTS = 4
OUT = os.path.join(ROOT, "results", "r4_2_warmstart_iters.csv")


def iters_to_converge(A, W, dem, ref_ttt, load0=None, k0=1):
    """So vong nho nhat de TTT vao trong TOL cua quy chieu. Tra MAX_ITERS neu khong dat."""
    n = A.shape[0]
    if load0 is None:
        paths = _route_on_cost(A, link_cost(W, np.zeros_like(W), CAP), dem)
        load = edge_loads([(p, r) for p, r in paths if p is not None], n)
    else:
        load = load0.copy()
    for k in range(k0, k0 + MAX_ITERS):
        cost = link_cost(W, load, CAP)
        aon = _route_on_cost(A, cost, dem)
        aload = edge_loads([(p, r) for p, r in aon if p is not None], n)
        load = load + (aload - load) / (k + 1)
        final = _route_on_cost(A, link_cost(W, load, CAP), dem)
        ttt = realized_ttt(W, final, CAP)
        if ttt <= ref_ttt * (1 + TOL):
            return k - k0 + 1, ttt
    return MAX_ITERS, ttt


def main():
    print("R4.2 -- so vong MSA can de hoi tu: khoi dong LANH vs AM")
    print(f"   quy chieu = MSA {REF_ITERS} vong; hoi tu = trong {TOL*100:.1f}% TTT quy chieu\n",
          flush=True)
    rows = []
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            warm_load, warm_k = None, 1
            for slot in range(N_SLOTS):
                tt = slot * SLOT_S
                A, W = grid_isl_graph(w, tt, seam=False)
                pos = w.positions(tt)
                # CUNG seed, chi TROI dai hotspot -- giong r2_7_warmstart_ecmp.py. Sinh nhu cau
                # doc lap moi lat cat se tuoc mat khoi dong am dung cai lam no manh.
                dem = gravity_demands(pos, npairs, np.random.default_rng(seed),
                                      hotspot_shift=slot * DRIFT_PER_SLOT)
                ref_ttt, ref_load = msa_from(A, W, dem, CAP, REF_ITERS)
                n_cold, _ = iters_to_converge(A, W, dem, ref_ttt)
                if slot == 0:
                    warm_load, warm_k = ref_load, REF_ITERS
                    continue      # lat cat 0 chi de nap cache, khong tinh diem
                n_warm, _ = iters_to_converge(A, W, dem, ref_ttt,
                                              load0=warm_load, k0=warm_k)
                rows.append({"shell": name, "seed": seed, "slot": slot,
                             "unit_of_analysis": "vo-x-seed-x-lat-cat",
                             "iters_cold": n_cold, "iters_warm": n_warm,
                             "ref_ttt": round(ref_ttt, 4)})
                print(f"  {name} sd{seed} lat{slot}: lanh={n_cold:2d} vong  am={n_warm:2d} vong",
                      flush=True)
                warm_load, warm_k = ref_load, REF_ITERS

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== KET QUA ===")
    for name, _, _ in SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        c = st.median(r["iters_cold"] for r in sel)
        m = st.median(r["iters_warm"] for r in sel)
        # Ghep cap theo tung don vi, khong lay hieu cua hai trung vi.
        pair = [r["iters_cold"] - r["iters_warm"] for r in sel]
        print(f"  {name}: lanh={c:.0f} vong (trung vi)  am={m:.0f} vong  "
              f"tiet kiem ghep cap={st.median(pair):+.0f} vong  ({sum(p>0 for p in pair)}/{len(pair)} don vi)")

    print("\n=== TUYEN BO TANG TOC BI ANH HUONG THE NAO ===")
    allc = st.median(r["iters_cold"] for r in rows)
    allm = st.median(r["iters_warm"] for r in rows)
    print(f"  Bang II cua bai ghi 'UE, SO (MSA) T ~ 20' khong kem dieu kien.")
    print(f"  do duoc: lanh {allc:.0f} vong, am {allm:.0f} vong.")
    if allm > 0:
        print(f"  => neu doi thu la MSA AM thi tang toc phai chia cho {allc/allm:.1f}x:")
        for sp in (21, 22, 29):
            print(f"       {sp}x bao trong bai  ->  ~{sp*allm/allc:.1f}x so voi MSA am")
    print("\n  Con so nao vao bai la tuy KICH BAN TRIEN KHAI, va bai phai NOI ro kich ban do:")
    print("  mot he dieu hanh giu duoc can bang lat truoc thi doi thu dung la MSA am.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
