"""R5.1b -- MOT don vi cong viec cua vo 1584: mot seed, mot viec. De chay song song.

Ban `r5_1_shell1584_converged.py` chay ba seed TUAN TU trong mot tien trinh, tuc thoi
gian bang 3x mot seed. Cac seed doc lap voi nhau, va lua giai UE / SO trong mot seed
cung doc lap, nen tren 80 nhan phai tach ra. Bai hoc tu chinh pilot: ban tuan tu uoc 4
gio cho MOT seed tren Mac, ban song song lam CA THANG trong 81 phut tren VPS.

    python r5_1b_unit.py --seed 0 --job ue    --iters 160
    python r5_1b_unit.py --seed 0 --job so    --iters 160
    python r5_1b_unit.py --seed 0 --job blind
    python r5_1b_unit.py --seed 0 --job gnn --tau 8.0
    python r5_1b_unit.py --seed 0 --job ecmp --eps 0.2

Moi lenh in DUNG MOT dong CSV: seed,job,param,iters,ttt,giay. Gom lai bang r5_1c_join.py.

⛔ KHONG script nao o day tu quyet dinh so vong. `--iters` bat buoc cho ue/so.
⛔ Rang buoc vat ly (SO <= UE, va moi chinh sach >= SO) duoc kiem o BUOC GOM, vi mot don
vi khong nhin thay cac don vi khac. Kiem o day thi khong kiem duoc gi.
"""
import argparse
import os
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
from traffic import evaluate, multipath_route, route_and_measure      # noqa: E402
from p5_gnn_router import (make_instance, train, TRAIN_WALKER,        # noqa: E402
                           TRAIN_PAIRS, CAP)
from r2_7_warmstart_ecmp import ecmp_ttt                              # noqa: E402

SHELL = Walker(1584, 72, 1, 53.0, 550.0)
NPAIRS = 7200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--job", choices=["ue", "so", "blind", "gnn", "ecmp"], required=True)
    ap.add_argument("--iters", type=int)
    ap.add_argument("--tau", type=float)
    ap.add_argument("--eps", type=float)
    a = ap.parse_args()
    if a.job in ("ue", "so") and not a.iters:
        ap.error("--iters bat buoc cho ue/so; lay tu ket luan cua r5_0")
    if a.job == "gnn" and a.tau is None:
        ap.error("--tau bat buoc cho gnn")
    if a.job == "ecmp" and a.eps is None:
        ap.error("--eps bat buoc cho ecmp")

    t0 = time.time()
    ins = make_instance(SHELL, NPAIRS, 900 + a.seed, need_eig=False)
    A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]

    if a.job == "blind":
        ttt, param = route_and_measure(A, W, dem, CAP, W)["total_ttt"], ""
    elif a.job in ("ue", "so"):
        ttt = evaluate(A, W, dem, CAP, policy=a.job, iters=a.iters)["total_ttt"]
        param = ""
    elif a.job == "ecmp":
        ttt, param = ecmp_ttt(A, W, dem, CAP, eps=a.eps), a.eps
    else:
        tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False)
              for i in range(10)]
        model = train("GCN", tr, seed=0)
        with torch.no_grad():
            g = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()
        rc = W.copy()
        rc[ins["rows"], ins["cols"]] = W[ins["rows"], ins["cols"]] * (1 + g)
        ttt, param = multipath_route(A, W, rc, dem, CAP, tau=a.tau)["total_ttt"], a.tau

    print("%d,%s,%s,%s,%.4f,%.1f"
          % (a.seed, a.job, param, a.iters or "", ttt, time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
