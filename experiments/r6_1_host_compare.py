"""R6.1 -- so hai tep r6_0 va tra loi DUNG cau hoi bai dang khai.

    python experiments/r6_1_host_compare.py

Bai khai hai dieu tach biet, va chung phai duoc kiem tach biet:

  (1) "duong ong tat dinh TREN MOT MAY, khong tat dinh giua cac may"
  (2) "moi dai luong KHONG di qua mang khop toi chu so in ra"

(2) manh hon (1) rat nhieu va la cai de sai. Script nay in ti so lech theo TUNG NHOM va
FAIL neu van ban con khai (2) trong khi du lieu bac no.

⛔ NO TU CHOI CHAY neu hai tep khac commit hoac trung tag: mot phep so "hai may" ma hai ben
khac ma nguon thi do ma nguon chu khong do may, va do dung la cai da xay ra voi bo
`/tmp/res_before`.
"""
import csv
import glob
import re
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")


def load():
    out = {}
    for p in sorted(glob.glob(os.path.join(RES, "r6_0_host_control_*.csv"))):
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if rows:
            out[rows[0]["tag"]] = rows
    return out


def main():
    d = load()
    if len(d) < 2:
        print("  ⛔ can it nhat HAI tep r6_0_host_control_*.csv (moi may mot tep); dang co: %s"
              % (sorted(d) or "khong co tep nao"))
        print("     Chay `python experiments/r6_0_host_control.py --tag <ten-may>` tren tung may.")
        return 1
    tags = sorted(d)
    if len(set(tags)) != len(tags):
        print("  ⛔ hai tep trung tag -- khong phan biet duoc may")
        return 1

    # ⛔ Ghim bang BAM NOI DUNG, khong bang commit: mot ben co the khong nam trong kho git
    # (thu muc lam viec tren Mac), va khi do so commit se tu choi chay dung luc can nhat.
    shas = {t: d[t][0].get("code_sha", "(khong ghi)") for t in tags}
    if len(set(shas.values())) != 1 or "(khong ghi)" in shas.values():
        print("  ⛔ HAI MAY CHAY HAI BAN MA KHAC NHAU (hoac chua ghi bam): %s" % shas)
        print("     Phep so nay se do MA NGUON chu khong do may. Dong bo ma roi chay lai.")
        return 1
    commits = {t: d[t][0].get("commit", "?") for t in tags}

    a, b = tags[0], tags[1]
    print("  bam ma nguon chung: %s | commit: %s" % (shas[a], commits))
    for t in tags:
        print("    %-5s %s" % (t, d[t][0]["env"]))

    ra = {(r["shell"], r["seed"]): r for r in d[a]}
    rb = {(r["shell"], r["seed"]): r for r in d[b]}
    keys = sorted(set(ra) & set(rb))
    if not keys:
        print("  ⛔ khong co don vi nao chung giua hai may")
        return 1

    groups = {"A (khong cham torch)": [], "B (qua torch)": []}
    worst = {"A (khong cham torch)": ("", 0.0), "B (qua torch)": ("", 0.0)}
    for k in keys:
        for col in ra[k]:
            if not (col.startswith("A_") or col.startswith("B_")):
                continue
            try:
                u, v = float(ra[k][col]), float(rb[k][col])
            except (TypeError, ValueError):
                continue
            g = "A (khong cham torch)" if col.startswith("A_") else "B (qua torch)"
            rel = abs(u - v) / max(abs(u), abs(v), 1e-300)
            groups[g].append(rel)
            if rel > worst[g][1]:
                worst[g] = ("%s %s %s" % (k[0], k[1], col), rel)

    exact_A = True
    for g in ("A (khong cham torch)", "B (qua torch)"):
        v = groups[g]
        if not v:
            print("  ⛔ nhom %s: 0 o so sanh duoc -- khong doc thanh dat" % g)
            return 1
        n_diff = sum(1 for x in v if x > 0)
        print("  %-22s %3d o, %3d o LECH, lon nhat %.3e  (%s)"
              % (g, len(v), n_diff, worst[g][1], worst[g][0] or "-"))
        if g.startswith("A") and n_diff:
            exact_A = False

    # ⛔ Doi chieu thang voi VAN BAN. Mot phep do khong tu no sua duoc mot cau khai sai;
    # cong phai noi ro cau nao trong bai da bi du lieu bac.
    # ⛔ KIEM CAU DUOC KHANG DINH, khong kiem chuoi co mat. Ban dau tien chi tim chuoi, nen
    # khi bai duoc sua thanh "An earlier version claimed that ... That claim was wrong", cong
    # van keu -- tuc no bao dong to hon sau khi bai da dung hon. Mot cong nhu vay day nguoi
    # dung di dung huong nguoc lai. Xem [[feedback-cong-suy-su-kien-tu-dau-vet-mo]].
    tex = os.path.join(ROOT, "..", "paper", "main.tex")
    CLAIM = "agreed to the printed digit"
    said = False
    if os.path.exists(tex):
        body = open(tex, encoding="utf-8").read()
        for m in re.finditer(re.escape(CLAIM), body):
            w = body[max(0, m.start() - 320):m.end() + 120].lower()
            retracted = re.search(r"earlier version|was wrong|no longer|we withdraw|"
                                  r"that claim|incorrect|retract", w)
            if not retracted:
                said = True
                break
    print()
    if exact_A:
        print("  ✅ nhom A khop TUNG BIT giua hai may.")
        print("     Cau 'every quantity avoiding the network agreed to the printed digit' duoc do ung ho.")
        return 0
    print("  ⛔ nhom A KHONG khop giua hai may (lon nhat %.3e)." % worst["A (khong cham torch)"][1])
    print("     Nghia la lech giua hai may KHONG chi den tu torch, va giai thich 'chi phan qua")
    print("     mang moi lech' la sai. Nguyen nhan con lai kha di: thu tu cong don cua BLAS,")
    print("     va thu tu duyet trong Dijkstra khi co canh dong gia.")
    if said:
        print("     ⛔ main.tex VAN dang in cau '%s' -- phai sua." % CLAIM)
        return 1
    print("     (main.tex khong con cau do.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
