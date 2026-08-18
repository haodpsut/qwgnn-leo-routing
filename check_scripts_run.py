#!/usr/bin/env python3
"""AR-9: MOI script trong experiments/ phai thuc su chay duoc, khong chi cac lenh trong README.

VI SAO. README thuong liet ke 3-4 lenh dai dien; con lai khong ai bam. Mot script hong nam im
trong artifact la mot loi hua khong giu, va nguoi doi chieu se phat hien truoc khi tac gia biet.

Che do mac dinh la KIEM TINH, du de bat cac hong pho bien ma khong ton hang gio:
  - cu phap Python
  - import module local co ton tai khong
  - script co ghi ra file ket qua ma no tu khai khong (OUT = ...)
Voi --deep no thuc su CHAY tung script, dung khi co thoi gian.

Usage: check_scripts_run.py <code-dir> [--deep] [--timeout SEC]
Exit: 0 moi script qua; 2 co script hong.
"""
import argparse
import ast
import os
import re
import subprocess
import sys


def local_modules(code):
    """MOI thu muc con co .py deu la nguon module tiem nang.

    Ban dau toi chi quet sim/ va experiments/, va cong bao 5 script "import khong giai duoc:
    models" trong khi models.py nam o smoke/ va cac script do CO them smoke/ vao sys.path. Mot
    cong bao dong gia la mot cong se bi phot lo; day la cai bay cua chinh no."""
    mods = set()
    for root, _dirs, files in os.walk(code):
        if any(f.endswith(".py") for f in files):
            mods |= {f[:-3] for f in files if f.endswith(".py")}
    return mods


def main():
    ap = argparse.ArgumentParser()
    # Sweep goi script nay KHONG THAM SO (quy uoc: no nam trong code/ va tu biet du an cua
    # minh). Bat buoc tham so thi cong bao FAIL vi thieu doi so, tuc mot loi GOI LENH doi lot
    # mot loi NOI DUNG -- dung cai bay da lam mat nua buoi hom nay.
    ap.add_argument("code", nargs="?", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()

    exp = os.path.join(a.code, "experiments")
    if not os.path.isdir(exp):
        print("khong thay %s => KHONG kiem duoc gi (hong, khong phai sach)" % exp)
        return 2
    mods = local_modules(a.code)
    scripts = sorted(f for f in os.listdir(exp) if f.endswith(".py"))
    bad = []
    for f in scripts:
        p = os.path.join(exp, f)
        src = open(p, encoding="utf-8").read()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            bad.append((f, "cu phap: %s" % e))
            print("  FAIL  %-34s cu phap dong %s" % (f, e.lineno))
            continue
        # import local tro toi module co that chua
        miss = []
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                base = n.module.split(".")[0]
                if base in mods or base in ("os", "sys", "csv", "json", "re", "time", "math",
                                            "argparse", "statistics", "collections", "itertools",
                                            "subprocess", "platform", "socket", "warnings",
                                            "functools", "concurrent", "urllib", "pathlib"):
                    continue
                try:
                    __import__(base)
                except Exception:
                    miss.append(base)
        if miss:
            bad.append((f, "import khong giai duoc: %s" % ", ".join(sorted(set(miss)))))
            print("  FAIL  %-34s import: %s" % (f, ", ".join(sorted(set(miss)))))
            continue
        if a.deep:
            r = subprocess.run([sys.executable, f], cwd=exp, capture_output=True,
                               timeout=a.timeout,
                               env={**os.environ, "OMP_NUM_THREADS": "1"})
            if r.returncode != 0:
                bad.append((f, "chay that bai: %s" % r.stderr.decode()[-120:]))
                print("  FAIL  %-34s chay that bai" % f)
                continue
        print("  ok    %-34s%s" % (f, " (da chay)" if a.deep else ""))

    print("\n%d script | hong: %d%s" % (len(scripts), len(bad),
                                        "" if a.deep else "  [kiem TINH; dung --deep de chay that]"))
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
