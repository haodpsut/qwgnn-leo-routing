"""Chay TOAN BO thi nghiem tren MOT may, song song, va ghi lai thoi gian tung cai.

VI SAO. Ngay 17/08/2026 cung mot script cung mot seed cho 0.1198 tren may Linux va 0.1140
tren may Mac; moi cot khac trung khit, chi cot di qua torch lech. Hai lan chay tren cung mot
may thi trung khop tung o. Bai vi the phai co MOI con so tu MOT may. File nay lam viec do
trong mot lenh, thay vi 26 lenh go tay ma khong ai nho da chay cai nao o dau.

BA DIEU DE Y KHI CHAY SONG SONG TREN MAY NHIEU NHAN

1. BLAS tu sinh luong. Tren may 80 nhan, moi tien trinh numpy mac dinh co the mo 80 luong;
   26 tien trinh nhu vay la 2080 luong tranh nhau 80 nhan, cham hon chay tuan tu. Vi vay
   moi tien trinh con bi ep OMP_NUM_THREADS=1: song song o muc TIEN TRINH, khong o muc BLAS.
2. Phu thuoc that su. Ba thi nghiem doc CSV cua cai khac, nen phai chay lam hai dot.
3. Log THO la du lieu. Moi thi nghiem giu nguyen dau ra vao logs/<ten>.log, khong chep tay,
   khong tom tat. Con so headline cua vo 1584 tung chi ton tai trong mot file log nhu vay.

Cach dung:  python3 run_all.py [--jobs N] [--only pat] [--dry]
"""
import argparse
import csv
import os
import platform
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(ROOT, "experiments")
LOGS = os.path.join(ROOT, "logs")
RES = os.path.join(ROOT, "results")

# Dot 2 doc CSV do dot 1 sinh ra, nen khong duoc tron hai dot.
WAVE2 = {"r2_7_budget_matched.py": "p6_baselines.csv",
         "r2_7_warmstart_ecmp.py": "p6_baselines.csv",
         "r3_2_feasibility.py": "p4_headroom.csv"}
SKIP = {"make_claims.py", "run_all.py", "extract_1584_from_logs.py"}

# Thi nghiem DO THOI GIAN phai chay MOT MINH. Lan dau toi cho no chay cung 25 tien trinh
# khac, va no do wall-clock duoi tranh chap CPU: 17.85s o vo 1584 thay vi 8.75s khi chay
# rieng, tuc gap doi. Con so ay khong noi gi ve chi phi cua phuong phap, no noi ve viec toi
# dang chay bao nhieu thu khac cung luc. Dung lop loi ma bai nay ton ca ngay de vach ra.
EXCLUSIVE = {"r4_4_stage_timing.py", "p6_baselines.py"}


def experiments():
    all_py = sorted(f for f in os.listdir(EXP) if f.endswith(".py") and f not in SKIP)
    w1 = [f for f in all_py if f not in WAVE2 and f not in EXCLUSIVE]
    w2 = [f for f in all_py if f in WAVE2]
    ex = [f for f in all_py if f in EXCLUSIVE]
    return w1, w2, ex


def run_one(script):
    env = dict(os.environ)
    # Ep mot luong moi tien trinh. Xem ghi chu 1 o dau file.
    env.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
    log = os.path.join(LOGS, script.replace(".py", ".log"))
    t0 = time.time()
    with open(log, "w") as fh:
        p = subprocess.run([sys.executable, "-u", script], cwd=EXP, env=env,
                           stdout=fh, stderr=subprocess.STDOUT)
    dt = time.time() - t0
    status = "OK" if p.returncode == 0 else f"LOI({p.returncode})"
    print(f"  {status:9s} {dt:8.1f}s  {script}", flush=True)
    return {"script": script, "seconds": round(dt, 1), "returncode": p.returncode,
            "log": os.path.relpath(log, ROOT)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=0, help="0 = so nhan - 2")
    ap.add_argument("--only", default="", help="chi chay script khop chuoi nay")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(RES, exist_ok=True)
    ncpu = os.cpu_count() or 4
    jobs = a.jobs or max(1, ncpu - 2)
    w1, w2, ex = experiments()
    if a.only:
        w1 = [s for s in w1 if a.only in s]
        w2 = [s for s in w2 if a.only in s]

    tag = f"{platform.system()}-{platform.machine()}-{socket.gethostname()}"
    print(f"MAY: {tag} | {ncpu} nhan | chay toi da {jobs} tien trinh song song")
    print(f"dot 1: {len(w1)} thi nghiem doc lap")
    print(f"dot 2: {len(w2)} thi nghiem phu thuoc ({', '.join(WAVE2)})")
    print(f"dot 3: {len(ex)} thi nghiem chay MOT MINH ({', '.join(EXCLUSIVE)})\n")
    if a.dry:
        for s in w1 + w2 + ex:
            print("  ", s)
        return 0

    t0 = time.time()
    rows = []
    # Dot 3 chay MOT MINH (par=1): do thoi gian ma co tien trinh khac tranh CPU thi con so
    # do duoc noi ve tai may, khong noi ve phuong phap.
    for wave, scripts, par in (("1", w1, jobs), ("2", w2, jobs), ("3 (mot minh)", ex, 1)):
        if not scripts:
            continue
        print(f"--- dot {wave} ---", flush=True)
        with ThreadPoolExecutor(max_workers=par) as pool:
            rows += list(pool.map(run_one, scripts))

    wall = time.time() - t0

    # Ghi bang thoi gian thanh CSV, de "chay het mat bao lau" cung la mot con so tra nguoc
    # duoc chu khong phai mot cau noi mieng.
    out = os.path.join(RES, "run_all_timing.csv")
    for r in rows:
        r["machine"] = tag
        r["n_cpu"] = ncpu
        r["parallel_jobs"] = jobs
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    bad = [r for r in rows if r["returncode"] != 0]
    ser = sum(r["seconds"] for r in rows)
    print(f"\n=== TONG KET ===")
    print(f"  {len(rows)} thi nghiem | that bai: {len(bad)}")
    print(f"  tong thoi gian CPU (neu chay tuan tu): {ser/60:.1f} phut")
    print(f"  thoi gian THUC (song song {jobs}):     {wall/60:.1f} phut")
    print(f"  he so tang toc: {ser/wall:.1f}x")
    print(f"  bang thoi gian -> results/run_all_timing.csv")
    if bad:
        print("\n  THAT BAI, xem log:")
        for r in bad:
            print(f"    {r['script']:34s} {r['log']}")
    print("\n  5 thi nghiem lau nhat:")
    for r in sorted(rows, key=lambda x: -x["seconds"])[:5]:
        print(f"    {r['seconds']:8.1f}s  {r['script']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
