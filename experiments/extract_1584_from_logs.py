"""Bóc hàng vỏ 1584 tu LOG THO thanh CSV, vi day la du lieu duy nhat cua no.

PHAN BIEN NGOAI y 2.1 lam lo ra mot chuyen no khong nhac: cac con so 1584 cua Bang VIII
(recovered 0.94, t_gnn 8.4s, speedup 29x) KHONG nam trong bat ky CSV nao. Chung chi ton tai
trong `results/p5_full_1584.log` va `results/p6_full_1584.log`, la dau ra man hinh cua mot lan
chay tren may khac (log con nguyen canh bao driver CUDA cua may do).

Hau qua: `verify_numbers` khong voi toi chung, `make_claims.py` khong tai tao duoc chung, va
mot con so headline cua bai khong co cong nao soi. Log THO la du lieu that (khong duoc chep tay
lai), nhung no phai duoc BOC thanh dang may doc duoc thi cong moi lam viec duoc.

Script nay doc log, khong sua gi, va ghi ra CSV kem cot `source_log` de truy nguoc.
"""
import csv
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")

rows = []
p5 = open(os.path.join(RES, "p5_full_1584.log"), encoding="utf-8", errors="replace").read()
for m in re.finditer(r"GCN\s+seed(\d+)\s+(\S+)\s+\|\s+recovered\s+([\d.]+)%\s+\+/-\s+([\d.]+)", p5):
    seed, split, val, sd = m.groups()
    rows.append({"quantity": "recovered_fraction", "shell": "w1584_i53" if "ood" in split else "w132_i53",
                 "split": split, "seed": int(seed), "value": round(float(val) / 100, 4),
                 "std_within_seed": round(float(sd) / 100, 4), "unit_of_analysis": "vo-x-seed",
                 "source_log": "p5_full_1584.log"})

p6 = open(os.path.join(RES, "p6_full_1584.log"), encoding="utf-8", errors="replace").read()
for m in re.finditer(r"^(\S+)\s+(\d+)\s+(\d+)\s+\|\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)x", p6, re.M):
    sh, nsat, pairs, tg, tu, sp = m.groups()
    rows.append({"quantity": "inference_time", "shell": sh, "split": "timing", "seed": -1,
                 "value": float(tg), "std_within_seed": "", "unit_of_analysis": "vo (mot lan do)",
                 "source_log": "p6_full_1584.log", "n_sat": int(nsat), "pairs": int(pairs),
                 "t_ue_s": float(tu), "speedup": float(sp)})

fields = ["quantity", "shell", "split", "seed", "value", "std_within_seed",
          "unit_of_analysis", "source_log", "n_sat", "pairs", "t_ue_s", "speedup"]
out = os.path.join(RES, "shell1584_from_logs.csv")
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
print(f"# {len(rows)} dong -> results/shell1584_from_logs.csv")
for r in rows:
    print(f"  {r['quantity']:18s} {r['shell']:12s} {r['split']:16s} seed={r['seed']:>2} "
          f"value={r['value']}" + (f" speedup={r['speedup']}x" if r.get("speedup") else ""))
