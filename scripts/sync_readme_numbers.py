"""Ghi lai cac con so ket qua trong README tu claims.json.

    python code/scripts/sync_readme_numbers.py --readme code/README.md --claims paper/claims.json

⛔ VI SAO CO FILE NAY. 27/08/2026, sau khi chay lai toan bo thi nghiem tren VPS, bai bao TU
DONG dung so moi -- vi moi con so cua no da duoc noi vao `\\clm{}`. README thi khong: no van
in `80.5%` trong khi du lieu moi cho `84.3%`, `29.8%` trong khi du lieu cho `33.8%`, va bay
con so nhu vay. Bai va artifact cua CUNG mot lan nop noi hai dieu khac nhau.

Do la ca ATTEST lap lai: bai doi 58 -> 76 luot, moi cong xanh, ARTIFACT-README van ghi 58.
Cong `check_artifact_claims.py` bat duoc, nhung bat xong thi van phai sua TAY, va sua tay la
cho lan sau lech tiep.

CACH NAY LAM: README danh dau tung con so bang mot chu thich HTML vo hinh khi hien thi:

    `0.973` <!--clm:fair-gnn-w132-i53-->

Script doc claims.json roi ghi lai gia tri trong dau nhay nguoc ngay TRUOC moi danh dau.
Danh dau la HTML comment nen GitHub khong hien no ra.

⛔ NO KHONG DOAN. So nao khong co danh dau thi khong bi dong toi, va script in ra danh sach
do de nguoi biet phan nao con go tay. Doan xem mot con so ung voi claim nao chinh la cach
mot ti le khe thoi gian tung bi in ra lam p-value.
"""
import argparse
import json
import re
import sys

MARK = re.compile(r"`([^`]*)`(\s*)<!--\s*clm:([a-z0-9-]+)\s*-->")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--readme", required=True)
    ap.add_argument("--claims", required=True)
    ap.add_argument("--check", action="store_true", help="chi kiem, khong ghi")
    a = ap.parse_args()

    C = json.load(open(a.claims, encoding="utf-8"))
    C = C["claims"] if isinstance(C, dict) else C
    val = {c["id"].replace("_", "-"): c["paper_value"].lstrip("+") for c in C}

    s = open(a.readme, encoding="utf-8").read()
    marked, changed, missing = 0, [], []

    def rep(m):
        nonlocal marked
        old, gap, cid = m.group(1), m.group(2), m.group(3)
        marked += 1
        if cid not in val:
            missing.append(cid)
            return m.group(0)
        new = val[cid]
        # giu hau to don vi neu co (vi du "29.8%")
        suf = re.sub(r"^[\d.eE+-]+", "", old)
        if old != new + suf:
            changed.append((cid, old, new + suf))
        return "`%s%s`%s<!--clm:%s-->" % (new, suf, gap, cid)

    out = MARK.sub(rep, s)

    if marked == 0:
        print("  ⛔ README khong co danh dau <!--clm:...--> nao -- KIEM 0 DON VI.")
        print("     Them danh dau vao tung con so ket qua, neu khong no se lech im lang.")
        return 1
    for cid in missing:
        print("  ⛔ danh dau tro toi claim khong ton tai: %s" % cid)
    for cid, o, n in changed:
        print("  ~  %-30s %s -> %s" % (cid, o, n))

    # so con lai trong dau nhay nguoc ma KHONG co danh dau
    bare = [m.group(1) for m in re.finditer(r"`([\d.]+%?)`(?!\s*<!--clm:)", out)]
    if bare:
        print("  ⚠  %d so trong README chua co danh dau, se khong bao gio tu cap nhat: %s"
              % (len(bare), ", ".join(sorted(set(bare))[:8])))

    if a.check:
        print("  da kiem %d danh dau: %d lech" % (marked, len(changed)))
        return 1 if (changed or missing) else 0
    if changed:
        open(a.readme, "w", encoding="utf-8").write(out)
    print("  da dong bo %d danh dau, cap nhat %d so, %d chua danh dau"
          % (marked, len(changed), len(bare)))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
