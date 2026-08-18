#!/usr/bin/env bash
# Chay thi nghiem cua BAT KY bai nao tren VPS, khong phai tren may nay.
#
# VI SAO CO FILE NAY. Ngay 17/08/2026, cung mot script cung mot seed cho hai ket qua khac
# nhau tren hai may: r_gnn ngoai phan phoi la 0.1198 tren may Linux va 0.1140 tren Mac. Moi
# cot khac trung khit; chi cot di qua torch lech. Hai lan chay tren CUNG may thi trung khop
# tung o. Ket luan la mot luat ap cho MOI bai, khong rieng bai TNSM:
#
#     MOI con so vao mot bai phai den tu MOT may.
#
# Va GPU thuong khong lien quan. Voi bai TNSM, forward cua mo hinh chiem 0.05% thoi gian o
# vo 1584; 99.95% con lai la Dijkstra tren CPU. VPS duoc dung vi NHAN CPU de chay song song,
# khong phai vi card. Truoc khi thue hay bat GPU cho mot bai moi, hay do ty le nay truoc.
#
# CAU HINH: ~/.config/paperlab-vps.env  (nam NGOAI moi git repo, chmod 600)
# Chon bai bang bien PROJECT hoac tham so --project.
#
#   ./vps-run.sh check
#   ./vps-run.sh setup
#   PROJECT=tnsm-route-under-load ./vps-run.sh run r4_1_shell1584_controls.py
#   PROJECT=tnsm-route-under-load ./vps-run.sh par a.py b.py c.py
#   ./vps-run.sh push
#   ./vps-run.sh pull
set -euo pipefail
CFG=${PAPERLAB_VPS_CFG:-$HOME/.config/paperlab-vps.env}
[ -f "$CFG" ] || { echo "Thieu $CFG. Copy tu ${CFG}.template roi dien."; exit 1; }
# shellcheck disable=SC1090
set -a; . "$CFG"; set +a
: "${VPS_HOST:?chua dien VPS_HOST}" "${VPS_USER:?chua dien VPS_USER}"
VPS_PORT=${VPS_PORT:-22}
VPS_ENV=${VPS_ENV:-paperlab}
WORK=${VPS_WORKDIR:-\$HOME/paperlab}

# --- chon bai ---
PROJECT=${PROJECT:-}
if [ "${1:-}" = "--project" ]; then PROJECT=$2; shift 2; fi
REPO_VAR="REPO_${PROJECT//-/_}"
GIT_REPO=${!REPO_VAR:-${GIT_REPO:-}}
SUBDIR=${SUBDIR:-code}          # thu muc chua experiments/ va results/ trong repo

# LOC BI MAT truoc khi in bat cu thu gi. Mot lenh `git remote -v` da lam lo token mot lan.
scrub() { sed -e "s|//[^@]*@|//|g" \
              -e "s|${GIT_TOKEN:-__none__}|<TOKEN>|g" \
              -e "s|${VPS_PASS:-__none__}|<PASS>|g"; }

sshx() {
  if [ -n "${VPS_KEY:-}" ]; then
    ssh -i "$VPS_KEY" -p "$VPS_PORT" -o StrictHostKeyChecking=accept-new "$VPS_USER@$VPS_HOST" "$@"
  elif [ -n "${VPS_PASS:-}" ]; then
    command -v sshpass >/dev/null || { echo "can sshpass, hoac dung VPS_KEY"; exit 1; }
    sshpass -p "$VPS_PASS" ssh -p "$VPS_PORT" -o StrictHostKeyChecking=accept-new \
        "$VPS_USER@$VPS_HOST" "$@"
  else echo "chua dien VPS_KEY hoac VPS_PASS"; exit 1; fi
}

name_of() { basename "${1%.git}"; }
PROJ_DIR="$WORK/$(name_of "${GIT_REPO:-repo}")"

