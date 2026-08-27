#!/usr/bin/env bash
# Keo ket qua tu VPS ve, sinh lai MOI hien vat, chay MOI cong, dung goi nop.
#
# ⛔ VI SAO PHAI LA MOT SCRIPT. Chuoi nay co thu tu bat buoc, va lam sai thu tu thi khong co
# gi keu len: chay `make_figs_tables` truoc `make_claims` cho ra bang lay so cu, con dung
# bai truoc khi sinh lai bang thi PDF mang so cu ma moi cong van xanh. Ca hai da xay ra.
#
#   VPS -> results/  ->  make_claims  ->  make_figs_tables  ->  make_r5_figs
#        ->  cac cong  ->  dung bai  ->  build-submit.sh
#
# Chay:  ./sync-from-vps.sh          (keo ve roi lam het)
#        ./sync-from-vps.sh --local  (bo qua buoc keo, dung ket qua dang co)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SK=${SKILL_DIR:-/Users/agentra/Documents/hao/working/paper-lab/my-skills/workflow4paper/viet-paper-chuan-dph}
FAIL=0
step() { printf "\n\033[1m== %s\033[0m\n" "$1"; }
chk()  { if [ "$2" -eq 0 ]; then printf "   ✅ %s\n" "$1"; else printf "   ⛔ %s\n" "$1"; FAIL=$((FAIL+1)); fi; }

if [ "${1:-}" != "--local" ]; then
  step "0/6 keo ket qua tu VPS (mot noi chay, mot noi doc)"
  set -a; . "$HOME/.config/paperlab-vps.env"; set +a
  # ⛔ Luu ban dang co TRUOC khi ghi de: muc tu khai cua bai phai noi duoc so cu lech bao
  # nhieu, va so sanh do chi lam duoc neu con giu ban cu. Ghi de roi moi nghi la mat han.
  rm -rf "$ROOT/code/results_prev" && cp -r "$ROOT/code/results" "$ROOT/code/results_prev"
  rsync -az -e "ssh -i $VPS_KEY -p $VPS_PORT" \
    "$VPS_USER@$VPS_HOST:/home/daipv/paperlab/qwgnn-leo-routing/results/" \
    "$ROOT/code/results/"
  chk "da keo ve $(ls "$ROOT/code/results"/*.csv | wc -l | tr -d ' ') CSV" $?
  # ⛔ MOI CSV phai mang nhan may, va phai la CUNG mot may. Bo `res_before` cu tung duoc
  # dung lam bang chung "lech giua hai may" trong khi ca hai deu la sol1.
  python3 - "$ROOT/code/results" <<'PY'
import csv, glob, os, sys
tags = {}
for p in glob.glob(os.path.join(sys.argv[1], "*.csv")):
    r = list(csv.DictReader(open(p)))
    if r:
        tags.setdefault(r[0].get("machine", "(khong co nhan)"), []).append(os.path.basename(p))
for t, f in sorted(tags.items()):
    print("   %-28s %d tep" % (t, len(f)))
if len(tags) > 1:
    print("   ⛔ KET QUA DEN TU NHIEU MAY -- bai phai lay so tu MOT may")
    sys.exit(1)
PY
  chk "moi CSV cung mot may" $?
fi

step "1/6 sinh lai claim, bang, hinh (dung thu tu)"
( cd "$ROOT/code" && python3 experiments/make_claims.py     >/dev/null ) ; chk "make_claims"      $?
( cd "$ROOT/code" && python3 experiments/make_figs_tables.py >/dev/null ) ; chk "make_figs_tables" $?
( cd "$ROOT/code" && python3 experiments/make_r5_figs.py     >/dev/null ) ; chk "make_r5_figs"     $?

step "2/6 cong RIENG cua bai nay"
python3 "$ROOT/code/scripts/check_msa_reference.py" --paper "$ROOT/paper" --code "$ROOT/code" \
  | tail -3 ; chk "tham chieu can bang dat chuan o moi vo con chia cho no" "${PIPESTATUS[0]}"
python3 "$ROOT/code/scripts/check_one_writer.py" --paper "$ROOT/paper" --code "$ROOT/code" \
  | tail -1 ; chk "moi hien vat co dung MOT bo sinh" "${PIPESTATUS[0]}"
python3 "$ROOT/code/scripts/check_no_hardcoded.py" --tex "$ROOT/paper/main.tex" \
  | tail -1 ; chk "khong bang/hinh nao go tay" "${PIPESTATUS[0]}"

step "3/6 so <-> du lieu"
( cd "$ROOT/paper" && python3 "$SK/scripts/verify_numbers.py" verify --manifest claims.json | tail -1 )
chk "133 claim khop CSV" "${PIPESTATUS[0]}"
python3 "$SK/scripts/check_paper_vs_claims.py" "$ROOT/paper/main.tex" "$ROOT/paper/claims.json" | tail -1
chk "van bai khong con gia tri cu" "${PIPESTATUS[0]}"
python3 "$ROOT/code/check_artifact_claims.py" | tail -1 ; chk "van xuoi artifact khop claim" "${PIPESTATUS[0]}"

step "4/6 dung bai"
( cd "$ROOT/paper" && rm -f main.aux && for i in 1 2 3; do
    pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1; done
  E=$(grep -c '^! ' main.log); C=$(grep -c 'khong co claim' main.log)
  P=$(pdfinfo main.pdf | awk '/^Pages/{print $2}')
  echo "   loi=$E  claim-thieu=$C  trang=$P"
  [ "$E" -eq 0 ] && [ "$C" -eq 0 ] )
chk "bai dung sach, moi \\clm{} giai duoc" $?

step "5/6 dung goi nop"
( cd "$ROOT" && ./build-submit.sh ) 2>&1 | tail -12 ; chk "build-submit.sh" "${PIPESTATUS[0]}"

step "6/6 sweep cuoi"
bash "$SK/scripts/g7_final_sweep.sh" "$ROOT/paper" "$ROOT/paper/main.tex" \
     "$ROOT/paper/claims.json" "$ROOT/code" "$ROOT/code/results" 2>&1 | tail -4

printf "\n"
if [ "$FAIL" -eq 0 ]; then printf "\033[1m✅ XONG -- 0 buoc hong\033[0m\n"; else
  printf "\033[1m⛔ %d buoc hong -- KHONG duoc dem di doc ngoai\033[0m\n" "$FAIL"; fi
exit "$FAIL"
