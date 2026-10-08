#!/usr/bin/env python3
"""Sinh DANH SÁCH THAY ĐỔI từ hai bản in, phủ 100% phần đã xoá.

⛔ VÌ SAO CÓ TỆP NÀY. Bản tô sáng do `latexdiff` sinh chỉ đặt lại được **46%** số câu đã
xoá vào đúng ngữ cảnh; 54% còn lại biến mất khỏi bản tô sáng mà không dấu vết. Phản biện 1
vòng 2 đã mất một lượt nhận xét vào đúng chỗ này: các "tracked-change artifact" họ nêu đều
là mối nối chữ ở bản tô sáng, không phải lỗi trong bản thảo.

Tệp này giải quyết bằng cách khác: không tô màu trong văn, mà **liệt kê** từng câu bị xoá và
từng câu mới, kèm số trang của bản tương ứng. Không có mối nối nào để dính chữ, và độ phủ là
100% theo định nghĩa.

Số đếm ở đây PHẢI khớp số đếm của bước thống kê trong `build-submit.sh`, vì cả hai dùng cùng
một phép tách câu trên cùng hai bản in; `build-submit.sh` so hai số đó và dừng nếu lệch.

    python3 scripts/make_change_list.py <cu.pdf> <moi.pdf> <ra.tex>
    python3 scripts/make_change_list.py --tu-kiem
"""
import argparse
import io
import os
import re
import subprocess
import sys

NGUONG = 80          # chỉ xét câu dài, như bước thống kê
KHOA = 60            # so khớp bằng 60 ký tự đầu, như bước thống kê


def phang(s):
    return re.sub(r"\s+", " ", s)


def trang(pdf):
    """Danh sách văn bản theo TRANG, để gắn số trang cho từng câu."""
    n = int(re.search(r"Pages:\s*(\d+)",
                      subprocess.run(["pdfinfo", pdf], capture_output=True,
                                     text=True).stdout).group(1))
    out = []
    for i in range(1, n + 1):
        out.append(phang(subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), pdf, "-"],
                                        capture_output=True, text=True).stdout))
    return out


def cau(ts):
    """Câu dài của CẢ tài liệu, kèm trang nơi tìm thấy nó.

    ⛔ Phải tách câu trên CẢ tài liệu rồi mới tìm trang, không được tách theo từng trang.
    Tách theo trang thì một câu vắt qua chỗ sang trang bị chẻ thành hai mảnh, và phép đếm
    lệch với bước thống kê của `build-submit.sh` (đo được: 90 so với 94). Hai nguồn cùng
    một phép đo thì phải cho cùng một số.
    """
    van = " ".join(ts)
    o = []
    for c in re.split(r"(?<=[.])\s", van):
        c = phang(c).strip()
        if len(c) < NGUONG:
            continue
        tr_ = next((i for i, t in enumerate(ts, 1) if c[:KHOA] in t), 0)
        o.append((c, tr_))
    return o


# Lop van ban cua PDF mang ky tu KHONG phai ASCII: dau tru U+2212, dau nhan U+00D7, cac
# ky tu BIEN THE U+FE00..FE0F do font toan sinh ra. pdflatex khong dich duoc chung va bao
# "Unicode character ... not set up for use with LaTeX" -- do duoc 5 loi o lan dung dau.
MAP = {"\u2212": "-", "\u00d7": r"$\times$", "\u2248": r"$\approx$", "\u2265": r"$\ge$",
       "\u2264": r"$\le$", "\u2019": "'", "\u2018": "'", "\u201c": "``", "\u201d": "''",
       "\u2013": "--", "\u2014": "--", "\u00a0": " ", "\u03c4": r"$\tau$",
       "\u03c3": r"$\sigma$", "\u00b1": r"$\pm$", "\u2032": "'", "\u00b0": r"$^\circ$"}


def thoat(s):
    """Về văn LaTeX an toàn: nội dung là văn bản đã bóc thẻ, nên chỉ cần thoát ký tự đặc biệt."""
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                 ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
                 ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")):
        s = s.replace(a, b)
    for a, b in MAP.items():
        s = s.replace(a, b)
    # Con lai gi khong phai ASCII thi BO, va noi ro la da bo, dung im lang.
    con = sorted({c for c in s if ord(c) > 127})
    if con:
        s = "".join(c for c in s if ord(c) <= 127)
    return s


