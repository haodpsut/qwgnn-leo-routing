"""R5.0b -- MOT loi giai can bang, mot tien trinh. Don vi de chay song song tren VPS.

Ban tuan tu `r5_0_msa_convergence_pilot.py` quet thang 20-40-80-160-320 trong mot tien
trinh: uoc tren may Mac la ~4 gio cho MOT seed. Nhung cac nac hoan toan DOC LAP voi nhau
(moi nac giai lai tu dau), va VPS co 80 nhan, nen tach moi (so-vong, chinh-sach) thanh
mot tien trinh rieng thi tong thoi gian bang nac DAT NHAT chu khong phai tong cac nac.

    python r5_0b_one_solve.py --iters 80 --policy ue --seed 0

⛔ PHAI ep OMP_NUM_THREADS=1 o phia goi. Mac dinh moi tien trinh numpy mo toi 80 luong;
muoi tien trinh la 800 luong tranh 80 nhan va CHAM HON chay tuan tu. Da ghi trong
reference-vps-sol1-swinburne.

In dung MOT dong CSV ra stdout de gom lai de dang.
"""
import argparse
import os
import sys
import time

# ⛔ Dat TRUOC khi numpy duoc nap, nen phai o day chu khong phai trong ham main.
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
          "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(v, "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                        # noqa: E402
from traffic import evaluate, route_and_measure         # noqa: E402
from p5_gnn_router import make_instance, CAP            # noqa: E402

SHELL = Walker(1584, 72, 1, 53.0, 550.0)
NPAIRS = 7200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, required=True)
    ap.add_argument("--policy", choices=["ue", "so", "blind"], required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    t0 = time.time()
    ins = make_instance(SHELL, NPAIRS, 900 + a.seed, need_eig=False)
    A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]
    if a.policy == "blind":
        ttt = route_and_measure(A, W, dem, CAP, W)["total_ttt"]
    else:
        ttt = evaluate(A, W, dem, CAP, policy=a.policy, iters=a.iters)["total_ttt"]
    print("%d,%s,%d,%.4f,%.1f" % (a.seed, a.policy, a.iters, ttt, time.time() - t0),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
