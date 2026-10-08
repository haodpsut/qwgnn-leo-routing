#!/usr/bin/env bash
# Dung TRON GOI nop lai TNSM tu nguon. Chay tu goc du an: ./build-submit.sh
#
# Vi sao co file nay: truoc do goi duoc dung bang cac lenh go tay roi rac, nen khong ai
# dung lai duoc bang chung, va ban highlight tung bi lech font vi mot lan go quen co.
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$PWD
OUT=$ROOT/submit
mkdir -p "$OUT"

build() {                      # build <thu-muc> <ten-tex>
  ( cd "$1" && for i in 1 2 3; do
      pdflatex -interaction=nonstopmode -halt-on-error "$2.tex" >/dev/null 2>&1 \
        || { echo "LOI dung $1/$2.tex"; pdflatex -interaction=nonstopmode "$2.tex" | grep -m5 '^!'; exit 1; }
    done )
}

echo "== 1/5 so lieu va bang/hinh sinh tu CSV"
# ⛔ 08/10: dong nay tung tro vao `code/experiments` -- cay lam viec 27/08 DA CHET, ma
# `PAPER` cua no tro dung vao `paper/` dang song. Dung goi bang no la GHI DE toan bo ban
# sua cua vong nay bang noi dung thang 8, va goi zip thi KHONG chua thi nghiem r7_1 tra
# loi Phan bien 1 y 5. Cay song la `repo/`.
( cd repo/experiments && python3 make_claims.py >/dev/null \
                      && python3 make_figs_tables.py >/dev/null \
                      && python3 make_r5_figs.py >/dev/null \
                      && python3 emit_r7_macros.py >/dev/null )
cp repo/results/r7_macros.tex repo/results/tab-imperfect.tex paper/

echo "== 2/5 ban thao sach"
build paper main
cp paper/main.pdf "$OUT/manuscript.pdf"

echo "== 2b/5 ABSTRACT va SO TRANG, do tren BAN IN"
# ⛔ Khong he co cong nao dem abstract, va chinh vi the ban nop 28/08 di voi 317 tu de Phan
#    bien 2 phai nhac ("much too long"). TNSM ghi nguyen van: "a 75 to 200 word abstract".
#    Dem tren BAN IN, khong dem tren nguon: trong nguon moi \clm{...} la mot macro bi xoa khi
#    boc the, con tren ban in no la MOT TU (mot con so). Dem nguon ra 200 trong khi ban in la
#    194 -- hai so khac nhau, va cai duy nhat noi nhan doc la ban in.
python3 - "$OUT/manuscript.pdf" <<'PYEOF'
import re, subprocess, sys
pdf = sys.argv[1]
t = re.sub(r"\s+", " ", subprocess.run(["pdftotext", "-f", "1", "-l", "1", pdf, "-"],
                                       capture_output=True, text=True).stdout)
if "Abstract" not in t or "Index Terms" not in t:
    print("   ⛔ khong tim thay Abstract hoac Index Terms o trang 1"); sys.exit(1)
ab = t[t.index("Abstract") + 8:t.index("Index Terms")].lstrip("\u2014-\u2013 ")
n = len(ab.split())
ok = 75 <= n <= 200
print("   abstract %d tu, han TNSM 75-200 => %s" % (n, "PASS" if ok else "FAIL"))
tr = int(subprocess.run(["pdfinfo", pdf], capture_output=True, text=True)
         .stdout.split("Pages:")[1].split()[0])
print("   %d trang | thu bien tap doi 14 | TNSM thu phi den toi da 16 => %s"
      % (tr, "trong han" if tr <= 14 else "VUOT, phai khai trong cover letter"))
sys.exit(0 if ok else 1)
PYEOF