remote() {
  sshx "bash -lc '
    CONDA_SH=\"${VPS_CONDA:-}\"
    [ -n \"\$CONDA_SH\" ] || CONDA_SH=\$(ls -d \$HOME/miniconda3/etc/profile.d/conda.sh \
       \$HOME/anaconda3/etc/profile.d/conda.sh \$HOME/.conda/etc/profile.d/conda.sh \
       /opt/conda/etc/profile.d/conda.sh 2>/dev/null | head -1)
    [ -n \"\$CONDA_SH\" ] && . \"\$CONDA_SH\"
    conda activate $VPS_ENV 2>/dev/null || true
    cd $PROJ_DIR/$SUBDIR 2>/dev/null || cd $PROJ_DIR 2>/dev/null || true
    $1
  '" 2>&1 | scrub
}

case "${1:-}" in
check)
  echo "=== MAY ==="
  remote 'nproc; free -h | head -2; df -h "$HOME" | tail -1; lscpu | grep -E "^Model name" || true'
  echo "=== MOI TRUONG ==="
  remote 'which python3 || echo "chua co python trong env"
    python3 -c "import numpy,networkx,torch;print(\"numpy\",numpy.__version__,\"networkx\",networkx.__version__,\"torch\",torch.__version__)" 2>&1 | tail -1'
  echo "=== CAC REPO DA CLONE ==="
  remote 'ls -d '"$WORK"'/*/ 2>/dev/null || echo "chua co gi trong '"$WORK"'"'
  echo "=== LOG GOC KHONG TAI TAO DUOC (dung ghi de) ==="
  remote 'find $HOME -maxdepth 6 -name "*_full_*.log" -o -maxdepth 6 -name "*RUN-LOG*" 2>/dev/null | head'
  echo "=== GPU (thuong la khong can, do truoc khi tin) ==="
  remote 'nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "khong co nvidia-smi"'
  ;;
setup)
  [ -n "$GIT_REPO" ] || { echo "chua biet repo: dat PROJECT=<ten> va REPO_<ten> trong $CFG"; exit 1; }
  remote 'set -e
    mkdir -p '"$WORK"' && cd '"$WORK"'
    conda env list | grep -q "^'"$VPS_ENV"' " || \
      conda create -y -n '"$VPS_ENV"' python=3.11 numpy scipy networkx pandas matplotlib
    conda activate '"$VPS_ENV"'
    python3 -c "import torch" 2>/dev/null || pip install -q torch --index-url https://download.pytorch.org/whl/cpu
    [ -d '"$(name_of "$GIT_REPO")"'/.git ] || git clone -q https://'"${GIT_TOKEN:+$GIT_TOKEN@}$GIT_REPO"'.git
    cd '"$(name_of "$GIT_REPO")"' && git pull -q --ff-only || true
    python3 -c "import numpy,networkx,torch;print(\"OK\",numpy.__version__,networkx.__version__,torch.__version__)"'
  ;;
run)
  [ $# -ge 2 ] || { echo "vd: PROJECT=... ./vps-run.sh run r4_1.py"; exit 1; }
  remote 'cd experiments && python3 -u '"$2"' 2>&1 | tail -40'
  ;;
par)
  shift; [ $# -ge 1 ] || { echo "vd: ./vps-run.sh par a.py b.py"; exit 1; }
  # Song song theo SCRIPT: cac thi nghiem doc lap va deu don luong, nen day la cach duy nhat
  # nhieu nhan CPU giup duoc gi.
  remote 'cd experiments
    for s in '"$*"'; do (nohup python3 -u "$s" > "/tmp/${s%.py}.log" 2>&1 &) ; done
    sleep 2; echo "da khoi dong: '"$*"'"'
  ;;
tail) remote 'tail -40 /tmp/'"${2:-}"'' ;;
ps)   remote 'ps -eo pid,etime,pcpu,comm,args --sort=-pcpu | grep "[p]ython3" | head' ;;
push)
  remote 'git config user.name haodpsut; git config user.email haodp.sut@gmail.com
    # Gan nhan MAY vao moi CSV. Lech giua may la co that, va no phai lo ra ngay trong du lieu
    # chu khong phai sau mot buoi truy nguoc.
    python3 - <<PY
import csv, glob, platform, socket
tag = f"{platform.system()}-{platform.machine()}-{socket.gethostname()}"
for f in glob.glob("results/*.csv"):
    rows = list(csv.DictReader(open(f)))
    if not rows or "machine" in rows[0]: continue
    for r in rows: r["machine"] = tag
    with open(f, "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("da gan nhan may:", tag)
PY
    git add -A results experiments && git diff --cached --quiet && echo "khong co gi moi" || \
    { git commit -q -m "results: chay tren VPS ($(nproc) nhan)"; git push -q origin HEAD && echo "da push"; }'
  ;;
pull)
  : "${LOCAL_CLONE:?dat LOCAL_CLONE trong $CFG, vd /private/tmp/qwgnn}"
  git -C "$LOCAL_CLONE" pull --ff-only 2>&1 | scrub
  echo "da keo ve $LOCAL_CLONE. Copy results/ vao thu muc bai roi chay make_claims."
  ;;
*) sed -n '2,25p' "$0"; exit 1;;
esac
