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
    return t.replace("\\begin{document}", SHIM + "\\begin{document}", 1)
for src, dst in ((os.path.join(root, "v1-rejected/main.tex"), "old.tex"),
                 (os.path.join(root, "paper/main.tex"), "new.tex")):
    io.open(os.path.join(work, dst), "w", encoding="utf-8").write(flatten(src))
PY
latexdiff --type=UNDERLINE --exclude-textcmd="section,subsection" \
  "$WORK/old.tex" "$WORK/new.tex" > "$WORK/diff.tex" 2>/dev/null
# Chi doi MAU, khong gach chan cung khong gach ngang: gach chan doi font nen trang danh dau
# doc khong cung co voi ban cuoi, va Hao da bat dung loi do mot lan.
python3 - "$WORK/diff.tex" <<'PY'
import re, sys, io
p = sys.argv[1]; t = io.open(p, encoding="utf-8").read()
t = re.sub(r"\\providecommand\{\\DIFadd\}\[1\]\{[^\n]*\}",
           r"\\providecommand{\\DIFadd}[1]{{\\protect\\color[rgb]{0,0,0.75}#1}}", t)
t = re.sub(r"\\providecommand\{\\DIFdel\}\[1\]\{[^\n]*\}",
           r"\\providecommand{\\DIFdel}[1]{{\\protect\\color[rgb]{0.7,0,0}#1}}", t)
t = t.replace("\\usepackage[normalem]{ulem}", "")     # bo hoan toan gach chan/gach ngang
head = (r"\noindent\textcolor[rgb]{0,0,0.75}{\textbf{Blue}}: text that is new in this manuscript. "
        r"\textcolor[rgb]{0.7,0,0}{\textbf{Red}}: text carried over from the previous submission "
        r"and removed, shown only where the two versions could be aligned. Because this manuscript "
        r"was rewritten rather than edited, most removed material could not be aligned and does "
        r"not appear here; the response letter lists what was removed and why. Unmarked text is "
        r"unchanged.\par\bigskip" "\n")
t = t.replace("\\maketitle", "\\maketitle\n" + head, 1)
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
if pct < 90:
    print(f"   ! chu thich ban danh dau PHAI noi ro phan xoa la KHONG day du ({pct:.0f}%)")
PY

echo "== 4/5 thu tra loi + cover letter"
build submit response-to-reviewers
build submit cover-letter

echo "== 5/5 zip nguon"
rm -f "$OUT/tnsm-resubmission-source.zip"
zip -qr "$OUT/tnsm-resubmission-source.zip" \
  paper/main.tex paper/*.bib paper/tab-*.tex paper/fig-tau.tex paper/claims.json \
  paper/authors code/experiments code/results README.md 2>/dev/null || true

echo
for f in "$OUT"/*.pdf "$OUT"/*.zip; do
  printf "  %-34s %s\n" "$(basename "$f")" \
    "$(pdfinfo "$f" 2>/dev/null | awk '/^Pages/{print $2" trang"}' || du -h "$f" | cut -f1)"
done
rm -rf "$WORK"
