#!/usr/bin/env bash
# Chay MOI cong cua pipeline tren bai nay, voi dung tham so.
#
# VI SAO CO FILE NAY. Ba lan trong mot ngay mot cong bao FAIL chi vi goi sai:
#   - verify_numbers chay tu thu muc sai  -> bao 61/61 SAI thay vi "khong tim thay file"
#   - g7_final_sweep goi bang duong dan tuong doi -> DANGEROUS=9 thay vi 2
#   - check_staleness voi $MAPS khong ngoac -> zsh khong tach chuoi, 30 "khong anh xa"
# Cong keu to vi loi GOI LENH cung nguy hiem nhu cong im lang: bao dong gia che mat loi that,
# va nguoi doc quen dan.
set -uo pipefail
# ⛔ 08/10: bon cong nay tung tro vao `code/` -- cay lam viec 27/08 DA CHET. CSV hai
# cay trung khit 38/38 nen so khong sai, nhung bo sinh lech 53 dong va CA HAI script
# cua thi nghiem ben vung moi (r7_1) nam NGOAI tam check_staleness. Cay song la `repo/`.
cd "$(dirname "$0")"
ROOT=$PWD
SK=${SKILL_DIR:-/Users/agentra/Documents/hao/working/viet-paper-chuan-dph}
S=$SK/scripts

# ⛔ 08/10: duong dan mac dinh cu tro vao paper-lab/my-skills/workflow4paper/... KHONG TON TAI.
# Hau qua: BAY cong A-E in "No such file or directory" roi script ket thuc binh thuong, nen ca
# bo cong la mot phep KHONG KIEM GI trong khi trong nhu da chay. Vi vay phai CHAN ngay tu dau.
thieu=0
for f in verify_numbers.py check_claim_scope.py check_cross_table.py check_paper_vs_claims.py \
         check_staleness.py verify_refs.py g7_final_sweep.sh; do
  [ -f "$S/$f" ] || { echo "⛔ thieu $S/$f"; thieu=$((thieu+1)); }
done
if [ "$thieu" -gt 0 ]; then
  echo "⛔ DUNG: $thieu script cong khong ton tai. Dat SKILL_DIR cho dung, dung chay tiep:"
  echo "   mot bo cong khong tim thay script se in ra toan dong trong va trong nhu DAT."
  exit 2
fi

line() { printf '\n\033[1m%s\033[0m\n' "$1"; }

line "A. So <-> du lieu"
( cd paper && python3 "$S/verify_numbers.py" verify --manifest claims.json | tail -2 )
python3 "$S/check_claim_scope.py" "$ROOT/paper" "$ROOT/repo/results" | tail -2
python3 "$S/check_cross_table.py" "$ROOT/paper/claims.json" --auto | grep "Tong ket"

line "B. So trong BAI <-> claim  (cong nay tra loi cau ma hai cong tren khong hoi)"
python3 "$S/check_paper_vs_claims.py" paper/main.tex paper/claims.json | tail -3

# THU GUI BIEN TAP cung la be mat tuyen bo. 18/08: bai da cap nhat sang so VPS, con cover
# letter va thu tra loi van in 79.1/30.9/0.317 cua may cu, va khong cong nao doc chung.
line "B2. So trong HAI LA THU <-> claim"
python3 - <<'PYEOF'
import json, re, io
C = {c["paper_value"].lstrip("+") for c in json.load(open("paper/claims.json"))}
SKIP = {"0.7", "0.75", "1.15", "2601.21921", "0.2", "1.4"}   # mau, le, arXiv id, tau, itemsep
bad = 0
for f in ("submit/cover-letter.tex", "submit/response-to-reviewers.tex"):
    t = io.open(f, encoding="utf-8").read()
    # ⛔ BO van trich nguyen van cua phan bien (\rc{...}) va ghi chu LaTeX truoc khi doi chieu.
    #    Con so trong cau cua PHAN BIEN la cua HO: thu buoc phai trich dung nguyen van, ke ca
    #    khi so do khong phai claim nao cua ta (vd ho viet "0.93, 0.94, 0.88 appear in different
    #    tables"). Cong doi nhung so TA TU KHAI, va chi the. Bo \rc{} bang cach dem ngoac.
    t = re.sub(r"(?<!\\)%.*", "", t)
    out, i = [], 0
    while i < len(t):
        j = t.find("\\rc{", i)
        if j < 0:
            out.append(t[i:]); break
        out.append(t[i:j])
        k, d = j + 4, 1
        while k < len(t) and d:
            d += (t[k] == "{") - (t[k] == "}")
            k += 1
        i = k
    t = "".join(out)
    # Va bo van nam trong dau trich LaTeX ``...'': dan lai mot caption cu de GIAI THICH
    # cho sua (vd ``5.0'' doi thanh ``5'') la DAN, khong phai KHAI. Con so ta tu khai van bi doi.
    t = re.sub(r"``.*?''", " ", t, flags=re.S)
    nums = {m.group(1) for m in re.finditer(r"(?<![\w.])(\d+\.\d+)", t)}
    miss = sorted(nums - C - SKIP, key=float)
    bad += len(miss)
    print("  %-28s khong khop claim: %s" % (f.split("/")[-1], miss or "khong"))
print("  => %s" % ("PASS" if not bad else "FAIL: thu dang in so khong con la claim nao"))
PYEOF

line "C. CSV <-> code sinh ra CSV"
# ${=VAR} la BAT BUOC o zsh: khong co dau '=' thi ca chuoi vao lam MOT tham so va cong
# bao "30 khong anh xa" trong khi ban do hoan toan dung.
MAPS=$(grep -E "^[a-z0-9_]+\.csv = " repo/csv-producers.txt | sed 's/ = /=/' | tr '\n' ' ')
if [ -n "${ZSH_VERSION:-}" ]; then
  python3 "$S/check_staleness.py" --code repo/experiments --results repo/results --map ${=MAPS} | tail -2
else
  python3 "$S/check_staleness.py" --code repo/experiments --results repo/results --map $MAPS | tail -2
fi

line "D. Tham khao"
( cd paper && python3 "$S/verify_refs.py" main.tex | tail -2 )

line "D2. TRUY SO VE CSV, goi TU GOC DU AN"
# ⛔ `trace_prose_numbers.py` can mot thu muc `paper/` TUONG DOI voi cwd. g7_final_sweep.sh
# doi thu muc truoc khi goi no, nen trong sweep no bao "THIEU DAU VAO / khong thay: paper"
# va res() doc thanh FAIL DANGEROUS -- tren mot bai ma phep kiem that su DAT (0 so khong
# truy duoc, 0 bang khong claim nao cham). Day dung lop loi ma dau tep nay canh bao: cong
# keu to vi loi GOI LENH che mat cong keu vi loi THAT. Nen goi lai o day, tu goc du an.
python3 "$S/trace_prose_numbers.py" paper/main.tex repo/results paper/claims.json \
  | grep -E "KHONG truy duoc ve CSV|KHONG claim nao cham toi|KHONG doi chieu duoc"

line "E. Sweep cuoi (tuyet doi hoa MOI duong dan)"
bash "$S/g7_final_sweep.sh" "$ROOT/paper" "$ROOT/paper/main.tex" "$ROOT/paper/claims.json" \
     "$ROOT/repo" "$ROOT/repo/results" "https://github.com/haodpsut/qwgnn-leo-routing" \
  | grep -E "FAIL|SKIP|DANGEROUS=|REVISABLE="