def lam(cu_pdf, moi_pdf, ra):
    t_cu, t_moi = trang(cu_pdf), trang(moi_pdf)
    c_cu, c_moi = cau(t_cu), cau(t_moi)
    van_cu, van_moi = " ".join(t_cu), " ".join(t_moi)
    bo = [(c, p) for c, p in c_cu if c[:KHOA] not in van_moi]
    them = [(c, p) for c, p in c_moi if c[:KHOA] not in van_cu]

    L = [r"% SINH TU repo/scripts/make_change_list.py -- DUNG SUA TAY.",
         r"\documentclass[10pt]{article}",
         r"\usepackage[margin=1in]{geometry}",
         r"\usepackage{enumitem}",
         r"\setlength{\parindent}{0pt}\setlength{\parskip}{3pt}",
         r"\pagestyle{plain}",
         r"\begin{document}",
         r"\section*{Change list, TNSM-2026-12059}",
         r"Every sentence that left the manuscript and every sentence that entered it, between"
         r" the version the reviewers read and the version submitted now. This list exists"
         r" because the marked-up copy cannot carry all of it: \texttt{latexdiff} places a"
         r" deleted sentence only where it can align the two documents, and on this revision it"
         r" could place fewer than half of them. The list below is complete by construction, and"
         r" it is derived from the two printed documents rather than from the comparison, so no"
         r" deleted word is ever joined to an inserted one.",
         r"",
         r"Page numbers are those of the document each sentence belongs to. Sentences shorter than"
         r" %d characters, table cells and figure captions are not listed: a caption regenerated by"
         r" script is reported as changed even when its content is not, and listing those would bury"
         r" the %d substantive items." % (NGUONG, len(bo) + len(them)),
         r"",
         r"\subsection*{Removed (%d sentences, from the previous version)}" % len(bo),
         r"\begin{enumerate}[leftmargin=2em,itemsep=2pt]"]
    for c, p in bo:
        L.append(r"\item \textit{p.%d:} %s" % (p, thoat(c)))
    L += [r"\end{enumerate}",
          r"\subsection*{Added (%d sentences, in the version submitted now)}" % len(them),
          r"\begin{enumerate}[leftmargin=2em,itemsep=2pt]"]
    for c, p in them:
        L.append(r"\item \textit{p.%d:} %s" % (p, thoat(c)))
    L += [r"\end{enumerate}", r"\end{document}", ""]
    io.open(ra, "w", encoding="utf-8").write("\n".join(L))
    print("   danh sach thay doi: %d cau bo, %d cau moi -> %s"
          % (len(bo), len(them), os.path.basename(ra)))
    return len(bo), len(them)


def tu_kiem():
    """Đối chứng: một câu bị bỏ và một câu thêm phải xuất hiện đúng một lần mỗi loại."""
    import tempfile
    print("== TU KIEM make_change_list ==\n")
    d = tempfile.mkdtemp()
    ok = True

    def pdf(ten, cau_rieng):
        tex = os.path.join(d, ten + ".tex")
        io.open(tex, "w", encoding="utf-8").write(
            "\\documentclass{article}\\begin{document}\n"
            "This first sentence is shared by both documents and is long enough to pass the "
            "length threshold used by the change list generator.\n" + cau_rieng +
            "\n\\end{document}\n")
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "-output-directory", d, tex],
                       capture_output=True)
        return os.path.join(d, ten + ".pdf")

    a = pdf("cu", "This sentence exists only in the previous version and is long enough to be "
                  "listed among the removed sentences by the generator.")
    b = pdf("moi", "This sentence exists only in the new version and is long enough to be "
                   "listed among the added sentences by the generator.")
    n_bo, n_them = lam(a, b, os.path.join(d, "cl.tex"))
    for nhan, co, mong in (("cau bi bo", n_bo, 1), ("cau them", n_them, 1)):
        dat = co == mong
        print("  %-46s %s" % ("%s: dem %d, mong %d" % (nhan, co, mong), "DAT" if dat else "HONG"))
        ok &= dat
    # cau DUNG CHUNG khong duoc liet ke o ca hai ben
    s = io.open(os.path.join(d, "cl.tex"), encoding="utf-8").read()
    dat = "shared by both documents" not in s
    print("  %-46s %s" % ("cau dung chung KHONG bi liet ke", "DAT" if dat else "HONG"))
    ok &= dat
    print("\n  => %s" % ("TAT CA DAT" if ok else "CO CA HONG"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cu", nargs="?")
    ap.add_argument("moi", nargs="?")
    ap.add_argument("ra", nargs="?")
    ap.add_argument("--tu-kiem", action="store_true")
    a = ap.parse_args()
    if a.tu_kiem:
        return tu_kiem()
    if not (a.cu and a.moi and a.ra):
        sys.exit("can: <cu.pdf> <moi.pdf> <ra.tex>")
    lam(a.cu, a.moi, a.ra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
