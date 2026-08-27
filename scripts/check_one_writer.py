"""Cong: moi tep sinh ra trong paper/ phai co DUNG MOT bo sinh ghi vao no.

    python code/scripts/check_one_writer.py --paper paper --code code

⛔ VI SAO CO FILE NAY. 27/08/2026, ba lan trong mot buoi, cung mot hong hoc:

  - `make_figs_tables.py::fig_speedup()` ghi mot khung "Figure pending" de len ban
    \\includegraphics viet tay -> Hinh 3 BIEN MAT khoi ban danh dau da gui di doc ngoai,
    va nguoi doc ngoai bao ve dung dieu do;
  - cung tep do con ghi de `fig-bound.tex` va `fig-proactive.tex`;
  - `make_claims.py` ghi de `fig-tau.tex`.

Trieu chung cua no rat dac trung va rat de doc nham: **ban sach va ban danh dau cua CUNG
mot lan nop hien hai hinh khac nhau**, tuy bo sinh nao chay sau. Khong co gi "hong" ca:
ca hai bo sinh deu chay dung, deu bao thanh cong, moi cong deu xanh. Ban dung hay sai chi
phu thuoc THU TU. Vi the khong cong nao dua tren noi dung tep bat duoc no.

Cach duy nhat bat duoc la kiem QUAN HE: dem so nguoi ghi tren mot duong dan.

CACH LAM. Chay THAT su tung bo sinh, chup van tay tep truoc va sau, va xem tep nao doi.
Khong dung phan tich tinh: ban quet regex tung bao fig-speedup.tex "van co nguoi ghi" chi
vi ten no duoc nhac trong docstring GIAI THICH rang khong con ai ghi nua, va ban quet AST
lai bo sot cac tep duoc ghi qua ham trung gian. Hai lan quet tinh cho hai ket qua khac
nhau, nen ca hai deu khong dung duoc. Chay that thi khong the noi doi.

FAIL neu: mot tep co >= 2 bo sinh ghi; hoac kiem 0 tep.
"""
import argparse
import hashlib
import os
import subprocess
import sys


def snapshot(paper):
    out = {}
    for f in sorted(os.listdir(paper)):
        if (f.startswith(("fig-", "tab-")) or f == "claims-macros.tex") and f.endswith(".tex"):
            p = os.path.join(paper, f)
            out[f] = hashlib.md5(open(p, "rb").read()).hexdigest()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    ap.add_argument("--code", required=True)
    a = ap.parse_args()
    paper = os.path.abspath(a.paper)
    code = os.path.abspath(a.code)

    gens = [f for f in sorted(os.listdir(os.path.join(code, "experiments")))
            if f.startswith("make_") and f.endswith(".py")]
    if not gens:
        print("  ⛔ khong tim thay bo sinh nao trong experiments/")
        return 1

    # ⛔ PHEP THU PHAI DUONG TINH. Ban dau tien so van tay truoc/sau moi lan chay, va no
    # bao "0 tep co nguoi ghi" tren ca 18 tep -- vi bo sinh ghi lai y HET noi dung cu nen
    # van tay khong doi. Mot cong bao PASS trong khi phat hien 0 don vi thi khong phan biet
    # duoc "dung mot nguoi ghi" voi "khong ai ghi", tuc no xanh ca tren kho rong.
    # Nen: XOA het rui do xem AI TAO LAI. Ai tao lai duoc thi nguoi do la nguoi ghi.
    # ⛔ SAO LUU TRUOC KHI CHAY BAT CU THU GI. Ban truoc chay mot luot "lam nong" tat ca
    # bo sinh ROI moi sao luu, nen khi mot bo sinh ghi bay vao paper/ thi ban sao luu da
    # dinh san loi do, va buoc khoi phuc o cuoi tra lai dung ban hong. Do la cong tu tay
    # lam hong hien vat no dang di bao ve: mot lan chay thu da xoa that fig-tau.tex.
    import shutil, tempfile
    keep = tempfile.mkdtemp(prefix="one_writer_")
    names = sorted(snapshot(paper))
    for f in names:
        shutil.copy2(os.path.join(paper, f), os.path.join(keep, f))

    # lam nong SAU khi da sao luu: dua paper/ ve trang thai on dinh de phep do sach
    for g in gens:
        subprocess.run([sys.executable, os.path.join("experiments", g)], cwd=code,
                       capture_output=True)

    writers = {}
    try:
        for g in gens:
            for f in names:
                q = os.path.join(paper, f)
                if os.path.exists(q):
                    os.remove(q)
            r = subprocess.run([sys.executable, os.path.join("experiments", g)], cwd=code,
                               capture_output=True, text=True)
            if r.returncode != 0:
                print("  ⛔ %s thoat voi ma %d khi chay tren paper/ da don sach." % (g, r.returncode))
                print("     Mot bo sinh phai tu tao duoc dau ra cua no; neu no doi tep do")
                print("     mot bo sinh KHAC de lai thi thu tu chay la mot phu thuoc an.")
                print("     %s" % (r.stderr.strip().splitlines() or ["(khong co stderr)"])[-1])
                return 1
            for f in names:
                if os.path.exists(os.path.join(paper, f)):
                    writers.setdefault(f, []).append(g)
    finally:
        for f in names:                       # tra paper/ ve dung trang thai truoc khi kiem
            shutil.copy2(os.path.join(keep, f), os.path.join(paper, f))
        shutil.rmtree(keep, ignore_errors=True)

    # ⛔ Tep KHONG doi khi chay lai van co the la tep duoc ghi (bo sinh ghi lai y het noi
    # dung cu). Nen "khong ai ghi" o day nghia la "khong ai ghi NOI DUNG KHAC", va do dung
    # la dieu ta muon: no chi ra tep viet tay, hoac tep co dung mot nguoi ghi on dinh.
    seen = {f: None for f in names}
    if not seen:
        print("  ⛔ KIEM 0 TEP trong %s -- khong duoc doc thanh sach" % paper)
        return 1

    bad = 0
    for f in sorted(seen):
        w = writers.get(f, [])
        if len(w) > 1:
            bad += 1
            print("  ⛔  %-26s <- %d bo sinh: %s" % (f, len(w), ", ".join(w)))
        else:
            print("  ok  %-26s <- %s" % (f, w[0] if w else "VIET TAY (khong bo sinh nao tao lai)"))

    print("  da kiem %d tep sinh ra, chay that %d bo sinh: %d tep bi nhieu nguoi ghi"
          % (len(seen), len(gens), bad))
    print("  => %s" % ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