echo "== 3/5 ban danh dau chinh sua"
WORK=$(mktemp -d)
cp paper/*.tex paper/*.bib "$WORK"/ 2>/dev/null || true
cp -r paper/authors "$WORK"/ 2>/dev/null || true
# ⛔ Chep CA thu muc hinh. Thieu no thi ban danh dau nem loi "figures/*.pdf not found",
# LaTeX ve khung rong roi di tiep, va gia ban danh dau van ra PDF. Da mac dung loi nay
# o bai IoT-70170 hom qua: ban danh dau giao di voi 8/8 hinh TRONG.
cp -r paper/figures "$WORK"/ 2>/dev/null || true
# Lam phang \input va doi \cmidrule(lr){a-b} -> \cmidrulelr{a-b} TRUOC khi so.
# latexdiff khong doc duoc doi so trong ngoac TRON, no cat giua lenh va bao
# "Paragraph ended before \@@@cmidrule was complete" -- loi nay khong noi gi ve nguyen nhan.
python3 - "$ROOT" "$WORK" <<'PY'
import re, os, io, sys
root, work = sys.argv[1], sys.argv[2]
SHIM = "\\newcommand{\\cmidrulex}[2]{\\cmidrule(#1){#2}}\n"
def flatten(path):
    base = os.path.dirname(path)
    t = io.open(path, encoding="utf-8").read()
    def sub(m):
        f = os.path.join(base, m.group(1))
        f = f if f.endswith(".tex") else f + ".tex"
        return io.open(f, encoding="utf-8").read() if os.path.exists(f) else m.group(0)
    for _ in range(4):
        t = re.sub(r"\\input\{([^}]+)\}", sub, t)
    # MOI bien the: (lr), (l), (r). Lan truoc chi bat (lr) nen mot cai \cmidrule(l){4-6}
    # van lot va cong bao dung cai loi cu, y het nhu chua sua gi.
    t = re.sub(r"\\cmidrule\(([a-z]+)\)\{([^}]*)\}", r"\\cmidrulex{\1}{\2}", t)
    assert "\\cmidrule(" not in t, "con bien the \\cmidrule(..) chua doi"
    # Thay RUOT moi tabular bang mot the mo duc, o CA HAI ban. latexdiff chen danh dau vao
    # giua hang bang la sinh \noalign sai cho va bai khong dung duoc. Va danh dau tung ky tu
    # trong mot bang do script sinh lai TRON VEN thi cung khong noi len dieu gi: bang doi hay
    # khong doi la mot su kien, khong phai mot day ky tu. Sau khi so xong, the duoc tra lai
    # bang ruot cua ban MOI.
    bodies = []
    def stash(m):
        bodies.append(m.group(0))
        return "\\TABLESTASH{%d}" % (len(bodies) - 1)
    t = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", stash, t, flags=re.S)
    return t.replace("\\begin{document}", SHIM + "\\begin{document}", 1), bodies
new_bodies = []
# ⛔ MOC SO SANH PHAI LA BAN PHAN BIEN VONG NAY DA DOC, khong phai ban bi reject 16/08.
# Dung v1-rejected thi ban to sang danh dau ca lan viet lai cua vong 1, va chinh dieu do
# sinh ra "duplicated abstract/introduction text" ma Phan bien 1 vong 2 bao. Moc dung la
# nguon GIAI TU goi da nop 28/08, da xac thuc bang hai phat bieu doc lap cua phan bien:
# abstract 317 tu ("much too long") va KHONG co hinh mo hinh he thong.
for src, dst in ((os.path.join(root, "v2-submitted-2026-08-28/main.tex"), "old.tex"),
                 (os.path.join(root, "paper/main.tex"), "new.tex")):
    txt, bodies = flatten(src)
    if dst == "new.tex":
        new_bodies = bodies
    io.open(os.path.join(work, dst), "w", encoding="utf-8").write(txt)
io.open(os.path.join(work, "bodies.txt"), "w", encoding="utf-8").write(
    "\n%%TABLESPLIT%%\n".join(new_bodies))
PY
# Loai TITLE khoi phep so. latexdiff tron tieu de cu voi moi theo TUNG TU, cho ra mot dong
# vo nghia ngay dong dau bai: "...Amortizes Congestion-Aware A Reality Check on Learned
# Traffic Engineering...". Tieu de doi hay khong la mot SU KIEN, khong phai mot day ky tu;
# cover letter da noi ro no doi va doi thanh gi.
latexdiff --type=UNDERLINE --exclude-textcmd="section,subsection,title" \
  "$WORK/old.tex" "$WORK/new.tex" > "$WORK/diff.tex" 2>/dev/null
# Chi doi MAU, khong gach chan cung khong gach ngang: gach chan doi font nen trang danh dau
# doc khong cung co voi ban cuoi, va Hao da bat dung loi do mot lan.
python3 - "$WORK/diff.tex" "$WORK/bodies.txt" <<'PY'
import re, sys, io
p = sys.argv[1]; t = io.open(p, encoding="utf-8").read()
bodies = io.open(sys.argv[2], encoding="utf-8").read().split("\n%%TABLESPLIT%%\n")
# GO VO BOC truoc khi tra ruot. latexdiff boc the trong \DIFadd{...}, va nhet ca mot tabular
# vao doi so macro thi \midrule (dung \noalign) roi ra ngoai ngu canh alignment: LaTeX bao
# "Misplaced \noalign" o mot dong khong lien quan gi toi nguyen nhan.
# The nam tren dong %DIFDELCMD phai BI XOA, khong duoc tra ruot. latexdiff dung mot dong
# chu thich de giu lai lenh da xoa; nhet mot tabular NHIEU DONG vao do thi chi dong dau con
# bi chu thich, phan con lai thanh LaTeX song va \toprule roi ra ngoai tabular. Trieu chung
# la "Misplaced \noalign" o mot dong cach nguyen nhan hang tram dong.
t = re.sub(r"(%DIFDELCMD[^\n]*?)\\TABLESTASH\{\d+\}", r"\1", t)
t = re.sub(r"\\DIF(?:add|del)(?:FL)?\{\s*(\\TABLESTASH\{\d+\})\s*\}", r"\1", t)
# The mang chi so cua ban CU thi tro toi bang khong ton tai trong ban moi: bo han.
t = re.sub(r"\\TABLESTASH\{(\d+)\}",
           lambda m: bodies[int(m.group(1))] if int(m.group(1)) < len(bodies) else "", t)
t = re.sub(r"\\DIF(?:add|del)(?:FL)?\{\s*\}", "", t)
t = re.sub(r"\\providecommand\{\\DIFadd\}\[1\]\{[^\n]*\}",
           r"\\providecommand{\\DIFadd}[1]{{\\protect\\color[rgb]{0,0,0.75}#1}}", t)
t = re.sub(r"\\providecommand\{\\DIFdel\}\[1\]\{[^\n]*\}",
           r"\\providecommand{\\DIFdel}[1]{{\\protect\\color[rgb]{0.7,0,0}#1}}", t)
t = t.replace("\\usepackage[normalem]{ulem}", "")     # bo hoan toan gach chan/gach ngang
# ⛔ BO doan ghi chu o dau ban danh dau. Loi khai do phu nam o THU TRA LOI va COVER
# LETTER, la cho bien tap doc; nhet mot doan van vao dau ban danh dau lam trang dau
# kho doc va lap lai thu da noi o hai cho khac.
# ⛔ THAM CHIEU CUA BAN CU KHONG GIAI DUOC trong ban danh dau. latexdiff giu nguyen
# \ref{...} nam trong doan BI XOA, ma nhan do chi ton tai o ban v1, nen chung in ra "??".
# Do 28/08: 9 dau ?? trong ban danh dau. Chung khong sai ve noi dung -- doan do dang bi
# xoa -- nhung mot tai lieu gui di doc ma rai ?? thi nguoi doc khong phan biet duoc dau la
# "da xoa" va dau la "bai hong". Thay bang chu, giu nguyen y.
import re as _re
import os as _os
_wd = _os.path.dirname(_os.path.abspath(p))
_known = set(_re.findall(r"\\label\{([^}]+)\}",
                        io.open(_os.path.join(_wd, "new.tex"), encoding="utf-8").read()))
def _fix(m):
    return m.group(0) if m.group(1) in _known else "\\textup{[removed]}"
t = _re.sub(r"\\(?:ref|autoref|eqref)\{([^}]+)\}", _fix, t)
io.open(p, "w", encoding="utf-8").write(t)
PY
build "$WORK" diff
cp "$WORK/diff.pdf" "$OUT/manuscript-highlighted.pdf"

# DO DO PHU PHAN XOA. Ban danh dau tung khang dinh "do = da xoa" trong khi 89% cau bi bo
# khong he xuat hien: latexdiff khong can chinh noi hai ban khac nhau qua nhieu, va no
# that bai IM LANG. Cong nay in ti le that de loi chu thich khong bao gio vuot qua so do.
python3 - "$ROOT" "$WORK" <<'PY'
import re, io, sys, subprocess
root, work = sys.argv[1], sys.argv[2]
flat = lambda s: re.sub(r"\s+", " ", s)
# ⛔ MOC THU HAI. Buoc tinh thong ke nay doc mot ban PDF KHAC voi ban latexdiff so, va no
# van tro vao v1-rejected sau khi moc so sanh da doi: ket qua la "mat 46%, moi 68%" cho
# mot vong chi them mot muc (so dong that: 291/1400 ~ 21%). Hai nguon mot phep do, va
# khong cong nao hoi chung co noi giong nhau.
old = flat(subprocess.run(["pdftotext", root+"/v2-submitted-2026-08-28/main.pdf","-"],
                          capture_output=True, text=True).stdout)
new = flat(subprocess.run(["pdftotext", root+"/paper/main.pdf","-"],
                          capture_output=True, text=True).stdout)
dif = flat(io.open(work+"/diff.tex", encoding="utf-8").read())
gone = [flat(s).strip()[:60] for s in re.split(r"(?<=[.])\s", old)
        if len(flat(s).strip()) >= 80 and flat(s).strip()[:60] not in new]
shown = [c for c in gone if c in dif]
pct = 100*len(shown)/max(1, len(gone))
print(f"   cau cu bi bo: {len(gone)} | hien trong ban danh dau: {len(shown)} ({pct:.0f}%)")
io.open("/tmp/_mk.txt", "w").write("%d cau bo\n" % len(gone))
# ⛔ HAI CON SO NAY PHAI SINH RA, KHONG GO TAY. Cover letter tung ghi "42% da mat, 56% la
# moi"; sau vai lan sua ban thao chung thanh 38% va 57% con la thu van in so cu. Dung lop
# loi "mat tien in so cu" da cat chinh bai nay ngay 18/08.
so = [x for x in (flat(y).strip() for y in re.split(r"(?<=[.])\s", old)) if len(x) >= 80]
sn = [x for x in (flat(y).strip() for y in re.split(r"(?<=[.])\s", new)) if len(x) >= 80]
pg = 100*len([x for x in so if x[:60] not in new])/max(1, len(so))
pn = 100*len([x for x in sn if x[:60] not in old])/max(1, len(sn))
io.open(root+"/submit/markup-stats.tex", "w", encoding="utf-8").write(
    "%% SINH TU build-submit.sh -- DUNG SUA TAY.\n"
    "\\newcommand{\\pctGone}{%.0f}\n\\newcommand{\\pctNew}{%.0f}\n"
    "\\newcommand{\\pctShown}{%.0f}\n" % (pg, pn, pct))
print(f"   -> submit/markup-stats.tex: mat {pg:.0f}%, moi {pn:.0f}%, danh dau {pct:.0f}%")
if pct < 90:
    print(f"   ! chu thich ban danh dau PHAI noi ro phan xoa la KHONG day du ({pct:.0f}%)")
PY

# ⛔ HAI BAN PHAI CO CUNG SO HINH. Loi nay da xay ra HAI LAN va ca hai lan nguoi doc phat
# hien chu khong phai cong: Hinh 3 hien trong manuscript.pdf va la mot O TRONG trong
# manuscript-highlighted.pdf, vi hai bo sinh cung ghi paper/fig-speedup.tex nen ban nao
# chay sau thi thang. Trieu chung dac trung: khong tep nao hong, khong lenh nao bao loi,
# chi la HAI BAN KHAC NHAU. Nen phai so hai ban voi nhau chu khong kiem tung ban.
#
# Dem HINH NHUNG THAT bang pdfimages, khong grep \includegraphics: ban danh dau dinh nghia
# lai \includegraphics trong phan dau, nen grep tung bao "can 11, duoc 8" tren mot ban hoan
# toan dung.
echo "== 3e/5 DANH SACH THAY DOI, phu 100% phan xoa"
# ⛔ Ban to sang chi dat lai duoc mot phan so cau da xoa vao ngu canh. Phan con lai bien mat
#    khoi no ma khong dau vet, va Phan bien 1 vong 2 da mat mot luot nhan xet vao dung cho do.
#    Hien vat nay liet ke DU, sinh tu hai BAN IN nen khong co moi noi nao de dinh chu.
python3 "$ROOT/repo/scripts/make_change_list.py" \
        "$ROOT/v2-submitted-2026-08-28/main.pdf" "$OUT/manuscript.pdf" \
        "$OUT/change-list.tex" | tee /tmp/_cl.txt
build submit change-list
# Doi chieu: so cau bi bo o danh sach PHAI bang so cua buoc thong ke (3/5). Hai nguon mot
# phep do thi phai noi giong nhau, neu khong thi mot trong hai dang do sai.
python3 - "$OUT" /tmp/_cl.txt <<'PYEOF'
import io, os, re, sys
out, log = sys.argv[1], sys.argv[2]
n_cl = int(re.search(r"(\d+) cau bo", io.open(log).read()).group(1))
st = io.open(out + "/markup-stats.tex").read()
m = re.search(r"\\newcommand\{\\pctShown\}\{(\d+)\}", st)
n_tk = int(re.search(r"(\d+) cau bo", io.open("/tmp/_mk.txt").read()).group(1)) \
    if os.path.exists("/tmp/_mk.txt") else n_cl
print("   danh sach: %d cau bo | ban danh dau dat lai duoc %s%% trong so do" % (n_cl, m.group(1)))
if n_cl != n_tk:
    print("   ⛔ LECH: buoc thong ke dem %d, danh sach dem %d. Hai nguon mot phep do." % (n_tk, n_cl))
sys.exit(1 if n_cl != n_tk else 0)
PYEOF

echo "== 3a/5 phu luc (ComSoc: phu luc phai duoc nop kem de phan bien doc)"
build paper supplementary
cp paper/supplementary.pdf "$OUT/supplementary.pdf"

echo "== 3b/5 MOI HINH PHAI CO MAT THAT O CA HAI BAN"
# ⛔ BON CACH DEU SAI, va toi da thu ca bon truoc khi den cach nay:
#   grep \includegraphics : ban danh dau dinh nghia lai macro do, nen grep tung bao
#                            "can 11, duoc 8" tren mot ban hoan toan dung;
#   pdfimages -list        : chi dem anh RASTER. Hinh o day la vector => dem 0 tren CA HAI
#                            ban, tuc cong bao dong gia 100%;
#   so trung tu trong hinh : chu trong hinh ("time per slot", "features") TRUNG voi tu ngu
#                            than bai, nen bo hinh di ma do phu van 100%;
#   dem so lan xuat hien   : cung ly do, 9/9 token van du sau khi hinh bien mat.
# Cach duy nhat phan biet duoc: TIM MANH LUONG BYTE cua tung tep hinh trong PDF cuoi.
# pdflatex nhung nguyen luong noi dung cua hinh vector, nen manh byte co mat <=> hinh co
# mat that. Do duoc: bo hinh 3 di thi no tut 2/3 -> 0/3, trong khi moi phep kiem chu deu
# khong doi. Va chinh phep kiem nay tim ra fig_denominator_drift duoc SINH RA nhung khong
# he duoc \input vao bai.
python3 - "$ROOT" "$OUT" <<'PYEOF'
import glob, os, re, subprocess, sys
root, out = sys.argv[1], sys.argv[2]
def chunks(p, n=3, ln=48):
    b = open(p, "rb").read()
    i = b.find(b"stream")
    if i < 0:
        return []
    body = b[i:]
    step = max(1, len(body) // (n + 1))
    return [c for c in (body[step*(k+1):step*(k+1)+ln] for k in range(n)) if len(c) == ln]
docs = {"ban sach": out + "/manuscript.pdf",
        "ban danh dau": out + "/manuscript-highlighted.pdf",
        "phu luc": out + "/supplementary.pdf"}
raw = {k: open(v, "rb").read() for k, v in docs.items() if os.path.exists(v)}
if not {"ban sach", "ban danh dau"} <= set(raw):
    print("   ⛔ thieu ban PDF: %s" % sorted({"ban sach","ban danh dau"} - set(raw))); sys.exit(1)
# ⛔ 08/10: cong nay tung doi MOI tep trong paper/figures/ phai co trong THAN BAI. Sau khi
# bon tieu muc chuyen sang phu luc, fig_proactive.pdf chi con o phu luc va cong bao FAIL
# tren mot bai hoan toan dung. Nhung KHONG duoc noi long thanh "co o dau cung duoc": muc
# dich goc cua cong la bat hinh DUOC SINH ma khong ai \input (no da tung bat
# fig_denominary_drift dung the). Nen phai DINH TUYEN: moi hinh phai co mat o dung tai lieu
# \input wrapper cua no, va hinh khong wrapper nao goi thi van la loi.
def inputs(path):
    return set(re.findall(r"\\input\{(fig-[^}]*)\}",
                          re.sub(r"(?<!\\\\)%.*", "", open(path).read())))
P = root + "/paper/"
than = inputs(P + "main.tex")
phu = inputs(P + "supplementary.tex")
for f in glob.glob(P + "supp-*.tex"):
    phu |= inputs(f)
used = than | phu

# wrapper -> tep hinh nó nhung vao (wrapper TikZ khong nhung tep nao)
def tep_cua(w):
    q = P + w + ".tex"
    if not os.path.exists(q):
        return None
    m = re.search(r"\\includegraphics\[[^\]]*\]\{(?:figures/)?([^}]+)\}", open(q).read())
    return m.group(1) if m else None

tai_lieu = {}
for w in used:
    t = tep_cua(w)
    if not t:
        continue
    t = t if t.endswith(".pdf") else t + ".pdf"
    tai_lieu.setdefault(t, set())
    if w in than:
        tai_lieu[t] |= {"ban sach", "ban danh dau"}
    if w in phu:
        tai_lieu[t] |= {"phu luc"}

figs = sorted(glob.glob(os.path.join(root, "paper", "figures", "*.pdf")))
if not figs:
    print("   ⛔ khong co tep hinh nao -- khong doc thanh sach"); sys.exit(1)
bad = 0
for f in figs:
    ten = os.path.basename(f)
    can = tai_lieu.get(ten)
    if not can:
        print("   ⛔  %-26s KHONG wrapper nao \\input -- hinh sinh ra ma khong dung" % ten)
        bad += 1
        continue
    cs = chunks(f)
    if not cs:
        print("   -- %-26s khong doc duoc luong byte" % ten); continue
    hit = {k: sum(1 for c in cs if c in raw[k]) for k in sorted(can) if k in raw}
    thieu = sorted(set(can) - set(raw))
    ok = bool(hit) and all(v > 0 for v in hit.values()) and not thieu
    print("   %s %-26s %s%s" % ("ok " if ok else "⛔ ", ten,
          "  ".join("%s %d/%d" % (k, v, len(cs)) for k, v in hit.items()),
          ("  [thieu ban: " + ", ".join(thieu) + "]") if thieu else ""))
    if not ok:
        bad += 1
txt = {k: subprocess.run(["pdftotext", v, "-"], capture_output=True, text=True).stdout
       for k, v in docs.items() if os.path.exists(v)}
ph = {k: len(re.findall(r"(?i)figure pending|image not found", t)) for k, t in txt.items()}
if any(ph.values()):
    print("   ⛔ con khung cho: %s" % {k: v for k, v in ph.items() if v}); bad += 1
print("   da kiem %d hinh, dinh tuyen theo %d wrapper (%d than bai, %d phu luc) => %s"
      % (len(figs), len(used), len(than), len(phu), "FAIL" if bad else "PASS"))
sys.exit(1 if bad else 0)
PYEOF

# ⛔ TRAN COT KHONG PHAI TRAN TRANG. Hao bat duoc Bang II de len than chu cot ben canh
# trong khi pdflatex bao 0 loi 0 Overfull, check_figure_quality bao DANGEROUS 0, va g7 bao
# 0/0/0. Ba tang deu xanh vi tat ca deu do bien TRANG. `Overfull \hbox` cung im, vi LaTeX
# chi keu khi mot hop vuot \hsize cua CHINH no -- mot tabular rong hon cot khong tao ra
# hop tran. Cong nay do bien COT, suy tu chinh bai, va da duoc thu bang cach tiem lai
# dung loi do: 16 tu tren 5 trang khi tran, 0 khi da sua.
echo "== 3c/5 KHONG GI DUOC VUOT BIEN COT"
python3 "$ROOT/repo/scripts/check_column_bleed.py" --pdf "$ROOT/paper/main.pdf" \
        --tex "$ROOT/paper/main.tex" | tail -3

echo "== 4/5 thu tra loi + cover letter"
build submit response-to-reviewers
build submit cover-letter
# ⛔ Don phu pham LaTeX. `check_submit_package.py` bat dung 6 tep .aux/.log/.out o day:
#    thu muc nop khong duoc lan thu gi ngoai hien vat nop.
rm -f "$OUT"/*.aux "$OUT"/*.log "$OUT"/*.out "$OUT"/*.fls "$OUT"/*.fdb_latexmk "$OUT"/*.synctex.gz
# .DS_Store cua Finder: khong phai hien vat nop, va no tu sinh lai moi lan mo thu muc.
rm -f "$OUT"/.DS_Store

echo "== 5/5 zip nguon"
rm -f "$OUT/tnsm-resubmission-source.zip"
# ⛔ KHONG liet ke tay. Ban truoc liet ke `paper/tab-*.tex paper/fig-tau.tex` va SOT
# `claims-macros.tex`, sau tep `fig-*.tex` moi, va ca `paper/figures/`. Goi giao di
# KHONG dung lai duoc: "File claims-macros.tex not found, Emergency stop". Chi lo ra khi
# GIAI NEN RA CHO KHAC roi bat dung lai -- xem buoc 5a ngay duoi.
zip -qr "$OUT/tnsm-resubmission-source.zip" \
  paper/*.tex paper/*.bib paper/claims.json paper/claim-scope.json paper/authors paper/figures \
  repo/experiments repo/results repo/sim repo/scripts \
  repo/run_all.py repo/csv-producers.txt repo/check_artifact_claims.py repo/README.md \
  repo/kiem_bang_sinh.py repo/kiem_phu_luc.py \
  repo/environment.yml repo/RESULTS-PROVENANCE.md \
  2>/dev/null || true

# ⛔ BUOC 5a CHI THU DICH LAI BAI, KHONG THU CHAY LAI THI NGHIEM. Va vi the no bao PASS
# trong khi goi thieu `run_all.py`, `README.md`, `csv-producers.txt` va
# `check_artifact_claims.py`: du de dich ra PDF, khong du de ai do chay lai bat cu thu gi.
# Mot artifact khong chay lai duoc thi phan "reproducible" cua bai la loi noi suong.
# Kiem danh sach toi thieu ngay tai day, tren chinh tep zip vua tao.
echo "== 5b/5 GOI PHAI CHAY LAI DUOC, khong chi dich lai duoc"
python3 - "$OUT/tnsm-resubmission-source.zip" <<'PYEOF'
import sys, zipfile
NEED = ["repo/run_all.py", "repo/README.md", "repo/csv-producers.txt",
        "repo/check_artifact_claims.py", "repo/sim/traffic.py",
        "repo/experiments/make_claims.py",
        # ⛔ Hai tep nay LA cau tra loi cho Phan bien 1 y 5. Goi thieu chung thi
        #    thi nghiem ben vung khong tai lap duoc, va cong cu khong he keu.
        "repo/experiments/r7_1_imperfect_state.py",
        "repo/experiments/emit_r7_macros.py",
        "repo/results/r7_1_imperfect_state.csv",
        # ⛔ README cua hien vat HUA rang hai cong nay kiem duoc goi. Loi hua phai co
        #    tep de thuc hien, va phai duoc kiem o day.
        "repo/kiem_bang_sinh.py", "repo/kiem_phu_luc.py",
        # ⛔ Thieu hai tep nay thi goi KHONG tai lap duoc: mot la cong thuc moi truong,
        #    mot la ban khai may do va phien ban goi. Ca hai tung bi bo ngoai zip.
        "repo/environment.yml", "repo/RESULTS-PROVENANCE.md",
        "paper/claims.json", "paper/main.tex", "paper/supplementary.tex"]
names = set(zipfile.ZipFile(sys.argv[1]).namelist())
miss = [f for f in NEED if f not in names]
for f in NEED:
    print("   %s %s" % ("ok " if f in names else "⛔ ", f))
print("   %d tep trong goi, %d thieu => %s" % (len(names), len(miss), "FAIL" if miss else "PASS"))
sys.exit(1 if miss else 0)
PYEOF

echo "== 5a/5 GOI PHAI TU DUNG LAI DUOC (giai nen ra cho khac, xoa PDF, dich lai)"
TMPX=$(mktemp -d)
unzip -q "$OUT/tnsm-resubmission-source.zip" -d "$TMPX"
( cd "$TMPX/paper" 2>/dev/null && rm -f main.pdf
  for i in 1 2 3; do pdflatex -interaction=nonstopmode main.tex >x$i.log 2>&1; done ) || true
if [ -f "$TMPX/paper/main.pdf" ]; then
  PN=$(pdfinfo "$TMPX/paper/main.pdf" | awk '/^Pages/{print $2}')
  EX=$(grep -c '^! ' "$TMPX/paper/x3.log") || EX=0
  RX=$(grep -c 'Reference.*undefined' "$TMPX/paper/x3.log") || RX=0
  echo "   ban giai nen: $PN trang, $EX loi, $RX tham chieu treo"
  [ "$PN" = "$(pdfinfo "$OUT/manuscript.pdf" | awk '/^Pages/{print $2}')" ] && [ "$EX" = "0" ] \
    && echo "   => PASS" || { echo "   => FAIL goi khong dung lai giong ban goc"; }
else
  echo "   ⛔ ban giai nen KHONG dich ra PDF"
  grep -m3 '^!' "$TMPX"/paper/x1.log 2>/dev/null | sed 's/^/      /'
fi
rm -rf "$TMPX"

echo "== 6/6 THU MUC NOP DAY DU + mot zip duy nhat"
# ⛔ MOT goi duy nhat de Hao tai len cong, khong de Hao phai tu chon tep. Thu muc nay chi
#    chua hien vat NOP: khong ghi chu noi bo, khong so nhan xet, khong tep trang thai.
FULL="$OUT/TNSM-2026-12059-R1-full"
rm -rf "$FULL" "$OUT/TNSM-2026-12059-R1-full.zip"
mkdir -p "$FULL"
for f in 00-README-SUBMISSION.txt manuscript.pdf manuscript-highlighted.pdf \
         response-to-reviewers.pdf cover-letter.pdf supplementary.pdf change-list.pdf \
         tnsm-resubmission-source.zip; do
  [ -f "$OUT/$f" ] || { echo "   ⛔ THIEU $f"; exit 1; }
  cp "$OUT/$f" "$FULL/"
done
( cd "$OUT" && zip -qr TNSM-2026-12059-R1-full.zip TNSM-2026-12059-R1-full )
# Kiem tren CHINH tep zip vua tao, khong tin lenh zip
python3 - "$OUT/TNSM-2026-12059-R1-full.zip" <<'PYEOF'
import sys, zipfile
CAN = ["00-README-SUBMISSION.txt", "manuscript.pdf", "manuscript-highlighted.pdf",
       "response-to-reviewers.pdf", "cover-letter.pdf", "supplementary.pdf",
       "change-list.pdf", "tnsm-resubmission-source.zip"]
z = zipfile.ZipFile(sys.argv[1])
co = {n.split("/")[-1] for n in z.namelist() if not n.endswith("/")}
thieu = [x for x in CAN if x not in co]
la = sorted(co - set(CAN))
bad = z.testzip()
for x in CAN:
    print("   %s %s" % ("ok " if x in co else "⛔ ", x))
if la:
    print("   ⛔ tep LA trong goi: %s" % ", ".join(la))
if bad:
    print("   ⛔ tep hong trong zip: %s" % bad)
print("   => %s" % ("FAIL" if (thieu or la or bad) else "PASS: %d/%d hien vat, 0 tep la" % (len(CAN), len(CAN))))
sys.exit(1 if (thieu or la or bad) else 0)
PYEOF

echo
for f in "$OUT"/*.pdf "$OUT"/*.zip; do
  printf "  %-34s %s\n" "$(basename "$f")" \
    "$(pdfinfo "$f" 2>/dev/null | awk '/^Pages/{print $2" trang"}' || du -h "$f" | cut -f1)"
done
rm -rf "$WORK"
