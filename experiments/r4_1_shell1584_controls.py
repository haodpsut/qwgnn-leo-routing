"""R4.1: cac DOI CHUNG con thieu tai vo 1584, la vo cho con so headline cua bai.

PHAN BIEN NGOAI, 17/08/2026, hai y 2.1a va 2.1b:
    "The 1584-satellite shell, the paper's headline transfer result, is absent from the
     temperature sweep (Fig. 9) and from Table X; yet the abstract reports 0.94 without the
     mandatory correction."
    "The blind multipath baseline was never run on 1584. The paper's own trend
     (0.668 -> 0.976 -> 0.973) predicts parity or worse for the learned field there."

Y kien nay dung, va no dung theo kieu kho chiu nhat: bai TU PHAT HIEN ra rang giu nhiet do co
dinh la dang do BO GIAI MA chu khong do mo hinh (muc VI-I), roi bao con so 1584 o dung tau=0.2
co dinh, khong quet. Con so to nhat cua bai la con so duy nhat khong duoc ap luat cua chinh bai.

Va xu huong cua chinh bai da noi truoc ket qua: baseline mu manh len theo co vo (0.668 tren
132, 0.976 tren 198, 0.973 tren 264) vi luoi lon cho nhieu duong vong gan-ngan-nhat hon. Ngoai
suy tu do thi o 1584 baseline mu rat co the NGANG hoac HON. Neu dung thi tuyen bo chuyen giao
cua bai mat not chan cuoi.

Chay CA HAI trong MOT luot, vi ca hai deu can chung loi giai UE va SO, von la phan dat nhat o
quy mo nay (UE ~ 29x thoi gian suy dien 8.4s theo Bang VIII, tuc vai phut moi instance).

KHONG dat truoc ket qua nao la "thanh cong". Ket qua co the la baseline mu thang, va neu vay thi
do la ket qua phai bao.
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

from constellation import Walker                                    # noqa: E402
from traffic import evaluate, multipath_route, route_and_measure     # noqa: E402
from p5_gnn_router import (make_instance, train, TRAIN_WALKER,       # noqa: E402
                           TRAIN_PAIRS, CAP)
from r2_7_warmstart_ecmp import ecmp_ttt                             # noqa: E402

# Cung luoi tau va eps voi r2_7_fair_tuned_wide.py, de so sanh duoc thang voi cac vo kia.
TAUS = [0.05, 0.10, 0.20, 0.35, 0.50, 1.00, 2.00, 3.50, 5.00, 8.00]
EPSS = [0.05, 0.10, 0.20, 0.35, 0.50, 0.75]
DEFAULT_TAU = 0.20
SHELL = ("w1584_i53", Walker(1584, 72, 1, 53.0, 550.0), 7200)
SEEDS = [0, 1, 2]
OUT = os.path.join(ROOT, "results", "r4_1_shell1584_controls.csv")


def main():
    name, w, npairs = SHELL
    print(f"R4.1 -- doi chung con thieu tai {name} ({w.T} ve tinh, {npairs} cap nhu cau)")
    print("   quet tau + baseline blind multipath, 3 seed. Cham vi UE/SO o quy mo nay.\n",
          flush=True)

    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False) for i in range(10)]
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
        ue = evaluate(A, W, dem, CAP, policy="ue")["total_ttt"]
        so = evaluate(A, W, dem, CAP, policy="so")["total_ttt"]
        span = blind - ue
        # Chan vat ly: SO phai <= UE. O 1584 no BI VI PHAM (PoA = 0.75), va do la DU LIEU chu
        # khong phai su co: no noi rang MSA 20 vong chua hoi tu o quy mo nay. Lan dau toi de
        # assert lam sap chuong trinh, tuc la vut di chinh phat hien do. Nay GHI NHAN roi chay
        # tiep, vi thuoc do cua bai (recovered) chi can blind va UE.
        poa_ok = so <= ue + 1e-6
        if not poa_ok:
            print(f"  ⚠ seed {seed}: SO={so:.1f} > UE={ue:.1f}, PoA={ue/so:.4f} < 1. "
                  f"MSA 20 vong CHUA HOI TU o quy mo nay.", flush=True)
        assert span > 0, "blind khong te hon UE: instance nay khong co gi de thu hoi"
        rec = lambda x: (blind - x) / span

        row = {"shell": name, "n_sat": w.T, "seed": seed, "unit_of_analysis": "vo-x-seed",
               "blind_ttt": round(blind, 4), "ue_ttt": round(ue, 4), "so_ttt": round(so, 4),
               # Y 2.4 cua phan bien: 'recovered' nen tai khi blind benh hoan. Ghi luon TY LE
               # blind/UE de doc gia biet mau so to co nao, va ty le chinh-sach/UE de biet
               # 'thu hoi 0.94' nghia la con cach can bang bao xa.
               "blind_over_ue": round(blind / ue, 2), "poa_violated": int(not poa_ok)}
        for t in TAUS:
            v = multipath_route(A, W, rc, dem, CAP, tau=t)["total_ttt"]
            if poa_ok:
                assert v >= so - 1e-6, f"gnn tau={t}: {v:.3f} duoi system optimum {so:.3f}"
            row[f"recovered_gnn_tau{t}"] = round(rec(v), 4)
            row[f"ratio_ue_gnn_tau{t}"] = round(v / ue, 2)
        for e in EPSS:
            v = ecmp_ttt(A, W, dem, CAP, eps=e)
            if poa_ok:
                assert v >= so - 1e-6, f"ecmp eps={e}: {v:.3f} duoi system optimum {so:.3f}"
            row[f"recovered_ecmp_eps{e}"] = round(rec(v), 4)
            row[f"ratio_ue_ecmp_eps{e}"] = round(v / ue, 2)
        rows.append(row)
        print(f"  seed {seed}: xong sau {time.time()-t0:.0f}s | "
              f"gnn(tau=0.2)={row['recovered_gnn_tau0.2']:.3f} "
              f"gnn(tot)={max(row[f'recovered_gnn_tau{t}'] for t in TAUS):.3f} "
              f"ecmp(tot)={max(row[f'recovered_ecmp_eps{e}'] for e in EPSS):.3f}", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    mt = {t: st.median(r[f"recovered_gnn_tau{t}"] for r in rows) for t in TAUS}
    me = {e: st.median(r[f"recovered_ecmp_eps{e}"] for r in rows) for e in EPSS}
    bt = max(TAUS, key=lambda t: mt[t])
    be = max(EPSS, key=lambda e: me[e])

    print("=== 2.1a: nhiet do co quan trong o 1584 khong? ===")
    print(f"{'tau':>6} " + " ".join(f"{t:g}".rjust(7) for t in TAUS))
    print(f"{'gnn':>6} " + " ".join(f"{mt[t]:7.3f}" for t in TAUS))
    print(f"  tot nhat tai tau={bt:g} ({mt[bt]:.3f}); tau=0.2 dung trong bai cho {mt[DEFAULT_TAU]:.3f}, "
          f"kem {mt[DEFAULT_TAU]-mt[bt]:+.3f}")
    if bt >= TAUS[-1]:
        print("  ⚠ CUC DAI NAM O BIEN cua luoi: phai noi rong luoi tau, chua ket luan duoc.")

    print("\n=== 2.1b: baseline mu o 1584 ===")
    print(f"{'eps':>6} " + " ".join(f"{e:g}".rjust(7) for e in EPSS))
    print(f"{'ecmp':>6} " + " ".join(f"{me[e]:7.3f}" for e in EPSS))
    print(f"  tot nhat tai eps={be:g} ({me[be]:.3f})")

    # Thong ke GHEP CAP theo tung don vi, khong phai hieu cua hai trung vi.
    # Bai da mot lan doc nham 0.309 vs 0.317 vi dung hieu-cua-trung-vi.
    diffs = [r[f"recovered_gnn_tau{bt}"] - r[f"recovered_ecmp_eps{be}"] for r in rows]
    wins = sum(d > 0 for d in diffs)
    print(f"\n=== ca hai ben cung duoc chinh, ghep cap theo don vi ===")
    print(f"  gnn(tau*={bt:g})={mt[bt]:.3f}  vs  ecmp(eps*={be:g})={me[be]:.3f}")
    print(f"  trung vi cua HIEU theo tung don vi: {st.median(diffs):+.3f}   thang {wins}/{len(diffs)}")
    print(f"  hieu cua hai trung vi (KHONG dung de bao cao): {mt[bt]-me[be]:+.3f}")

    print("\n=== 2.4: 'thu hoi 0.94' o day nghia la cach can bang bao xa? ===")
    print(f"  blind te hon UE {st.median(r['blind_over_ue'] for r in rows):.0f} lan tren vo nay.")
    print(f"{'tau':>6} " + " ".join(f"{t:g}".rjust(7) for t in TAUS))
    print(f"{'x UE':>6} " + " ".join(
        f"{st.median(r[f'ratio_ue_gnn_tau{t}'] for r in rows):7.1f}" for t in TAUS))
    nviol = sum(r["poa_violated"] for r in rows)
    if nviol:
        print(f"\n  ⚠ {nviol}/{len(rows)} instance co PoA < 1: MSA 20 vong chua hoi tu o 1584.")
        print("    Moi con so dung UE lam quy chieu o quy mo nay deu keo theo su khong chac do.")

    print("\n=== KET LUAN ===")
    print(f"  Voi n={len(SEEDS)} seed, khong mot dau hieu nao o day du suc tach khoi hoa. Con so "
          f"can doc\n  la HUONG va DO LON, va ca hai deu phai vao bai du chung noi gi.")
    if st.median(diffs) <= 0:
        print("  ⚠ BASELINE MU KHONG THUA o 1584. Tuyen bo chuyen giao cua bai mat chan cuoi:\n"
              "    phai rut, khong phai lam nhe di.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
