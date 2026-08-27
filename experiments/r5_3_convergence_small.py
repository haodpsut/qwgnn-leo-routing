"""R5.3 -- MSA co hoi tu o vo 132 va 264 khong? Cau hoi quan trong hon ca vo 1584.

⛔ VI SAO PHAI HOI. Vo 1584 da do duoc: PoA bo 0.7697 -> 0.8872 -> 0.9490 -> 0.9729 theo
20/40/80/160 vong, khoang cach toi 1 co lai he so 0.53 moi lan gap doi, tuc KHONG co so
vong kha thi nao dua no toi 1. Ket luan: vo do khong co tham chieu can bang dang tin.

Nhung MOI TUYEN BO CHINH cua bai nam o vo 132 va 264, va chung cung dung MSA 20 vong.
Neu 20 vong cung chua du o do thi van de khong phai "mot vo bi hong" ma la "thuoc do
`recovered` cua ca bai dung mot mau so chua hoi tu".

Do la cau hoi phai tra loi TRUOC khi quyet dinh rut cai gi. Va no RE: hai vo nay nho hon
nhieu (100-1600 cap nhu cau so voi 7200), nen ca thang chay trong vai phut.

Tieu chi, chot truoc khi nhin so, giong het r5_0:
    (1) PoA = UE/SO >= 1                      -- rang buoc VAT LY
    (2) UE doi < 0.5% giua hai muc lien tiep   -- da on dinh
"""
import csv
import os
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
          "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(v, "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                # noqa: E402
from traffic import evaluate, route_and_measure                 # noqa: E402
from p5_gnn_router import make_instance, CAP                    # noqa: E402

SHELLS = [("w132_i53", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264_i53", Walker(264, 24, 1, 53.0, 550.0), 1200)]
LADDER = [20, 40, 80, 160, 320, 640]
SEEDS = [0, 1, 2]
TOL = 0.005
OUT = os.path.join(ROOT, "results", "r5_3_convergence_small.csv")


def main():
    rows = []
    print("=" * 78)
    print("  R5.3 -- MSA hoi tu o vo NHO (noi moi tuyen bo chinh cua bai nam)")
    print("=" * 78, flush=True)
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            ins = make_instance(w, npairs, 900 + seed, need_eig=False)
            A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]
            blind = route_and_measure(A, W, dem, CAP, W)["total_ttt"]
            prev = None
            print("\n  %s seed %d  (blind = %.1f)" % (name, seed, blind), flush=True)
            print("  %6s | %12s %12s %8s | %8s" % ("vong", "UE", "SO", "PoA", "dUE"))
            for it in LADDER:
                t0 = time.time()
                ue = evaluate(A, W, dem, CAP, policy="ue", iters=it)["total_ttt"]
                so = evaluate(A, W, dem, CAP, policy="so", iters=it)["total_ttt"]
                d = abs(ue - prev) / prev if prev else float("nan")
                print("  %6d | %12.2f %12.2f %8.4f | %7.3f%%  (%.0fs)"
                      % (it, ue, so, ue / so, 100 * d if prev else float("nan"),
                         time.time() - t0), flush=True)
                rows.append(dict(shell=name, n_sat=w.T, seed=seed, pairs=npairs,
                                 iters=it, blind_ttt=round(blind, 4),
                                 ue_ttt=round(ue, 4), so_ttt=round(so, 4),
                                 poa=round(ue / so, 6),
                                 d_ue_pct=round(100 * d, 4) if prev else "",
                                 blind_over_ue=round(blind / ue, 3)))
                prev = ue

    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    print("\n" + "=" * 78)
    print("  KET LUAN theo tieu chi da chot (PoA >= 1 VA dUE < 0.5%)")
    print("=" * 78)
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            s = [r for r in rows if r["shell"] == name and r["seed"] == seed]
            ok = [r for r in s if r["poa"] >= 1.0 - 1e-9
                  and r["d_ue_pct"] != "" and r["d_ue_pct"] < 0.5]
            best = min(s, key=lambda r: abs(r["poa"] - 1))
            print("  %-10s seed %d: %s | PoA gan 1 nhat = %.4f o %d vong"
                  % (name, seed,
                     ("hoi tu tu %d vong" % ok[0]["iters"]) if ok else "⛔ KHONG hoi tu",
                     best["poa"], best["iters"]))
    print("  => da ghi results/%s" % os.path.basename(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
