"""R5.1 -- chay lai vo 1584 voi loi giai can bang DA HOI TU, va noi dai luoi tau.

Gop HAI viec cua nguoi doc ngoai 27/08 vao MOT luot, vi ca hai dung chung phan dat nhat
(dung instance 1584 va giai UE/SO tren no):

  (1) "the twenty-iteration solve supplying our equilibrium reference has not converged:
      the price of anarchy comes out below one on all three instances, which is
      impossible ... yet continued publishing the unconverged values"
  (2) "the tau optimum sits at the edge of our grid, so 0.980 is a lower bound"

So vong dung o day KHONG duoc go tay: truyen bang --iters, lay tu ket luan cua
`r5_0_msa_convergence_pilot.py`. Chay ma quen truyen thi script DUNG, khong tu chon.

⛔ IN CA HAI CANH NHAU. Moi dong ghi ca gia tri o 20 vong (nhu da cong bo) va o so vong
da hoi tu, cung ti so giua chung. Bai can bao "so cu sai bao nhieu", khong chi thay so
moi: chinh nguoi doc ngoai da tinh ra blind se thanh 1179x UE thay vi 786x, va hoc duoc
o tau tot nhat thanh 24,0x thay vi 16,0x. Phai kiem con so do bang du lieu cua ta.

⛔ RANG BUOC VAT LY LA CONG, KHONG PHAI GHI CHU. O 20 vong, PoA<1 tung duoc ghi nhan roi
cho chay tiep. Voi so vong da hoi tu thi PoA<1 la LOI: script dung han. Neu no dung, ket
luan dung khong phai "ha nguong" ma la "o quy mo nay MSA khong hoi tu trong tam chi phi",
va khi do moi tuyen bo quy chieu ve can bang o vo 1584 phai RUT chu khong phai sua so.
"""
import argparse
import csv
import os
import statistics as st
import sys
import time

import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                     # noqa: E402
from traffic import evaluate, multipath_route, route_and_measure     # noqa: E402
from p5_gnn_router import make_instance, train, TRAIN_WALKER, TRAIN_PAIRS, CAP  # noqa: E402
from r2_7_warmstart_ecmp import ecmp_ttt                             # noqa: E402

# Luoi cu dung toi 8.0 va toi uu o vo 1584 NAM O DO, tuc o bien. Noi dai theo cap so nhan
# cho toi khi toi uu nam BEN TRONG; neu no van o bien 128 thi bao va khong ket luan.
TAUS = [0.05, 0.10, 0.20, 0.35, 0.50, 1.00, 2.00, 3.50, 5.00, 8.00,
        16.0, 32.0, 64.0, 128.0]
EPSS = [0.05, 0.10, 0.20, 0.35, 0.50, 0.75]
OLD_ITERS = 20                       # so vong cua ban da cong bo
SHELL = ("w1584_i53", Walker(1584, 72, 1, 53.0, 550.0), 7200)
SEEDS = [0, 1, 2]
OUT = os.path.join(ROOT, "results", "r5_1_shell1584_converged.csv")


