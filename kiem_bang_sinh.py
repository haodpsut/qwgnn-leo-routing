#!/usr/bin/env python3
"""Cổng: bảng SINH TU phải khớp bản sinh lại, và dải gộp phải đặt đúng bảng.

⛔ VÌ SAO CÓ TỆP NÀY. Trong một buổi, bốn chuyện cùng xảy ra trên thư mục `paper/`:

  1. Tôi sửa tay sáu tệp `.tex` mang dòng "SINH TU ... DUNG SUA TAY". Lần chạy bộ sinh
     kế tiếp xoá sạch, không cổng nào kêu.
  2. Một caption mang HAI câu nói ngược nhau: câu gõ tay "median 0.908 spanning 0.863 to
     0.928, across all three run sets" (di sản của bản v1 BỊ REJECT, hồi đó gộp 17 đơn vị)
     nằm cạnh câu macro "29 đơn vị, bốn run set". Cả hai dịch sạch, 0 lỗi LaTeX.
  3. Tôi chèn câu "đọc giá trị gộp" vào ĐÚNG BA bảng KHÔNG thuộc phép gộp (decode,
     ablation, cost) và bỏ sót cả ba bảng thuộc phép gộp (summary, fair, scale). Một dải
     gộp dán lên bảng ngoài pool là tuyên bố SAI về độ phủ.
  4. Phép chèn của tôi đặt `" + POOLED_NGOAI + r"` vào giữa một literal r\"\"\"...\"\"\",
     nên văn bản đó in NGUYÊN VĂN vào caption. LaTeX không kêu một chữ.

Thân bài `sec:pooled` còn kể BA lần đo trong khi bộ gộp lấy BỐN run set, và tệp
`tab-summary.tex` khai nguồn sinh là `code/experiments/...` tức bản 27/08 đã chết.

    python3 kiem_bang_sinh.py
    python3 kiem_bang_sinh.py --tu-kiem
"""
import argparse
import difflib
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _bo_cuc():
    """Tìm `paper/` và `experiments/` theo CẢ HAI bố cục.

    ⛔ Hai bố cục thật, và cổng phải chạy được ở cả hai:
      - thư mục bài:  <bai>/paper  +  <bai>/repo/experiments
      - trong gói nộp / trong kho: <goi>/paper  +  <goi>/repo/experiments, mà cổng lại
        nằm ở <goi>/repo/, nên phải đi LÊN một bậc.
    Bản đầu chỉ biết bố cục thứ nhất, nên bản chép vào kho tự nó không chạy được -- tức
    README hứa một phép kiểm mà hiện vật không thực hiện được.
    """
    for goc in (HERE, os.path.dirname(HERE)):
        p = os.path.join(goc, "paper")
        for e in (os.path.join(goc, "repo", "experiments"), os.path.join(goc, "experiments")):
            if os.path.isdir(p) and os.path.isdir(e):
                return p, e
    return os.path.join(HERE, "paper"), os.path.join(HERE, "repo", "experiments")


PAPER, EXP = _bo_cuc()
# Goc goi = thu muc chua `paper/`. Dau "SINH TU repo/experiments/..." trong tep .tex la
# duong dan TUONG DOI VOI GOC GOI, khong phai voi cho dat cong nay.
GOC = os.path.dirname(PAPER)

# Bang sinh boi make_figs_tables.py: ten ham -> ten tep
# (khong go tay danh sach nay; cong tu doc main() cua bo sinh)
DAU_TRONG = r"\emph{Pooled:}"
DAU_NGOAI = "not among the run sets pooled"
# Mot bang co the TU KHAI pham vi run set cua no thay vi dung hai cau tren.
TU_KHAI = ("no entry is combined across run sets",
           "Read down a block, not across blocks",
           r"run set \texttt{")


