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
cd "$(dirname "$0")"
ROOT=$PWD
SK=${SKILL_DIR:-/Users/agentra/Documents/hao/working/paper-lab/my-skills/workflow4paper/viet-paper-chuan-dph}
S=$SK/scripts

line() { printf '\n\033[1m%s\033[0m\n' "$1"; }

line "A. So <-> du lieu"
( cd paper && python3 "$S/verify_numbers.py" verify --manifest claims.json | tail -2 )
python3 "$S/check_claim_scope.py" "$ROOT/paper" "$ROOT/code/results" | tail -2
python3 "$S/check_cross_table.py" "$ROOT/paper/claims.json" --auto | grep "Tong ket"

line "B. So trong BAI <-> claim  (cong nay tra loi cau ma hai cong tren khong hoi)"
python3 "$S/check_paper_vs_claims.py" paper/main.tex paper/claims.json | tail -3

line "C. CSV <-> code sinh ra CSV"
# ${=VAR} la BAT BUOC o zsh: khong co dau '=' thi ca chuoi vao lam MOT tham so va cong
# bao "30 khong anh xa" trong khi ban do hoan toan dung.
MAPS=$(grep -E "^[a-z0-9_]+\.csv = " code/csv-producers.txt | sed 's/ = /=/' | tr '\n' ' ')
if [ -n "${ZSH_VERSION:-}" ]; then
  python3 "$S/check_staleness.py" --code code/experiments --results code/results --map ${=MAPS} | tail -2
else
  python3 "$S/check_staleness.py" --code code/experiments --results code/results --map $MAPS | tail -2
fi

line "D. Tham khao"
( cd paper && python3 "$S/verify_refs.py" main.tex | tail -2 )

line "E. Sweep cuoi (tuyet doi hoa MOI duong dan)"
bash "$S/g7_final_sweep.sh" "$ROOT/paper" "$ROOT/paper/main.tex" "$ROOT/paper/claims.json" \
     "$ROOT/code" "$ROOT/code/results" "https://github.com/haodpsut/qwgnn-leo-routing" \
  | grep -E "FAIL|SKIP|DANGEROUS=|REVISABLE="
