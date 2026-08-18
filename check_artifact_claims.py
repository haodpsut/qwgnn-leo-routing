#!/usr/bin/env python3
"""AR-10: so trong README/RUN-LOG cua artifact phai khop claims.json cua bai.

VI SAO. Ca ATTEST 15/08/2026: bai doi tu 58 len 76 luot khi them ho model thu hai. main.tex,
claims.json va MOI CSV deu cap nhat; verify_numbers, trace_prose_numbers, check_freshness deu
xanh. Nhung ARTIFACT-README.md van ghi 58. Nguoi doc doi chieu bai voi artifact thay HAI con so
khac nhau va khong co cach nao biet cai nao cu. Hao bat duoc bang mat, khong cong nao bat.

Van xuoi mo ta cong viec cung la mot BE MAT TUYEN BO. README khong phai tai lieu phu.

Usage: check_artifact_claims.py <claims.json> <file-van-xuoi> [them file...]
Exit: 0 moi so trong van xuoi deu la gia tri cua mot claim (hoac duoc mien tuong minh);
      2 co so khong khop claim nao.
"""
import json
import os
import re
import sys

# Con so KHONG phai ket qua do dac: phien ban, cong, nam, kich thuoc file, so trang.
ALLOW_CTX = re.compile(
    r"(python|version|v\d|\.csv|\.py|\.md|\.pdf|20\d\d|MB|KB|GB|GHz|core|nhan|seed \d|"
    r"http|doi|arXiv|figure|table|section|page)", re.I)


def numbers(text):
    """(chuoi, vi tri) cho moi so co the la ket qua: co phan thap phan hoac co dau %."""
    for m in re.finditer(r"(?<![\w.])(\d+\.\d+|\d+(?=\s*%))", text):
        yield m.group(1), m.start()


def main():
    # Khong tham so: suy tu vi tri cua chinh file nay (quy uoc pipeline: script nam trong code/).
    args = sys.argv[1:]
    if not args:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(here)
        args = [os.path.join(root, "paper", "claims.json")]
        # RESUME.md la ban ghi LICH SU cua giai doan truoc, khong phai tuyen bo hien hanh; no
        # tu khai dieu do o dau file. Bat no khop claims hien tai la sai: bo ghi that bai chinh
        # la thu ta muon giu nguyen.
        for cand in ("README.md", "RUN-LOG.md", "ARTIFACT-README.md"):
            for base in (root, here):
                p = os.path.join(base, cand)
                if os.path.exists(p):
                    args.append(p)
        if len(args) < 2:
            print("khong tim thay file van xuoi nao (README/RUN-LOG) => KHONG kiem duoc gi")
            return 2
    if len(args) < 2:
        sys.exit(__doc__)
    raw = json.load(open(args[0], encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("claims", raw)
    vals = {str(c["paper_value"]).lstrip("+") for c in rows}

    bad, checked = [], 0
    for path in args[1:]:
        if not os.path.exists(path):
            print("  bo qua (khong co): %s" % path)
            continue
        text = open(path, encoding="utf-8").read()
        for v, pos in numbers(text):
            ctx = text[max(0, pos - 70):pos + 40].replace("\n", " ")
            checked += 1
            if v in vals:
                continue
            if ALLOW_CTX.search(ctx):
                continue
            bad.append((os.path.basename(path), v, re.sub(r"\s+", " ", ctx).strip()))

    print("da doi chieu %d con so trong %d file van xuoi" % (checked, len(args) - 1))
    if not checked:
        # Quet 0 don vi khong phai sach. Xem feedback-kiem-0-don-vi-khong-phai-sach.
        print("KHONG co so nao de kiem => HONG, khong phai PASS")
        return 2
    if bad:
        print("\n%d so KHONG khop claim nao va khong nam trong ngu canh duoc mien:" % len(bad))
        for f, v, ctx in bad[:30]:
            print("  %-22s %-9s ...%s..." % (f, v, ctx[:74]))
        print("\nFAIL -- moi so ket qua trong van xuoi artifact phai la mot claim.")
        return 2
    print("PASS -- moi so ket qua trong van xuoi artifact deu khop claims.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
