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
( cd code/experiments && python3 make_claims.py >/dev/null )

echo "== 2/5 ban thao sach"
build paper main
cp paper/main.pdf "$OUT/manuscript.pdf"

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
for src, dst in ((os.path.join(root, "v1-rejected/main.tex"), "old.tex"),
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
old = flat(subprocess.run(["pdftotext", root+"/v1-rejected/main.pdf","-"],
                          capture_output=True, text=True).stdout)
new = flat(subprocess.run(["pdftotext", root+"/paper/main.pdf","-"],
                          capture_output=True, text=True).stdout)
dif = flat(io.open(work+"/diff.tex", encoding="utf-8").read())
gone = [flat(s).strip()[:60] for s in re.split(r"(?<=[.])\s", old)
        if len(flat(s).strip()) >= 80 and flat(s).strip()[:60] not in new]
shown = [c for c in gone if c in dif]
pct = 100*len(shown)/max(1, len(gone))
print(f"   cau cu bi bo: {len(gone)} | hien trong ban danh dau: {len(shown)} ({pct:.0f}%)")
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
docs = {"ban sach": out + "/manuscript.pdf", "ban danh dau": out + "/manuscript-highlighted.pdf"}
raw = {k: open(v, "rb").read() for k, v in docs.items() if os.path.exists(v)}
if len(raw) < 2:
    print("   ⛔ thieu mot trong hai ban PDF: %s" % sorted(set(docs) - set(raw))); sys.exit(1)
used = set(re.findall(r"\\input\{(fig-[^}]*)\}", open(root + "/paper/main.tex").read()))
figs = sorted(glob.glob(os.path.join(root, "paper", "figures", "*.pdf")))
if not figs:
    print("   ⛔ khong co tep hinh nao -- khong doc thanh sach"); sys.exit(1)
bad = 0
for f in figs:
    cs = chunks(f)
    if not cs:
        print("   -- %-26s khong doc duoc luong byte" % os.path.basename(f)); continue
    hit = {k: sum(1 for c in cs if c in d) for k, d in raw.items()}
    ok = all(v > 0 for v in hit.values())
    print("   %s %-26s %s" % ("ok " if ok else "⛔ ", os.path.basename(f),
          "  ".join("%s %d/%d" % (k, v, len(cs)) for k, v in sorted(hit.items()))))
    if not ok:
        bad += 1
txt = {k: subprocess.run(["pdftotext", v, "-"], capture_output=True, text=True).stdout
       for k, v in docs.items()}
ph = {k: len(re.findall(r"(?i)figure pending|image not found", t)) for k, t in txt.items()}
if any(ph.values()):
    print("   ⛔ con khung cho: %s" % ph); bad += 1
print("   da kiem %d hinh tren 2 ban PDF (%d wrapper duoc \input) => %s"
      % (len(figs), len(used), "FAIL" if bad else "PASS"))
sys.exit(1 if bad else 0)
PYEOF

# ⛔ TRAN COT KHONG PHAI TRAN TRANG. Hao bat duoc Bang II de len than chu cot ben canh
# trong khi pdflatex bao 0 loi 0 Overfull, check_figure_quality bao DANGEROUS 0, va g7 bao
# 0/0/0. Ba tang deu xanh vi tat ca deu do bien TRANG. `Overfull \hbox` cung im, vi LaTeX
# chi keu khi mot hop vuot \hsize cua CHINH no -- mot tabular rong hon cot khong tao ra
# hop tran. Cong nay do bien COT, suy tu chinh bai, va da duoc thu bang cach tiem lai
# dung loi do: 16 tu tren 5 trang khi tran, 0 khi da sua.
echo "== 3c/5 KHONG GI DUOC VUOT BIEN COT"
python3 "$ROOT/code/scripts/check_column_bleed.py" --pdf "$ROOT/paper/main.pdf" \
        --tex "$ROOT/paper/main.tex" | tail -3

echo "== 4/5 thu tra loi + cover letter"
build submit response-to-reviewers
build submit cover-letter

echo "== 5/5 zip nguon"
rm -f "$OUT/tnsm-resubmission-source.zip"
# ⛔ KHONG liet ke tay. Ban truoc liet ke `paper/tab-*.tex paper/fig-tau.tex` va SOT
# `claims-macros.tex`, sau tep `fig-*.tex` moi, va ca `paper/figures/`. Goi giao di
# KHONG dung lai duoc: "File claims-macros.tex not found, Emergency stop". Chi lo ra khi
# GIAI NEN RA CHO KHAC roi bat dung lai -- xem buoc 5a ngay duoi.
zip -qr "$OUT/tnsm-resubmission-source.zip" \
  paper/*.tex paper/*.bib paper/claims.json paper/authors paper/figures \
  code/experiments code/results code/sim code/scripts README.md 2>/dev/null || true

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

echo
for f in "$OUT"/*.pdf "$OUT"/*.zip; do
  printf "  %-34s %s\n" "$(basename "$f")" \
    "$(pdfinfo "$f" 2>/dev/null | awk '/^Pages/{print $2" trang"}' || du -h "$f" | cut -f1)"
done
rm -rf "$WORK"
