"""Cong: trong bo cuc HAI COT, khong gi duoc vuot bien COT sang mang giua.

    python code/scripts/check_column_bleed.py --pdf paper/main.pdf

⛔ VI SAO CO FILE NAY. 27/08/2026 Hao bao "table 2 dang tran width". Luc do bai da qua:

    pdflatex        0 loi, 0 Overfull
    check_figure_quality  DANGEROUS 0
    g7_final_sweep  DANGEROUS 0, REVISABLE 0, POLISH 0

va phep do toa do chu cua chinh toi cung bao "0/17 trang tran". Ba tang kiem deu xanh
tren mot trang ma cot gia tri cua Bang II in de len than chu cua cot ben canh.

Ly do rat cu the: toi lay bien PHAI CUA TRANG (563pt) lam nguong. Trong bo cuc mot cot
do la dung. Trong bo cuc HAI COT thi khong: mot bang o cot TRAI co the chay toi 310pt --
qua bien cot trai (305pt) va vao mang giua -- ma van con cach bien trang 250pt. Do la
kiem SAI NGUONG chu khong phai thieu kiem, va no cho ra mau xanh dep nhat trong ca buoi.

`Overfull \\hbox` cung khong bat duoc: LaTeX chi keu khi mot hop vuot \\hsize cua no. Mot
`tabular` rong hon cot khong lam \\hbox tran neu no duoc dat trong mot moi truong noi.

CACH LAM. Do hinh hoc hai cot TU CHINH BAI (khong go cung): lay cac tu tren nhieu trang,
gom xMin thanh hai cum, suy ra bien moi cot. Roi bao moi tu BAT DAU trong mot cot ma
KET THUC ngoai cot do.

MIEN TRU: tieu de bai va cac moi truong trai hai cot (figure*/table*) that su rong het
trang. Chung duoc nhan ra bang cach chinh chung TRAI DAI qua ca hai cot, nen dieu kien
mien tru la "tu nay nam trong mot dai y ma dai do co chu o CA HAI cot".
"""
import argparse
import re
import subprocess
import sys