def solve_pair(A, W, dem, iters):
    ue = evaluate(A, W, dem, CAP, policy="ue", iters=iters)["total_ttt"]
    so = evaluate(A, W, dem, CAP, policy="so", iters=iters)["total_ttt"]
    return ue, so


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, required=True,
                    help="so vong MSA da hoi tu, lay tu ket luan cua r5_0")
    a = ap.parse_args()

    name, w, npairs = SHELL
    print("=" * 78)
    print("  R5.1 -- vo %s, loi giai can bang %d vong (cu: %d vong)"
          % (name, a.iters, OLD_ITERS))
    print("=" * 78, flush=True)

    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False)
          for i in range(10)]
    model = train("GCN", tr, seed=0)

    rows = []
    for seed in SEEDS:
        t0 = time.time()
        ins = make_instance(w, npairs, 900 + seed, need_eig=False)
        A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]
        with torch.no_grad():
            g = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()
        rc = W.copy()
        rc[ins["rows"], ins["cols"]] = W[ins["rows"], ins["cols"]] * (1 + g)

        blind = route_and_measure(A, W, dem, CAP, W)["total_ttt"]
        ue_old, so_old = solve_pair(A, W, dem, OLD_ITERS)
        ue, so = solve_pair(A, W, dem, a.iters)

        if so > ue + 1e-6:
            print("\n  ⛔ DUNG: o %d vong PoA=%.4f VAN duoi 1 (SO=%.1f > UE=%.1f)."
                  % (a.iters, ue / so, so, ue))
            print("     Khong duoc ha nguong. O quy mo nay MSA chua hoi tu trong tam chi")
            print("     phi, nen moi tuyen bo quy chieu ve can bang o vo nay phai RUT.")
            return 1

        span, span_old = blind - ue, blind - ue_old
        assert span > 0, "blind khong te hon UE"
        rec = lambda x: (blind - x) / span
        rec_old = lambda x: (blind - x) / span_old

        row = {"shell": name, "n_sat": w.T, "seed": seed,
               "unit_of_analysis": "vo-x-seed",
               "iters_converged": a.iters, "iters_old": OLD_ITERS,
               "blind_ttt": round(blind, 4),
               "ue_ttt": round(ue, 4), "so_ttt": round(so, 4),
               "ue_ttt_old": round(ue_old, 4), "so_ttt_old": round(so_old, 4),
               "poa": round(ue / so, 4), "poa_old": round(ue_old / so_old, 4),
               "ue_shift_pct": round(100 * (ue_old - ue) / ue, 2),
               "blind_over_ue": round(blind / ue, 2),
               "blind_over_ue_old": round(blind / ue_old, 2)}
        for t in TAUS:
            v = multipath_route(A, W, rc, dem, CAP, tau=t)["total_ttt"]
            assert v >= so - 1e-6, "gnn tau=%s duoi system optimum" % t
            row["recovered_gnn_tau%s" % t] = round(rec(v), 4)
            row["recovered_gnn_old_tau%s" % t] = round(rec_old(v), 4)
            row["ratio_ue_gnn_tau%s" % t] = round(v / ue, 2)
        for e in EPSS:
            v = ecmp_ttt(A, W, dem, CAP, eps=e)
            assert v >= so - 1e-6, "ecmp eps=%s duoi system optimum" % e
            row["recovered_ecmp_eps%s" % e] = round(rec(v), 4)
            row["recovered_ecmp_old_eps%s" % e] = round(rec_old(v), 4)
            row["ratio_ue_ecmp_eps%s" % e] = round(v / ue, 2)
        rows.append(row)
        bt = max(TAUS, key=lambda t: row["recovered_gnn_tau%s" % t])
        print("  seed %d: %.0fs | PoA %.4f (cu %.4f) | UE doi %+.1f%% | "
              "gnn tot %.3f o tau=%g | ecmp tot %.3f"
              % (seed, time.time() - t0, row["poa"], row["poa_old"],
                 row["ue_shift_pct"], row["recovered_gnn_tau%s" % bt], bt,
                 max(row["recovered_ecmp_eps%s" % e] for e in EPSS)), flush=True)

    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    med = lambda k: st.median(r[k] for r in rows)
    bt = max(TAUS, key=lambda t: med("recovered_gnn_tau%s" % t))
    be = max(EPSS, key=lambda e: med("recovered_ecmp_eps%s" % e))
    print()
    print("  tham chieu can bang doi %+.1f%% (trung vi)" % med("ue_shift_pct"))
    print("  blind/UE : %.1f  (cu %.1f)" % (med("blind_over_ue"), med("blind_over_ue_old")))
    print("  GNN tot nhat : %.3f o tau=%g   (thuoc do cu: %.3f)"
          % (med("recovered_gnn_tau%s" % bt), bt, med("recovered_gnn_old_tau%s" % bt)))
    print("  blind tot nhat: %.3f o eps=%g  (thuoc do cu: %.3f)"
          % (med("recovered_ecmp_eps%s" % be), be, med("recovered_ecmp_old_eps%s" % be)))
    if bt == TAUS[-1]:
        print("  ⚠ toi uu tau VAN nam o bien luoi (%g): con so tren la CHAN DUOI." % bt)
    else:
        print("  ✅ toi uu tau nam BEN TRONG luoi, khong con la chan duoi.")
    print("  => da ghi results/%s" % os.path.basename(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
