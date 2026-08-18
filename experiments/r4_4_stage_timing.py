"""R4.4: phan ra thoi gian theo TUNG CHANG, va doi chieu voi do dai lat cat.

PHAN BIEN NGOAI 17/08/2026, y 2.3:
    "GNN inference at 1584 takes 8.4 s while slots last 'a few seconds'. The precomputation
     claim in Section VII-A is incorrect because the features depend on live demand (the AON
     pass routes the demands). Provide a per-stage wall-clock breakdown at 1584 against the
     slot duration; correct or withdraw the precomputation claim."

Ho dung ca hai ve, va ve thu hai la mot MAU THUAN NOI BO cua bai:

  - Muc I lap luan UE bat kha thi vi "topology changing every few seconds".
  - Bang VIII do GNN het 8.4 giay o vo 1584.
  => Theo dung tieu chi bai tu dat ra de loai UE, GNN cung bi loai.

Va mo phong dung SLOT_S = 60.0 giay, khong phai "vai giay". Cau "few seconds" la loi to dam
khong co can cu trong chinh ma cua bai.

Ve tien tinh: dac trung gom BLIND LOAD, tuc tai sinh ra boi mot luot all-or-nothing tren MA
TRAN NHU CAU. Topology biet truoc, nhu cau thi khong. Nen chang dat nhat KHONG tien tinh duoc.
Script nay do rieng tung chang de bai in duoc su that do thay vi mot con so gop.
"""
import csv
import os
import statistics as st
import sys
import time

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                   # noqa: E402
from traffic import multipath_route, route_and_measure              # noqa: E402
from p5_gnn_router import (make_instance, train, TRAIN_WALKER,      # noqa: E402
                           TRAIN_PAIRS, CAP)

SLOT_S = 60.0        # dung con so cua mo phong (r2_7_warmstart_ecmp.py), khong phai van xuoi
SHELLS = [("w132", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264", Walker(264, 24, 1, 53.0, 550.0), 1200),
          ("w1584", Walker(1584, 72, 1, 53.0, 550.0), 7200)]
SEEDS = [0, 1, 2]
OUT = os.path.join(ROOT, "results", "r4_4_stage_timing.csv")


def main():
    print(f"R4.4 -- phan ra thoi gian theo chang; lat cat = {SLOT_S:.0f}s (theo MA, khong theo van xuoi)\n",
          flush=True)
    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False) for i in range(10)]
    model = train("GCN", tr, seed=0)

    rows = []
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            ins = make_instance(w, npairs, 900 + seed, need_eig=False)
            A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]

            # Chang 1: luot all-or-nothing mu, sinh dac trung blind-load.
            # PHU THUOC NHU CAU => khong tien tinh duoc du topology biet truoc.
            t0 = time.perf_counter()
            route_and_measure(A, W, dem, CAP, W)
            t_feat = time.perf_counter() - t0

            # Chang 2: forward cua GNN. Chi phu thuoc do thi va dac trung.
            t0 = time.perf_counter()
            with torch.no_grad():
                g = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()
            t_fwd = time.perf_counter() - t0

            rc = W.copy()
            rc[ins["rows"], ins["cols"]] = W[ins["rows"], ins["cols"]] * (1 + g)

            # Chang 3: giai ma da duong. Mot Dijkstra moi DICH.
            t0 = time.perf_counter()
            multipath_route(A, W, rc, dem, CAP, tau=0.2)
            t_dec = time.perf_counter() - t0

            tot = t_feat + t_fwd + t_dec
            rows.append({"shell": name, "n_sat": w.T, "seed": seed,
                         "unit_of_analysis": "vo-x-seed",
                         "t_features_s": round(t_feat, 4), "t_forward_s": round(t_fwd, 4),
                         "t_decode_s": round(t_dec, 4), "t_total_s": round(tot, 4),
                         "slot_s": SLOT_S, "frac_of_slot": round(tot / SLOT_S, 4),
                         "precomputable_s": round(t_fwd, 4),
                         "demand_dependent_s": round(t_feat + t_dec, 4)})
            print(f"  {name:6s} sd{seed}: dac trung={t_feat:7.3f}s  forward={t_fwd:6.3f}s  "
                  f"giai ma={t_dec:7.3f}s  TONG={tot:7.3f}s  = {100*tot/SLOT_S:5.1f}% lat cat",
                  flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== 2.3: co vua mot lat cat khong, va bao nhieu phan TIEN TINH duoc ===")
    for name, _, _ in SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        tot = st.median(r["t_total_s"] for r in sel)
        pre = st.median(r["precomputable_s"] for r in sel)
        dep = st.median(r["demand_dependent_s"] for r in sel)
        print(f"  {name:6s}: tong={tot:7.3f}s ({100*tot/SLOT_S:5.1f}% lat cat) | "
              f"tien tinh duoc={pre:6.3f}s ({100*pre/tot:4.1f}%) | "
              f"phu thuoc nhu cau={dep:7.3f}s ({100*dep/tot:4.1f}%)")
    print()
    print("  => Phan TIEN TINH DUOC chi la forward cua GNN. Hai chang con lai deu can ma tran")
    print("     nhu cau cua lat cat dang xet, nen tuyen bo 'topology biet truoc nen tien tinh")
    print("     duoc feature pass va forward' la SAI o ve dau va do la ve nang hon.")
    big = st.median(r["t_total_s"] for r in rows if r["shell"] == "w1584")
    print(f"\n  Voi lat cat {SLOT_S:.0f}s, vo 1584 dung het {100*big/SLOT_S:.1f}% ngan sach: VUA.")
    print("  Nhung van xuoi cua bai viet 'topology changing every few seconds' de loai UE.")
    print("  Neu lat cat that su chi vai giay thi GNN cung bi loai boi chinh tieu chi do.")
    print("  Mot trong hai phai sua, va sua theo MA moi dung: mo phong dung 60s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