def words(pdf, page):
    subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf, "/tmp/_cb.xml"],
                   capture_output=True)
    s = open("/tmp/_cb.xml", encoding="utf-8").read()
    return [(float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), m.group(5))
            for m in re.finditer(
                r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', s)]


def npages(pdf):
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    return int(out.split("Pages:")[1].split()[0])


def geometry(pdf, n):
    """Suy bien hai cot tu chinh bai.

    ⛔ DUNG MODE, KHONG DUNG MIN. Ban truoc lay xMin NHO NHAT cua nua phai lam moc cot phai,
    va mot bang le bat dau som keo moc do tu 312 xuong 305. Cot trai vi the duoc coi la
    rong hon 7pt so voi thuc te, va dung 7pt ay che mat cai bang dang ri ra. Le trai cua
    THAN CHU la gia tri LAP LAI NHIEU NHAT, khong phai gia tri cuc tieu.
    """
    from collections import Counter
    lefts, rights, rmax = Counter(), Counter(), 0.0
    for p in range(2, min(n, 9) + 1):
        for x0, y0, x1, y1, t in words(pdf, p):
            (lefts if x0 < 300 else rights)[round(x0)] += 1
            rmax = max(rmax, x1)
    if not lefts or not rights:
        return None
    l0 = lefts.most_common(1)[0][0]
    r0 = rights.most_common(1)[0][0]
    return float(l0), float(r0), rmax


def full_width_captions(tex):
    """Cac moi truong figure*/table* trong .tex -> vai tu dau cua chu thich."""
    if not tex:
        return []
    src = open(tex, encoding="utf-8").read()
    d = __import__("os").path.dirname(__import__("os").path.abspath(tex))
    for f in re.findall(r"\\input\{([^}]+)\}", src):
        q = __import__("os").path.join(d, f if f.endswith(".tex") else f + ".tex")
        if __import__("os").path.exists(q):
            src += "\n" + open(q, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"\\begin\{(?:figure|table)\*\}(.*?)\\end\{(?:figure|table)\*\}",
                         src, re.S):
        c = re.search(r"\\caption\{", m.group(1))
        if not c:
            continue
        body = m.group(1)[c.end():]
        plain = re.sub(r"\\[a-zA-Z]+\s*|[{}$\\]", " ", body)
        ws = [x for x in plain.split() if len(x) > 2][:4]
        if ws:
            out.append(ws)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--tex", help="main.tex, de doc cac moi truong TRAI HAI COT")
    ap.add_argument("--tol", type=float, default=1.5, help="dung sai, pt")
    a = ap.parse_args()

    n = npages(a.pdf)
    g = geometry(a.pdf, n)
    if not g:
        print("  ⛔ khong suy duoc hinh hoc cot -- khong doc thanh sach")
        return 1
    l0, r0, rmax = g
    colw = rmax - r0
    L1 = l0 + colw                     # bien phai cot trai
    print("  hinh hoc suy tu bai: cot trai %.0f..%.0f | cot phai %.0f..%.0f (rong %.0fpt)"
          % (l0, L1, r0, rmax, colw))

    caps = full_width_captions(a.tex)
    full_width_y = {}
    for p in range(1, n + 1):
        ww = words(a.pdf, p)
        flat = " ".join(t for *_, t in ww)
        for ws in caps:
            # ⛔ KHOP THEO TAP TU, KHONG THEO CUM TU LIEN. Trong ban DANH DAU, latexdiff chen
            # lenh va tu vao giua chu thich, nen cum "4 tu dau" vo va float khong duoc nhan
            # ra ⇒ cong bao mot chu thich figure* trai ngang la "tran cot". Do 28/08 tren bai
            # IoT-70170: ban sach PASS, ban danh dau FAIL, cung mot hinh, khac moi dau sua.
            # Doi hoi da so tu xuat hien thi song duoc qua moi kieu chen cua latexdiff.
            toks = set(x.lower() for x in ws)
            have = set(x.lower() for *_, x in ww)
            if len(toks & have) >= max(2, len(toks) - 1):
                ys = [y for x0, y, x1, y1, t in ww if t.lower() in toks]
                if ys:
                    full_width_y.setdefault(p, []).append(max(ys))
    if a.tex:
        print("  moi truong trai hai cot khai trong .tex: %d, thay tren %d trang"
              % (len(caps), len(full_width_y)))

    total, pages = 0, 0
    for p in range(1, n + 1):
        w = words(a.pdf, p)
        if not w:
            continue
        # ⛔ MIEN TRU DAI TRAI HAI COT. Mot dong thuoc figure*/table*/tieu de co chu o CA HAI
        # phia mang giua tren cung mot dai y. Neu khong mien tru, tieu de bai bi bao la loi.
        # ⛔ GOM DONG THEO DAI, khong theo round(y0). Chu cung mot dong co y0 lech nhau vai
        # phan muoi (chan chu, chi tren chi duoi), nen round() tach chung thanh hai nhom va
        # mien tru "trai hai cot" truot -- tieu de bai bi bao la loi trong khi no dung la
        # trai hai cot. Dai 3pt gom du mot dong ma khong nuot dong ke tiep.
        def key(y):
            return int(y // 3)
        band = {}
        for x0, y0, x1, y1, t in w:
            band.setdefault(key(y0), []).append((x0, x1))
        # ⛔ MIEN TRU: chi dai nao co mot tu BAT DAU DUNG O LE cot phai (trong 2pt) moi la
        # dai hai cot. Dai trai het trang (tieu de, figure*) chay lien mach nen khong tu nao
        # roi dung vao le do. Tieu chi "vuon sau vao cot phai" cua ban truoc mien tru MOI
        # dai, vi trong bo cuc hai cot dai nao cung co chu cot phai vuon sau -- no bien cong
        # thanh vo dung ma van bao PASS.
        # ⛔ MIEN TRU PHAI LAY TU BAI, KHONG SUY TU HINH DANG. Toi da thu ba tieu chi hinh
        # dang (co tu bat dau o le cot phai / vuon sau vao cot phai / dai ngang lon) va ca
        # ba deu hoac mien tru MOI THU hoac bao nham tieu de va figure*. Ly do don gian:
        # nhin vao toa do thi mot figure* rong het trang va mot bang ri ra khong khac nhau
        # ve NGUYEN TAC, chi khac ve Y DINH. Y dinh nam trong .tex chu khong trong PDF.
        spans = set()
        for y in band:
            near = [c for k in (y - 1, y, y + 1) for c in band.get(k, [])]
            if any(abs(x0 - r0) <= 2.0 for x0, _ in near):
                spans.add(y)
        # ⛔ Khoi tieu de trang 1 (\maketitle cua IEEEtran) trai ngang theo thiet ke va khong
        # phai figure*/table*, nen no khong nam trong danh sach doc tu .tex. Mien tru tu dau
        # trang toi dong "Abstract", va chi tren trang 1.
        if p == 1:
            ab = [y for x0, y, x1, y1, t in w if t.startswith("Abstract")]
            cut = min(ab) if ab else 0
            for y in list(band):
                if y * 3 <= cut:
                    spans.add(y)
        for cy in full_width_y.get(p, []):
            for y in band:
                if y * 3 <= cy + 6:        # moi thu PHIA TREN chu thich cua float trai ngang
                    spans.add(y)
        # ⛔ Dong chay dau trang ("IEEE TRANSACTIONS ... (SUBMITTED)  <so trang>") trai ngang
        # ca trang theo thiet ke va khong co tu nao dung o le cot phai, nen mien tru theo
        # VUNG chu khong theo hinh dang. Khai ro bang toa do de nguoi doc thay pham vi.
        HEAD_Y, FOOT_Y = 40.0, max(y for _, y, _, _, _ in w) - 8.0
        bad = [(x1, t, y0) for x0, y0, x1, y1, t in w
               if not (y0 < HEAD_Y or y0 > FOOT_Y)
               if x0 < L1 and x1 > L1 + a.tol and key(y0) not in spans]
        if bad:
            pages += 1
            total += len(bad)
            mx = max(x for x, _, _ in bad)
            print("  ⛔ trang %-2d: %d tu tran khoi cot trai, xa nhat %.1f (+%.1fpt): %s"
                  % (p, len(bad), mx, mx - L1,
                     ", ".join(repr(t) for _, t, _ in sorted(bad, key=lambda z: -z[0])[:5])))

    print("  da kiem %d trang: %d trang co chu tran khoi cot, %d tu" % (n, pages, total))
    if n == 0:
        print("  ⛔ KIEM 0 TRANG")
        return 1
    print("  => %s" % ("FAIL" if total else "PASS"))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