def doc(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def nap(ten, paper=None):
    """Nạp một bộ sinh, trỏ PAPER của nó sang thư mục khác nếu cần.

    ⛔ Gán `m.PAPER` là KHÔNG ĐỦ. `make_claims.py` buộc `OUT_JSON` và `OUT_TEX` ngay ở
    mức module (dòng 32-33), nên hai đường dẫn đó đã đóng băng vào `paper/` THẬT lúc
    import. Bản đầu của cổng này vì thế GHI VÀO `paper/` thật trong lúc đang kiểm nó:
    một công cụ xác minh tự sửa hiện vật mình xác minh. Nên phải đổi MỌI biến mức module
    có giá trị là đường dẫn nằm dưới PAPER, và G5 còn tự kiểm là `paper/` không đổi.
    """
    p = os.path.join(EXP, ten)
    spec = importlib.util.spec_from_file_location("bs_" + ten[:-3], p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if paper:
        that = m.PAPER
        for k, v in list(vars(m).items()):
            if isinstance(v, str) and v.startswith(that + os.sep):
                setattr(m, k, os.path.join(paper, os.path.relpath(v, that)))
        m.PAPER = paper
    return m


def bam(d):
    """Vân tay thư mục: tên tệp -> băm nội dung, để chứng minh cổng không ghi vào."""
    import hashlib
    out = {}
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if os.path.isfile(p):
            out[f] = hashlib.sha256(io.open(p, "rb").read()).hexdigest()
    return out


def pool_run_set():
    """Danh sách CSV mà phép gộp 264 thật sự lấy, đọc TỪ MÃ chứ không gõ tay."""
    s = doc(os.path.join(EXP, "make_claims.py"))
    i = s.index("pooled_w264_fixedtau.csv")
    j = s.rindex("for f, col, flt in (", 0, i)
    return sorted(set(re.findall(r'"(\w+\.csv)"', s[j:i])))


def nguon_bang():
    """Mỗi `def tab_X` trong make_figs_tables.py lấy số từ những CSV nào."""
    s = doc(os.path.join(EXP, "make_figs_tables.py"))
    out = {}
    kh = [(m.start(), m.group(1)) for m in re.finditer(r"^def (tab_\w+)", s, re.M)]
    for k, (i, ten) in enumerate(kh):
        j = kh[k + 1][0] if k + 1 < len(kh) else len(s)
        tep = re.search(r'return w\("([\w-]+\.tex)"', s[i:j])
        if tep:
            out[tep.group(1)] = sorted(set(re.findall(r'rd\("(\w+\.csv)"\)', s[i:j])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tu-kiem", action="store_true")
    ap.add_argument("--paper", default=PAPER)
    a = ap.parse_args()
    if a.tu_kiem:
        return tu_kiem()

    loi = []
    tex = sorted(f for f in os.listdir(a.paper) if f.endswith(".tex"))
    print("== Cong bang sinh / dai gop ==\n")

    # ---- G1: rac Python lot vao .tex ----------------------------------------
    # Mau NGUY HIEM: phep noi chuoi Python ("..." + TEN + r"...") hoac mot ten
    # bien cua bo sinh. KHONG bat dau `+` tran, vi LaTeX dung `+` hop phap.
    RAC = [re.compile(r'"\s*\+\s*[A-Za-z_]\w*\s*\+\s*r?"'),
           re.compile(r"\b(?:POOLED|CAP|PRE|HDR)_[A-Z]\w*")]
    g1 = []
    for f in tex:
        s = doc(os.path.join(a.paper, f))
        for rx in RAC:
            m = rx.search(s)
            if m:
                g1.append("%s: %r" % (f, m.group(0)))
                break
    print("  %s G1 khong co rac Python trong .tex%s"
          % ("DAT " if not g1 else "HONG", "" if not g1 else "  [" + "; ".join(g1) + "]"))
    if g1:
        loi.append("G1")

    # ---- G2: cau noi ve dai gop phai dung macro, khong duoc go tay chu so ----
    # ⛔ Ban dau cong nay chia cau tren CA tep roi bat moi so 0.xxx cung xuat hien voi
    #    "sec:pooled". `tab-summary.tex` la bang, khong co dau cau, nen ca tep thanh MOT
    #    "cau" va cong bao 20 bao dong gia. Pham vi dung la VAN XUOI cua caption, va chi
    #    nhung chu so dung NGAY CANH tu ngu cua phep gop moi dang ke.
    #    Mo rong sau lan tiem dau: chi quet caption thi mot con so gop go tay nam trong
    #    VAN XUOI than bai se lot. Nen quet moi van xuoi, chi BO hang du lieu tabular.
    GOP = re.compile(r"\b(pool\w*|median|spanning|range)\b", re.I)
    TABULAR = re.compile(r"\\begin\{tabular\}.*?\\end\{tabular\}", re.S)
    g2 = []
    for f in tex:
        s = TABULAR.sub(" ", doc(os.path.join(a.paper, f)))
        for cau in re.split(r"(?<=\.)\s+", s):
            if "sec:pooled" not in cau or r"\clm{pooled-" in cau:
                continue
            if re.search(r"\b0\.\d{3}\b", cau) and GOP.search(cau):
                g2.append("%s: %s" % (f, ", ".join(re.findall(r"\b0\.\d{3}\b", cau))))
    print("  %s G2 moi cau dan sec:pooled dung macro, khong go tay chu so%s"
          % ("DAT " if not g2 else "HONG", "" if not g2 else "  [" + "; ".join(g2) + "]"))
    if g2:
        loi.append("G2")

    # ---- G3: dai gop dat dung bang ------------------------------------------
    # ⛔ Dai gop CHI noi ve phan so hoi phuc (recovered fraction). `tab-cost` dem so luot
    #    AoN va `tab-msa` dem so vong lap; ca hai co chu "264" nhung dan dai gop vao do la
    #    SAI don vi. Ban dau cong bat theo chu "264" nen bao dong gia dung hai bang nay.
    pool = set(pool_run_set())
    g3 = []
    for f, csvs in sorted(nguon_bang().items()):
        p = os.path.join(a.paper, f)
        if not os.path.exists(p):
            continue
        s = doc(p)
        trong = bool(set(csvs) & pool)
        if not trong and DAU_TRONG in s:
            g3.append("%s KHONG thuoc pool ma lai tro vao dai gop" % f)
            continue
        if "264" not in s or not re.search(r"recovered fraction", s, re.I):
            continue
        # Bang THUOC pool phai hoac dan dai gop, hoac TU KHAI ro la khong gop cheo run set
        # (`tab-matched` lam the: "no entry is combined across run sets"). Do la phat bieu
        # dung, khong phai loi noi long.
        if trong and DAU_TRONG not in s and not any(t in s for t in TU_KHAI):
            g3.append("%s lay so tu %s (TRONG pool) ma khong dan dai gop, cung khong tu khai"
                      % (f, ",".join(sorted(set(csvs) & pool))))
        if not trong and DAU_NGOAI not in s and not any(t in s for t in TU_KHAI):
            g3.append("%s ngoai pool, bao phan so hoi phuc tren 264, ma khong khai run set" % f)
    print("  %s G3 dai gop chi dan o bang THUOC phep gop%s"
          % ("DAT " if not g3 else "HONG", "" if not g3 else "\n       - " + "\n       - ".join(g3)))
    if g3:
        loi.append("G3")

    # ---- G4: so run set trong than bai = so run set bo gop thuc su lay ------
    CHU = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    body = doc(os.path.join(a.paper, "main.tex"))
    m = re.search(r"measured in (\w+)\s+separate run sets", body)
    thay = m.group(1) if m else "(khong tim thay cau)"
    mong = CHU.get(len(pool), str(len(pool)))
    ok4 = thay == mong
    print("  %s G4 than bai khai '%s' run set, bo gop lay %d (%s)"
          % ("DAT " if ok4 else "HONG", thay, len(pool), mong))
    if not ok4:
        loi.append("G4")

    # ---- G5: tep SINH TU phai khop ban sinh lai -----------------------------
    tmp = tempfile.mkdtemp()
    for f in tex:
        shutil.copy(os.path.join(a.paper, f), tmp)
    for j in os.listdir(a.paper):
        if j.endswith(".json"):
            shutil.copy(os.path.join(a.paper, j), tmp)
    # Dat mtime = 0 cho moi tep vua sao: sau khi chay bo sinh, tep nao mtime > 0 la tep
    # bo sinh GHI RA. Cach nay khong phu thuoc do min cua dong ho tep.
    for f in os.listdir(tmp):
        os.utime(os.path.join(tmp, f), (0, 0))
    truoc = bam(a.paper)
    cwd = os.getcwd()
    try:
        for ten in ("make_claims.py", "make_figs_tables.py"):
            m = nap(ten, paper=tmp)
            os.chdir(EXP)
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                m.main()
    except Exception as e:
        print("  HONG G5 khong chay lai duoc bo sinh: %s" % e)
        loi.append("G5")
        tmp = None
    finally:
        os.chdir(cwd)

    # G5b: cong KHONG duoc ghi vao paper/ trong luc kiem. Day la loi that cua ban dau.
    sau = bam(a.paper)
    doi = sorted(k for k in sau if truoc.get(k) != sau[k])
    print("  %s G5b cong khong tu ghi vao paper/ khi dang kiem%s"
          % ("DAT " if not doi else "HONG", "" if not doi else "  [da sua: " + ", ".join(doi) + "]"))
    if doi:
        loi.append("G5b")

    if tmp:
        # ⛔ Tap tep can kiem lay tu BAN SINH LAI, khong lay tu dong "SINH TU" con nam
        #    trong tep o `paper/`. Tiem loi lan dau cho thay: xoa dong dau la cong im,
        #    vi no loc theo chinh cai dau no dang kiem. Bo sinh moi la nguon su that ve
        #    "tep nao la tep sinh".
        sinh = sorted(f for f in os.listdir(tmp)
                      if f.endswith(".tex") and os.path.getmtime(os.path.join(tmp, f)) > 0)
        g5 = []
        for f in sinh:
            p0 = os.path.join(a.paper, f)
            if not os.path.exists(p0):
                g5.append("%s (bo sinh tao ra ma paper/ KHONG CO)" % f)
                continue
            s0, s1 = doc(p0), doc(os.path.join(tmp, f))
            if s0 != s1:
                d = list(difflib.unified_diff(s0.splitlines(), s1.splitlines(), lineterm="", n=0))
                g5.append("%s (%d dong lech)" % (f, sum(1 for x in d if x[:1] in "+-")))
        print("  %s G5 moi tep SINH (%d tep) khop ban sinh lai, khong sua tay%s"
              % ("DAT " if not g5 else "HONG", len(sinh),
                 "" if not g5 else "\n       - " + "\n       - ".join(g5)))
        if g5:
            loi.append("G5")

        # G5c: moi tep SINH phai CO dau nguon. Khong co dau thi lan sau khong ai biet
        #      no la tep sinh, va dung la cach lam G5/G6 im o ban dau.
        g5c = [f for f in sinh if "SINH TU" not in doc(os.path.join(a.paper, f))[:200]
               and "Auto-generated" not in doc(os.path.join(a.paper, f))[:200]]
        print("  %s G5c moi tep SINH deu CO dau nguon%s"
              % ("DAT " if not g5c else "HONG", "" if not g5c else "  [" + ", ".join(g5c) + "]"))
        if g5c:
            loi.append("G5c")

    # ---- G6: dau SINH TU phai tro vao ban SONG, va khong duoc NHAP NHANG ----
    # ⛔ `make_claims.py`, `make_figs_tables.py`, `make_r5_figs.py` ton tai o CA `code/`
    #    (ban 27/08 da chet) va `repo/`. `tab-summary.tex` tung khai "SINH TU
    #    code/experiments/make_claims.py", tuc chi nguoi doc ve ban chet; ma `PAPER` cua
    #    ban code/ lai tro dung vao `paper/` dang song, nen chay nham la bai quay ve
    #    thang 8. Vi vay ten TRAN bi coi la loi khi no ung voi nhieu hon mot bo sinh.
    THU_MUC = [os.path.join(GOC, "repo", "experiments"),
               os.path.join(GOC, "code", "experiments")]
    g6 = []
    for f in tex:
        h = doc(os.path.join(a.paper, f))[:200]
        for m in re.finditer(r"SINH TU ([\w/.-]+\.py)", h):
            ten = m.group(1)
            if "/" in ten:
                if not os.path.exists(os.path.join(GOC, ten)):
                    g6.append("%s -> %s (khong ton tai)" % (f, ten))
            else:
                co = [d for d in THU_MUC if os.path.exists(os.path.join(d, ten))]
                if not co:
                    g6.append("%s -> %s (khong tim thay o dau)" % (f, ten))
                elif len(co) > 1:
                    g6.append("%s -> %s (ten TRAN ma co %d ban: %s)"
                              % (f, ten, len(co),
                                 ", ".join(os.path.relpath(d, GOC) for d in co)))
    print("  %s G6 dau SINH TU tro vao tep CO THAT%s"
          % ("DAT " if not g6 else "HONG", "" if not g6 else "  [" + "; ".join(g6) + "]"))
    if g6:
        loi.append("G6")

    print("\n  pool 264 gom %d run set: %s" % (len(pool), ", ".join(sorted(pool))))
    print("\n=> %s (%d loi)" % ("DAT" if not loi else "CHUA DAT", len(loi)))
    return 0 if not loi else 1


def tu_kiem():
    """Đối chứng DƯƠNG: tiêm từng lỗi vào bản sao, cổng phải bắt ĐÚNG cổng đó."""
    import subprocess
    print("== TU KIEM cong bang sinh ==\n")
    ok = True
    goc = tempfile.mkdtemp()
    for f in os.listdir(PAPER):
        if f.endswith((".tex", ".json")):
            shutil.copy(os.path.join(PAPER, f), goc)

    def chay(d):
        return subprocess.run([sys.executable, os.path.abspath(__file__), "--paper", d],
                              capture_output=True, text=True).stdout

    def thu(nhan, ma, mong_hong, sua):
        d = tempfile.mkdtemp()
        for f in os.listdir(goc):
            shutil.copy(os.path.join(goc, f), d)
        if sua:
            sua(d)
        out = chay(d)
        dong = [l for l in out.splitlines() if " " + ma + " " in l]
        hong = bool(dong) and dong[0].strip().startswith("HONG")
        dat = hong == mong_hong
        print("  %-62s %s" % (nhan, "DAT" if dat else "HONG"))
        return dat

    def noi(d, f, them):
        # ⛔ DOC xong moi GHI. Ban dau viet io.open(p,"w").write(doc(p)...): Python danh gia
        #    io.open(p,"w") TRUOC, cat tep ve rong, roi doc(p) doc ra chuoi rong -- nen phep
        #    tiem khong tiem gi ca, chi xoa tep. Sau sau phep thu bao "khong bat duoc" la vi
        #    the, va no con lam sau phep thu "ban SACH phai im" DAT MOT CACH RONG.
        p = os.path.join(d, f)
        s = doc(p)
        assert r"\end{table}" in s, "khong tim thay moc tiem trong " + f
        io.open(p, "w", encoding="utf-8").write(s.replace(r"\end{table}", them + "\n\\end{table}"))

    def thay(d, f, cu, moi):
        p = os.path.join(d, f)
        s = doc(p)
        assert cu in s, "khong tim thay %r trong %s" % (cu[:40], f)
        io.open(p, "w", encoding="utf-8").write(s.replace(cu, moi))

    ok &= thu("ban SACH: G1 phai im", "G1", False, None)
    ok &= thu("ban SACH: G2 phai im", "G2", False, None)
    ok &= thu("ban SACH: G3 phai im", "G3", False, None)
    ok &= thu("ban SACH: G4 phai im", "G4", False, None)
    ok &= thu("ban SACH: G5 phai im", "G5", False, None)
    ok &= thu("ban SACH: G6 phai im", "G6", False, None)

    ok &= thu("tiem rac Python vao caption: G1 HONG", "G1", True,
              lambda d: noi(d, "tab-cost.tex", 'x " + POOLED_NGOAI + r" y'))
    ok &= thu("tiem cau dan sec:pooled voi chu so go tay: G2 HONG", "G2", True,
              lambda d: noi(d, "tab-cost.tex",
                            r"Pooling gives a median of 0.908 (Sec.~\ref{sec:pooled})."))
    ok &= thu("dan dai gop vao bang NGOAI pool (tab-decode): G3 HONG", "G3", True,
              lambda d: noi(d, "tab-decode.tex", DAU_TRONG + " 264 blah."))
    ok &= thu("bo cau gop khoi bang TRONG pool (tab-scale): G3 HONG", "G3", True,
              lambda d: thay(d, "tab-scale.tex", DAU_TRONG, r"\emph{Note:}"))
    ok &= thu("than bai khai 'three' run set: G4 HONG", "G4", True,
              lambda d: thay(d, "main.tex", "measured in four\nseparate run sets",
                             "measured in three\nseparate run sets"))
    ok &= thu("sua tay mot tep SINH TU: G5 HONG", "G5", True,
              lambda d: noi(d, "tab-ablation.tex", "% mot dong sua tay"))
    ok &= thu("dau SINH TU tro vao tep khong ton tai: G6 HONG", "G6", True,
              lambda d: thay(d, "tab-cost.tex", "SINH TU repo/experiments/make_figs_tables.py",
                             "SINH TU repo/experiments/khong_co_dau.py"))

    print("\n  => %s" % ("TAT CA DAT" if ok else "CO CA HONG"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
