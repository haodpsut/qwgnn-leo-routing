"""Cong: so trong van xuoi GAN mot claim nhung KHONG BANG no.

    python code/scripts/check_near_miss.py --tex paper/main.tex --claims paper/claims.json

⛔ VI SAO CO FILE NAY. 27/08/2026, khi noi cac con so cua bai vao macro `\\clm{}`, bon con
so lo ra cung mot lot:

    bai in    du lieu    claim
    0.937     0.936      fair_gnn_fixedtau_w264_i70
    16.3      16.36      time_total_w1584
    0.50      0.49       time_total_w264
    27.2%     27.3%      time_pct_w1584

Khong con so nao trong so do bi bat boi lop cong dang co, va ly do rat cu the: cong
"gia tri cu" chi keu khi con so TUNG la mot claim, con cong truy-so chi kiem nhung con so
DA duoc khai. Mot con so go tay lech mot chu so cuoi thi khong thuoc ca hai nhom -- no
khong phai gia tri cu cua claim nao, va no khong duoc khai o dau ca. No chi don gian la
SAI, va im lang.

Nguyen nhan sinh ra chung deu la nguoi: lam tron tay (16.36 -> 16.3), doc nham cot
(0.937), hoac chep tu mot lan chay truoc roi lan chay sau doi (0.50 -> 0.49).

CACH NAY LAM: voi moi so thap phan trong van xuoi ma KHONG bang bat ky claim nao, tim
claim gan nhat. Neu khoang cach tuong doi duoi NGUONG thi bao: gan nhu chac chan day la
mot phien ban go tay cua claim do.

⚠ NO LA CONG BAO DONG, KHONG PHAI CONG CHAN. Mot bai co the co so that su khong lien quan
ma tinh co gan mot claim (vi du "60 s" cua khe thoi gian gan mot ti le nao do). Nen no in
ra de nguoi soi, va chi FAIL khi khoang cach RAT nho (duoi 2%) VA so chu so co nghia bang
nhau -- dau hieu cua lam tron tay chu khong phai cua mot dai luong khac.

Xem [[feedback-so-headline-mot-cho-o]] va [[feedback-cong-bat-sai-khong-bat-thieu]].
"""
import argparse
import json
import os
import re
import sys

# Khong xet: so mu, so hieu phien ban, toa do, va cac hang so cau hinh quen thuoc.
IGNORE = {"0.5", "1.0", "2.0", "0.0", "0.05", "0.1", "0.2", "0.25", "0.75",
          "1.5", "0.01", "0.001", "60.0", "0.95", "0.99"}
FAIL_REL = 0.02          # duoi 2% => coi la lam tron tay / go nham
WARN_REL = 0.06
TOP = 12                 # so ung vien in ra; dai hon thi khong ai doc


def prose(tex):
    # ⛔ CHI QUET VAN DO NGUOI GO. Ban dau tien gop ca cac tep tab-*.tex \input vao, va 5
    # trong 16 bao dong den tu do -- vo nghia, vi nhung tep ay SINH RA tu CSV nen theo dinh
    # nghia khong the la ban go tay cua mot claim. Do la cong tu tao nhieu cho chinh no.
    s = open(tex, encoding="utf-8").read()
    s = re.sub(r"(?<!\\)%.*", "", s)
    # ⛔ Bo phan DA noi vao macro: no khong the lech, va de nguyen thi cong tu tao nhieu.
    s = re.sub(r"\\clm\{[^}]*\}", " ", s)
    # bo nhan, tham chieu, duong dan
    # tham so tuy chon cua includegraphics chua "1.25in" -> tung bi bao la ban go tay cua
    # mot ti so 1.23. Bo CA phan [...] chu khong chi phan {...}.
    s = re.sub(r"\\includegraphics\s*(\[[^\]]*\])?\s*\{[^}]*\}", " ", s)
    s = re.sub(r"\\(?:label|ref|autoref|eqref|cite|input)\{[^}]*\}", " ", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", required=True)
    ap.add_argument("--claims", required=True)
    a = ap.parse_args()

    C = json.load(open(a.claims, encoding="utf-8"))
    C = C["claims"] if isinstance(C, dict) else C
    vals = []
    for c in C:
        try:
            vals.append((float(c["paper_value"].lstrip("+")), c["paper_value"].lstrip("+"), c["id"]))
        except ValueError:
            continue
    exact = {v[1] for v in vals}
    if not vals:
        print("  ⛔ claims.json khong co gia tri so nao -- khong doc thanh sach")
        return 1

    s = prose(a.tex)
    seen, warn, bad = set(), [], []
    for m in re.finditer(r"(?<![\w.\\])(\d+\.\d+)(?![\d])", s):
        t = m.group(1)
        if t in exact or t in IGNORE or t in seen:
            continue
        seen.add(t)
        x = float(t)
        near = min(vals, key=lambda v: abs(v[0] - x) / max(abs(v[0]), 1e-12))
        rel = abs(near[0] - x) / max(abs(near[0]), 1e-12)
        if rel == 0 or rel > WARN_REL:
            continue
        # cung so chu so sau dau cham => dau hieu go/lam tron tay, khong phai dai luong khac
        # claim co the la so nguyen ("3", "196") nen khong chac co phan thap phan
        dp = lambda z: len(z.split(".")[1]) if "." in z else 0
        same_dp = dp(t) == dp(near[1])
        ctx = " ".join(s[max(0, m.start() - 70):m.end() + 55].split())
        rec = (t, near[1], near[2], rel, ctx)
        (bad if (rel <= FAIL_REL and same_dp) else warn).append(rec)

    # ⛔ CONG NAY BAO CAO, KHONG CHAN. Ban chan dau tien co 16 bao dong trong do 7 la gia
    # (44%). Mot cong bao sai gan mot nua se bi bo qua, va lan sau no im lang tren loi that
    # -- te hon la khong co cong. Nen: xep hang theo do gan va in DANH SACH NGAN de soi tay.
    # Do gan KHONG phai bang chung; no chi la thu tu uu tien.
    rank = sorted(bad + warn, key=lambda r: r[3])[:TOP]
    for t, nv, nid, rel, ctx in rank:
        print("  ?  bai in %-8s | claim gan nhat %-8s (%s) lech %.2f%%" % (t, nv, nid, 100 * rel))
        print("     ...%s..." % ctx[:112])
    print("  da kiem %d so thap phan khong trung claim; in %d ung vien gan nhat de soi tay."
          % (len(seen), len(rank)))
    if not seen:
        print("  ⛔ KIEM 0 SO -- khong duoc doc thanh sach")
        return 1
    print("  => BAO CAO (khong chan). Moi dong tren phai duoc tra lai CSV bang tay.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
