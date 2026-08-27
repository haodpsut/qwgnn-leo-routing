"""R5.0 -- PILOT: MSA hoi tu o vong thu bao nhieu tai vo 1584?

⛔ VI SAO CO TEP NAY. Bai tu khai o muc Limitations rang loi giai can bang 20 vong tai
vo 1584 CHUA HOI TU: gia cua vo chinh phu (PoA = UE/SO) ra **duoi 1** tren ca ba
instance, dieu khong the xay ra, va bai uoc rang tham chieu "roi khoang mot phan ba khi
keo dai loi giai". Roi bai van in cac so quy chieu ve can bang do.

Nguoi doc ngoai 27/08 goi dung ten viec nay: *"yet continued publishing the unconverged
values"*. Day la buoc sua dau tien.

⛔ VA KHONG DUOC DOAN so vong. Script anh em `r4_2_warmstart_iters.py` dat REF_ITERS=80,
nhung do la mot lua chon cho VIEC KHAC (moc hoi tu cua phep dem vong), khong phai bang
chung rang 80 du cho vo 1584. Chep con so do sang day la lay mot gia dinh lam ket qua.

Nen: quet so vong tren MOT seed truoc, in PoA theo tung muc, va chon muc nho nhat thoa
CA HAI dieu kien:
    (1) PoA = UE/SO >= 1        -- rang buoc VAT LY, khong the vi pham
    (2) UE doi < 0.5% giua hai muc lien tiep  -- da on dinh

Chi sau khi co so do moi chay ban day du ba seed. Pilot mot seed ton ~1/3 thoi gian cua
mot lan chay day, va no ngan viec dot ba gio cho mot so vong van chua du.
"""
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                # noqa: E402
from traffic import evaluate, route_and_measure                 # noqa: E402
from p5_gnn_router import make_instance                         # noqa: E402
from p5_gnn_router import CAP                                   # noqa: E402

SHELL = Walker(1584, 72, 1, 53.0, 550.0)
NPAIRS = 7200
SEED = 0
LADDER = [20, 40, 80, 160, 320]
TOL = 0.005          # 0,5% -- cung nguong "coi la hoi tu" ma r4_2 dung


def main():
    print("=" * 78)
    print("  R5.0 PILOT -- MSA hoi tu o vong nao tai vo 1584 (seed %d)" % SEED)
    print("=" * 78, flush=True)
    ins = make_instance(SHELL, NPAIRS, 900 + SEED, need_eig=False)
    A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]

    blind = route_and_measure(A, W, dem, CAP, W)["total_ttt"]
    print("  blind TTT = %.1f\n" % blind, flush=True)
    print("  %6s | %12s %12s %8s | %9s %9s" %
          ("vong", "UE", "SO", "PoA", "dUE", "blind/UE"))
    print("  " + "-" * 68)

    prev = None
    ok_at = None
    for it in LADDER:
        t0 = time.time()
        ue = evaluate(A, W, dem, CAP, policy="ue", iters=it)["total_ttt"]
        so = evaluate(A, W, dem, CAP, policy="so", iters=it)["total_ttt"]
        poa = ue / so
        d = abs(ue - prev) / prev if prev else float("nan")
        print("  %6d | %12.1f %12.1f %8.4f | %8.3f%% %9.1f    (%.0fs)"
              % (it, ue, so, poa, 100 * d if prev else float("nan"), blind / ue,
                 time.time() - t0), flush=True)
        if ok_at is None and poa >= 1.0 - 1e-9 and prev is not None and d < TOL:
            ok_at = it
        prev = ue

    print()
    if ok_at is None:
        print("  ⛔ CHUA co muc nao thoa CA HAI dieu kien tren thang %s." % LADDER)
        print("     Khong duoc chon bua mot so; phai noi dai thang roi chay lai pilot.")
        return 1
    print("  ✅ muc nho nhat thoa ca hai: %d vong" % ok_at)
    print("     dung so nay cho ban day du ba seed (r5_1).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
