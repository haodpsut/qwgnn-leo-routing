"""R6.0 -- do LECH GIUA HAI MAY co kiem soat, va tach rieng phan KHONG di qua torch.

    python experiments/r6_0_host_control.py --tag vps
    python experiments/r6_0_host_control.py --tag mac

Ghi ra `results/r6_0_host_control_<tag>.csv`. Chay tren tung may roi so hai tep.

⛔ VI SAO PHAI CO SCRIPT RIENG THAY VI SO HAI THU MUC KET QUA. Ban truoc lay lam bang chung
cho tuyen bo "lech giua hai may" bang cach so `/tmp/res_before` voi `results/`. Doi chieu
27/08/2026 cho thay khong dung duoc:

  - CA HAI thu muc deu mang nhan `Linux-x86_64-sol1`, tuc khong co bo nao la bo cua may Mac;
  - so o lech la 1094/3345, trong khi ghi chep noi bo ghi 17/2999 cho phep so sanh hai may.
    Hai con so cach nhau hai bac ⇒ hai thu muc do khac nhau vi mot ly do KHAC, gan nhu chac
    chan la doi ma nguon (san MSA 20 -> 40) chu khong phai doi may.

Nghia la ban cu do "hai lan chay khac nhau" roi goi ten no la "hai may khac nhau". Xuat xu
tung o deu dung; cai sai la NHAN dat cho phep do. Xem [[feedback-tiem-so-gia-de-thu-cong]].

MOT PHEP DO HAI MAY CHI DUNG KHI GIU CO DINH: cung commit, cung seed, cung tham so, cung
thu tu; chi doi MAY. Script nay ep ca bon:

  - in `git rev-parse HEAD` vao TUNG DONG, nen hai tep khac commit se lo ra ngay;
  - seed va cau hinh dat cung mot cho, khong doc bien moi truong;
  - ghi ca `platform` va `numpy/torch` version, vi day la cac nghi pham that su.

VA NO TACH HAI NHOM DAI LUONG, vi day moi la dieu bai muon khai:

  nhom A (KHONG cham torch): duong di ngan nhat, MSA, TTT cua blind/UE/SO
  nhom B (co torch):         forward cua GNN va moi thu bat nguon tu no

Bai dang khai "moi dai luong khong di qua mang deu khop toi chu so in ra". Do la mot tuyen
bo ve nhom A, va no phai duoc do RIENG tren nhom A chu khong suy ra tu mot phep so gop.
"""
import argparse
import csv
import hashlib
import os
import platform
import subprocess
import sys

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
          "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[v] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

import numpy as np                                                    # noqa: E402
import torch                                                          # noqa: E402
from constellation import Walker                                      # noqa: E402
from traffic import evaluate                                          # noqa: E402
from p5_gnn_router import (make_instance, train, TRAIN_WALKER,        # noqa: E402
                           TRAIN_PAIRS, CAP)

# Co dinh o day, KHONG doc bien moi truong: mot phep do hai may ma mot ben lay tham so tu
# moi truong thi khong con la phep do hai may nua.
SHELLS = [("w132_i53", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264_i53", Walker(264, 24, 1, 53.0, 550.0), 1200)]
SEEDS = [0, 1, 2]


# ⛔ KHONG dua vao git de ghim ma nguon. Ban tren VPS nam trong mot clone nen `git rev-parse`
# tra ve commit; ban tren Mac thi thu muc code/ khong phai kho git nen no tra ve
# "(khong phai git repo)", va phep so hai may tu choi chay -- dung luc no can chay nhat.
# Bam NOI DUNG cac tep that su quyet dinh ket qua thi dung tren ca hai may, va con chat hon
# git: no bat ca sua chua chua commit.
SRC = ("sim/traffic.py", "sim/constellation.py", "experiments/p5_gnn_router.py",
       "experiments/r6_0_host_control.py")


def code_sha():
    h = hashlib.sha256()
    for rel in SRC:
        p = os.path.join(ROOT, rel)
        h.update(rel.encode())
        h.update(open(p, "rb").read() if os.path.exists(p) else b"<THIEU>")
    return h.hexdigest()[:12]


def head():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "(khong phai git repo)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="ten may, vi du vps hoac mac")
    a = ap.parse_args()

    commit = head()
    sha = code_sha()
    env = "%s-%s | numpy %s | torch %s" % (platform.system(), platform.machine(),
                                           np.__version__, torch.__version__)
    print("=" * 78)
    print("  R6.0 host control | tag=%s | commit=%s | code_sha=%s" % (a.tag, commit, sha))
    print("  %s" % env)
    print("=" * 78, flush=True)

    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False)
          for i in range(10)]
    model = train("GCN", tr, seed=0)

    rows = []
    for name, wk, npairs in SHELLS:
        for seed in SEEDS:
            ins = make_instance(wk, npairs, 900 + seed, need_eig=False)
            A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]

            # ---- nhom A: khong cham torch mot dong nao ----
            blind = evaluate(A, W, dem, CAP, policy="blind")["total_ttt"]
            ue_r = evaluate(A, W, dem, CAP, policy="ue")
            so = evaluate(A, W, dem, CAP, policy="so")["total_ttt"]

            # ---- nhom B: di qua torch ----
            with torch.no_grad():
                g = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()

            rows.append({
                "tag": a.tag, "commit": commit, "code_sha": sha, "env": env,
                "shell": name, "seed": seed, "unit_of_analysis": "vo-x-seed",
                # nhom A -- in DU chu so, khong lam tron: mot phep do ve "khop toi chu so
                # in ra" ma tu lam tron truoc khi so thi da tra loi san cau hoi cua no.
                "A_blind_ttt": repr(blind),
                "A_ue_ttt": repr(ue_r["total_ttt"]),
                "A_so_ttt": repr(so),
                "A_poa": repr(ue_r["total_ttt"] / so),
                "A_msa_iters": ue_r["msa_iters"],
                # nhom B
                "B_g_sum": repr(float(g.sum())),
                "B_g_max": repr(float(g.max())),
            })
            print("  %-10s seed %d | A: blind %.6f ue %.6f so %.6f (PoA %.6f, %d vong) | "
                  "B: sum(g) %.6f" % (name, seed, blind, ue_r["total_ttt"], so,
                                      ue_r["total_ttt"] / so, ue_r["msa_iters"],
                                      float(g.sum())), flush=True)

    out = os.path.join(ROOT, "results", "r6_0_host_control_%s.csv" % a.tag)
    with open(out, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    print("  => da ghi results/%s" % os.path.basename(out))
    print("  So hai may: python experiments/r6_1_host_compare.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
