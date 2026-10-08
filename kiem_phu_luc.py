#!/usr/bin/env python3
"""Cổng: thân bài gọi "Appendix A/B/C/D" bằng CHỮ, phụ lục phải khớp đúng thứ tự đó.

⛔ VÌ SAO CÓ TỆP NÀY. Tham chiếu chéo giữa hai tài liệu LaTeX không giải được, nên thân
bài phải gọi phụ lục bằng chữ cứng ("Appendix~A of the supplementary material"). Cái giá
là: đổi thứ tự \\input trong supplementary.tex thì thân bài lặng lẽ trỏ sai, và không
cổng LaTeX nào bắt được vì cả hai tài liệu vẫn dịch sạch.

Đây đúng lớp lỗi "hai nguồn không ai hỏi chúng có nói giống nhau".

    python3 kiem_phu_luc.py
    python3 kiem_phu_luc.py --tu-kiem
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _tim_paper():
    """Tìm `paper/` theo cả hai bố cục: thư mục bài, và trong kho của gói nộp.

    ⛔ Bản đầu cố định `HERE/paper`, nên bản chép vào kho tự nó không chạy được: khi giải
    nén gói, cổng nằm ở `<goi>/repo/` còn bản thảo ở `<goi>/paper/`.
    """
    for goc in (HERE, os.path.dirname(HERE)):
        p = os.path.join(goc, "paper")
        if os.path.isfile(os.path.join(p, "main.tex")):
            return p
    return os.path.join(HERE, "paper")


PAPER = _tim_paper()
CHU = "ABCDEFGH"


def doc(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def thu_tu_phu_luc(supp_tex):
    """Thứ tự các tệp phụ lục theo \\input trong supplementary.tex, kèm tiêu đề mục."""
    s = doc(supp_tex)
    ten = re.findall(r"\\input\{(supp-[\w-]+)\}", s)
    out = []
    for t in ten:
        p = os.path.join(os.path.dirname(supp_tex), t + ".tex")
        tieu = ""
        if os.path.exists(p):
            m = re.search(r"\\section\{([^}]*)\}", doc(p))
            tieu = " ".join(m.group(1).split()) if m else ""
        out.append((t, tieu))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tu-kiem", action="store_true")
    ap.add_argument("--paper", default=PAPER)
    a = ap.parse_args()
    if a.tu_kiem:
        return tu_kiem()

    main_tex = os.path.join(a.paper, "main.tex")
    supp_tex = os.path.join(a.paper, "supplementary.tex")
    for p in (main_tex, supp_tex):
        if not os.path.exists(p):
            sys.exit("⛔ thieu %s" % p)

    loi = []
    thu_tu = thu_tu_phu_luc(supp_tex)
    print("== Cong khop phu luc <-> than bai ==\n")
    print("  thu tu trong supplementary.tex:")
    for i, (t, tieu) in enumerate(thu_tu):
        print("    Appendix %s  %-26s %s" % (CHU[i] if i < len(CHU) else "?", t, tieu[:46]))

    body = doc(main_tex)
    goi = re.findall(r"Appendix~([A-H])\b", body)
    print("\n  than bai goi: %s" % (", ".join("Appendix " + g for g in sorted(set(goi)))
                                    or "khong goi phu luc nao"))

    # P1: moi chu than bai goi phai ton tai trong phu luc
    thua = sorted({g for g in goi if CHU.index(g) >= len(thu_tu)})
    ok1 = not thua
    print("\n  %s P1 moi Appendix than bai goi deu TON TAI trong phu luc%s"
          % ("DAT " if ok1 else "HONG", "" if ok1 else "  [khong co: " + ", ".join(thua) + "]"))
    if not ok1:
        loi.append("P1")

    # P2: moi muc phu luc phai duoc than bai goi, khong de muc mo coi
    chua_goi = [CHU[i] + " (" + t + ")" for i, (t, _) in enumerate(thu_tu)
                if i < len(CHU) and CHU[i] not in goi]
    ok2 = not chua_goi
    print("  %s P2 khong co muc phu luc MO COI%s"
          % ("DAT " if ok2 else "HONG", "" if ok2 else "  [khong ai goi: " + ", ".join(chua_goi) + "]"))
    if not ok2:
        loi.append("P2")

    # P3: tep phu luc KHONG duoc \input lai float ma than bai cung \input
    f_body = set(re.findall(r"\\input\{((?:tab|fig)-[\w-]+)\}", body))
    trung = []
    for t, _ in thu_tu:
        p = os.path.join(a.paper, t + ".tex")
        if os.path.exists(p):
            trung += [x for x in re.findall(r"\\input\{((?:tab|fig)-[\w-]+)\}", doc(p))
                      if x in f_body]
    ok3 = not trung
    print("  %s P3 phu luc khong \\input lai float cua than bai%s"
          % ("DAT " if ok3 else "HONG", "" if ok3 else "  [trung: " + ", ".join(sorted(set(trung))) + "]"))
    if not ok3:
        loi.append("P3")

    # P4: moi tep phu luc phai co dung MOT \section
    sai4 = []
    for t, tieu in thu_tu:
        p = os.path.join(a.paper, t + ".tex")
        if not os.path.exists(p):
            sai4.append(t + " (thieu tep)")
        elif len(re.findall(r"\\section\{", doc(p))) != 1:
            sai4.append(t + " (khong phai dung 1 section)")
    ok4 = not sai4
    print("  %s P4 moi tep phu luc co dung MOT section%s"
          % ("DAT " if ok4 else "HONG", "" if ok4 else "  [" + ", ".join(sai4) + "]"))
    if not ok4:
        loi.append("P4")

    print("\n=> %s (%d loi)" % ("DAT" if not loi else "CHUA DAT", len(loi)))
    return 0 if not loi else 1


def tu_kiem():
    """Đối chứng DƯƠNG: tiêm từng lỗi, cổng phải bắt đúng cổng đó."""
    import tempfile
    import subprocess
    print("== TU KIEM cong phu luc ==\n")
    ok = True
    d = tempfile.mkdtemp()

    def dung(so_muc, goi_chu, float_trung=False, hai_section=False):
        for i in range(so_muc):
            t = "a" if (hai_section and i == 0) else ""
            io.open(os.path.join(d, "supp-m%d.tex" % i), "w").write(
                "\\section{Muc %d}\n\\label{supp:m%d}\n" % (i, i)
                + ("\\section{Them}\n" if hai_section and i == 0 else "")
                + ("\\input{tab-x}\n" if float_trung and i == 0 else ""))
        io.open(os.path.join(d, "supplementary.tex"), "w").write(
            "".join("\\input{supp-m%d}\n" % i for i in range(so_muc)))
        io.open(os.path.join(d, "main.tex"), "w").write(
            "\\input{tab-x}\n" + "".join("see Appendix~%s of the supplementary.\n" % c
                                         for c in goi_chu))

    def chay():
        return subprocess.run([sys.executable, os.path.abspath(__file__), "--paper", d],
                              capture_output=True, text=True).stdout

    def thu(ten, ma, mong_hong):
        out = chay()
        dong = [l for l in out.splitlines() if " " + ma + " " in l]
        hong = bool(dong) and dong[0].strip().startswith("HONG")
        dat = hong == mong_hong
        print("  %-54s %s" % (ten, "DAT" if dat else "HONG"))
        return dat

    dung(2, "AB")
    ok &= thu("2 muc, than bai goi A va B: tat ca DAT", "P1", False)
    ok &= thu("   va khong co muc mo coi", "P2", False)

    dung(2, "ABC")
    ok &= thu("than bai goi Appendix C ma phu luc chi co 2: P1 HONG", "P1", True)

    dung(3, "AB")
    ok &= thu("phu luc co 3 muc ma than bai goi 2: P2 HONG", "P2", True)

    dung(2, "AB", float_trung=True)
    ok &= thu("phu luc \\input lai float cua than bai: P3 HONG", "P3", True)

    dung(2, "AB", hai_section=True)
    ok &= thu("mot tep phu luc co 2 section: P4 HONG", "P4", True)

    print("\n  => %s" % ("TAT CA DAT" if ok else "CO CA HONG"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
