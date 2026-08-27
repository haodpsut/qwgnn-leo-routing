"""Cong: MOI so cua bang va hinh phai o trong tep SINH RA, khong duoc go trong main.tex.

    python code/scripts/check_no_hardcoded.py --tex paper/main.tex

⛔ VI SAO. 27/08/2026 kiem ke bai TNSM: 14 bang/hinh, chi 5 sinh tu du lieu, 9 go tay
thang trong main.tex (6 bang + 3 hinh, 55 toa do). Hau qua da xay ra chu khong phai gia
dinh:

  - `tab:decode` in DUNG so cua lan chay TRUOC 18/08. Ngay 18/08 bai chay lai toan bo tren
    mot may, van xuoi duoc cap nhat (44 claim), bang thi khong. Bo sinh chay tren CSV cu
    `d6ff618` tai tao chinh xac ca sau gia tri dang in.
  - `tab:baselines` bi va tay TUNG O: cot blind-mp la so moi, o GNN OOD van la so cu
    (0.11 thay vi 0.12).
  - `fig:speedup` go cung (132,21.8)(264,21.2)(1584,29.1) -- dung ba con so nguoi doc
    ngoai dang bac.

Cong truy so cua bai doc CLAIM trong van xuoi nen khong thay o bang. Khong ai va tay hai
muoi o ma khong sot; cach duy nhat la sinh ra het.

Cong nay chan chieu nguoc: neu `main.tex` con du lieu go tay thi FAIL.
"""
import argparse
import os
import re
import sys

# Moi truong duoc phep chua du lieu go tay: khong cai nao. Bang/hinh phai la \input.
# Ngoai le duy nhat: hinh so do khoi (khong co du lieu do luong) -- khai o day, co ten.
ALLOW = {
    "fig:pipeline",   # so do khoi cua bo giai, khong chua so do luong nao
}


def blocks(s):
    for m in re.finditer(r"\\begin\{(table\*?|figure\*?)\}(.*?)\\end\{\1\}", s, re.S):
        lab = re.search(r"\\label\{([^}]*)\}", m.group(2))
        yield (lab.group(1) if lab else "(khong nhan)"), m.group(1), m.group(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", required=True)
    a = ap.parse_args()

    s = open(a.tex, encoding="utf-8").read()
    s = re.sub(r"(?<!\\)%.*", "", s)          # bo chu thich truoc, khong doc nham
    bad = ok = 0
    for lab, env, body in blocks(s):
        if lab in ALLOW:
            print("  --  %-16s %s: mien tru da khai (so do khoi)" % (lab, env))
            continue
        has_input = bool(re.search(r"\\input\{", body))
        coords = re.findall(r"\(\s*-?[\d.]+\s*,\s*-?[\d.]+\s*\)", body)
        # dong bang co du lieu: co '&' VA co so
        rows = [l for l in body.split("\\\\")
                if "&" in l and re.search(r"\d", l) and "caption" not in l]
        if has_input and not coords and not rows:
            ok += 1
            print("  ok  %-16s %s: chi \\input" % (lab, env))
            continue
        bad += 1
        why = []
        if coords:
            why.append("%d toa do" % len(coords))
        if rows:
            why.append("%d dong bang" % len(rows))
        print("  ⛔  %-16s %s: GO TAY (%s)" % (lab, env, ", ".join(why) or "khong \\input"))

    # ⛔ Khi MOI bang/hinh da thanh \\input roi thi trong main.tex khong con moi truong
    # nao de duyet, va cong tung bao "kiem 0 don vi" tren dung trang thai DAT. Nen phai
    # dem ca cac dong \\input{tab-*} / \\input{fig-*}: do la don vi DA SINH RA.
    inputs = sorted(set(re.findall(r"\\input\{((?:tab|fig)-[^}]*)\}", s)))
    for f in inputs:
        d = os.path.dirname(os.path.abspath(a.tex))
        q = os.path.join(d, f if f.endswith(".tex") else f + ".tex")
        if os.path.exists(q):
            ok += 1
            print("  ok  %-16s %s" % (f, "tep sinh ra"))
        else:
            bad += 1
            print("  ⛔  %-16s \\input tro toi tep KHONG TON TAI" % f)

    print("  da kiem %d bang/hinh: %d sinh-ra, %d go tay" % (ok + bad, ok, bad))
    if ok + bad == 0:
        print("  ⛔ KIEM 0 DON VI -- khong duoc doc thanh sach")
        return 1
    print("  => %s" % ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
