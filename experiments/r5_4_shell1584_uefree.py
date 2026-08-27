"""R5.4 -- vo 1584 KHONG DUNG can bang: chi so sanh nhung gi do truc tiep duoc.

⛔ VI SAO BO UE O VO NAY. Do 27/08 tren nam nac (20/40/80/160/320 vong):
    PoA = UE/SO : 0.7697 -> 0.8872 -> 0.9490 -> 0.9729 -> 0.9844,  LUON DUOI 1
Khoang cach toi 1 chi co lai he so ~0.55 moi lan gap doi so vong, on dinh qua ba lan do,
nen ngoai suy can >2500 vong (~10 gio moi loi giai) va VAN duoi 1. Doi chieu: vo 132 dat
PoA = 1.0265 ngay tu 20 vong, vo 264 dat 1.0060 tu 40 vong.

Ket luan khong phai "chay lau hon thi co so dung" ma la: **o quy mo nay khong co tham
chieu can bang dang tin**, nen moi dai luong chia cho UE (recovered, blind/UE, speedup
vs UE) mat mau so.

⭐ Nhung tuyen bo NANG NHAT cua bai o vo nay khong can UE:
    "on the largest shell the blind split comes out ahead"
Do la THU HANG giua hai chinh sach, ca hai deu do truc tiep. Script nay do dung nhung
thu do va khong hon:

    - TTT tuyet doi cua blind / GNN(tau) / eps-ECMP
    - ti so so voi blind (blind = 1.00 theo dinh nghia, khong can UE)
    - THU HANG: chinh sach nao thap nhat o tung seed
    - thoi gian suy dien tung chang

Re hon r4_1 khoang 30 lan vi khong giai MSA lan nao.
"""
import argparse
import csv
import os
import statistics as st
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
          "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(v, "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

import torch                                                          # noqa: E402
from constellation import Walker                                      # noqa: E402
from traffic import multipath_route, route_and_measure                # noqa: E402
from p5_gnn_router import (make_instance, train, TRAIN_WALKER,        # noqa: E402
                           TRAIN_PAIRS, CAP)
from r2_7_warmstart_ecmp import ecmp_ttt                              # noqa: E402

SHELL = ("w1584_i53", Walker(1584, 72, 1, 53.0, 550.0), 7200)
# ⛔ Luoi phai noi cho toi khi toi uu nam BEN TRONG. Ban 8.0 co toi uu o bien 8.0;
# noi toi 128.0 thi toi uu van o bien 128.0 tren CA BA seed. Nen phai noi tiep. Con so
# lay o bien la CHAN DUOI, khong duoc trich nhu mot gia tri da do duoc.
TAUS = [0.05, 0.10, 0.20, 0.35, 0.50, 1.00, 2.00, 3.50, 5.00, 8.00,
        16.0, 32.0, 64.0, 128.0, 256.0, 512.0, 1024.0]
EPSS = [0.05, 0.10, 0.20, 0.35, 0.50, 0.75]
OUTDIR = os.path.join(ROOT, "results")
BASE = "r5_4_shell1584_uefree"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    a = ap.parse_args()

    name, w, npairs = SHELL
    print("=" * 78)
    print("  R5.4 -- vo %s, KHONG dung can bang lam moc" % name)
    print("=" * 78, flush=True)

    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False)
          for i in range(10)]
    model = train("GCN", tr, seed=0)

    rows = []
    for seed in a.seeds:
        t0 = time.time()
        ins = make_instance(w, npairs, 900 + seed, need_eig=False)
        A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]

        t = time.time()
        with torch.no_grad():
            g = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()
        t_forward = time.time() - t
        rc = W.copy()
        rc[ins["rows"], ins["cols"]] = W[ins["rows"], ins["cols"]] * (1 + g)

        blind = route_and_measure(A, W, dem, CAP, W)["total_ttt"]
        row = {"shell": name, "n_sat": w.T, "seed": seed,
               "unit_of_analysis": "vo-x-seed", "blind_ttt": round(blind, 4),
               "t_forward_s": round(t_forward, 4)}

        best_gnn, best_tau = float("inf"), None
        for x in TAUS:
            t = time.time()
            v = multipath_route(A, W, rc, dem, CAP, tau=x)["total_ttt"]
            row["ttt_gnn_tau%g" % x] = round(v, 4)
            row["rel_gnn_tau%g" % x] = round(v / blind, 4)
            if x == 0.20:
                row["t_decode_s"] = round(time.time() - t, 4)
            if v < best_gnn:
                best_gnn, best_tau = v, x

        best_ecmp, best_eps = float("inf"), None
        for e in EPSS:
            v = ecmp_ttt(A, W, dem, CAP, eps=e)
            row["ttt_ecmp_eps%g" % e] = round(v, 4)
            row["rel_ecmp_eps%g" % e] = round(v / blind, 4)
            if v < best_ecmp:
                best_ecmp, best_eps = v, e

        # ⭐ THU HANG la tuyen bo cua bai o vo nay, va no khong can UE
        row.update(best_gnn_ttt=round(best_gnn, 4), best_gnn_tau=best_tau,
                   best_ecmp_ttt=round(best_ecmp, 4), best_ecmp_eps=best_eps,
                   rel_best_gnn=round(best_gnn / blind, 4),
                   rel_best_ecmp=round(best_ecmp / blind, 4),
                   winner="ecmp" if best_ecmp < best_gnn else "gnn",
                   margin_pct=round(100 * abs(best_gnn - best_ecmp)
                                    / min(best_gnn, best_ecmp), 3),
                   tau_at_grid_edge=int(best_tau == TAUS[-1]))
        rows.append(row)
        print("  seed %d: %.0fs | blind %.0f | GNN tot %.4f o tau=%g | "
              "ECMP tot %.4f o eps=%g | THANG: %s (cach %.2f%%)"
              % (seed, time.time() - t0, blind, row["rel_best_gnn"], best_tau,
                 row["rel_best_ecmp"], best_eps, row["winner"], row["margin_pct"]),
              flush=True)

    # ⛔ Ten tep mang SEED: ba tien trinh song song tung cung ghi mot duong dan va de
    # len nhau, CSV chi con 1/3 seed. Chay mot tien trinh nhieu seed thi ten khong co hau to.
    tag = "" if len(a.seeds) > 1 else "_seed%d" % a.seeds[0]
    OUT = os.path.join(OUTDIR, BASE + tag + ".csv")
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    wins = [r["winner"] for r in rows]
    print()
    print("  THU HANG tren %d seed: ecmp thang %d, gnn thang %d"
          % (len(rows), wins.count("ecmp"), wins.count("gnn")))
    print("  ti so so voi blind (trung vi): GNN %.4f | blind-mp %.4f"
          % (st.median(r["rel_best_gnn"] for r in rows),
             st.median(r["rel_best_ecmp"] for r in rows)))
    edge = sum(r["tau_at_grid_edge"] for r in rows)
    if edge:
        print("  ⚠ %d/%d seed co toi uu tau NAM O BIEN luoi (%g): con so la CHAN DUOI"
              % (edge, len(rows), TAUS[-1]))
    else:
        print("  ✅ toi uu tau nam BEN TRONG luoi o moi seed")
    print("  => da ghi results/%s" % os.path.basename(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
