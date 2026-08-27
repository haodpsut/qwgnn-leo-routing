"""Cong: moi vo ma bai CHIA CHO can bang phai dat PoA >= 1 tai san so vong dang dung.

    python code/scripts/check_msa_reference.py --tex paper/main.tex

⛔ VI SAO CO FILE NAY. 27/08/2026, nguoi doc ngoai lan hai bat mot loi khong cong nao trong
14 cong cua bai nhin thay: vo 264 lay tham chieu can bang giai o T=20, va tai T=20 no cho

    PoA = TTT_UE / TTT_SO = 0.9976 < 1

Day la dieu KHONG THE XAY RA: can bang nguoi dung (UE) khong the tot hon toi uu he thong
(SO). Nen con so 0.9976 khong phai "gan 1", no la bang chung rang loi giai CHUA phai can
bang. Vay ma moi dai luong cua vo 264 trong bai deu chia cho no.

Vi sao 14 cong deu xanh: `traffic.py` khai HAI tieu chi dung trong chu thich

    (1) PoA >= 1                      -- rang buoc vat ly
    (2) |dUE| < 0.5% giua hai lan kiem -- da on dinh

nhung than ham chi cai dat (2). O vo 264, (2) dat ngay tu 20 vong, nen ham dung som va bao
"da hoi tu". Mot tieu chi duoc VIET ra ma khong duoc CAI DAT thi khong ai kiem, va lop cong
truy-so o tren khong the thay: xuat xu cua 0.9976 hoan toan dung, chi co GIA TRI la bang
chung tu bac bo. Xem [[feedback-cong-kiem-ten-thay-vi-ban-chat]].

CACH CONG NAY LAM VIEC, va vi sao no khong the tu xanh gia:

  - doc nac do duoc `r5_3_convergence_small.csv` (PoA theo so vong, tung vo, tung seed) --
    la DU LIEU DO, khong phai gia tri khai trong ma;
  - doc san `MSA_MIN_ITERS` tu chinh `sim/traffic.py` dang dung, khong go lai o day;
  - doc `main.tex` xem vo nao con duoc trich theo don vi CHIA CHO UE (recovered, blind/UE,
    speedup vs UE). Vo da rut khoi cac don vi do thi khong bi doi hoi.

FAIL neu: mot vo con duoc trich theo don vi chia-cho-UE ma PoA < 1 tai san; hoac nac do
khong phu toi san (khong co du lieu = khong duoc coi la dat); hoac kiem 0 vo.
"""
import argparse
import csv
import os
import re
import sys

# Don vi CHIA CHO can bang. Vo nao xuat hien cung mot trong cac tu nay thi phai co tham
# chieu dat chuan. Tim theo NGHIA (co mau so la UE), khong theo ten bang.
UE_DENOM = ("recovered", "fraction of the equilibrium", "of the UE", "vs.\\ UE",
            "speedup over the equilibrium", "relative to UE")


def read_floor(root):
    s = open(os.path.join(root, "code", "sim", "traffic.py"), encoding="utf-8").read()
    m = re.search(r"^MSA_MIN_ITERS\s*=\s*(\d+)", s, re.M)
    if not m:
        print("  ⛔ khong doc duoc MSA_MIN_ITERS trong sim/traffic.py")
        return None
    return int(m.group(1))


def read_ladder(root):
    """-> {ten_vo: {so_vong: [PoA tung seed]}}"""
    p = os.path.join(root, "code", "results", "r5_3_convergence_small.csv")
    if not os.path.exists(p):
        return None
    out = {}
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            shell = r.get("shell") or r.get("name") or "?"
            try:
                it = int(float(r.get("iters") or r.get("msa_iters") or r.get("T")))
                poa = float(r["poa"]) if "poa" in r else float(r["PoA"])
            except (TypeError, ValueError, KeyError):
                continue
            out.setdefault(shell, {}).setdefault(it, []).append(poa)
    return out


def shells_still_divided(tex):
    """Vo nao con duoc trich theo don vi chia-cho-UE, doc tu chinh van ban."""
    s = open(tex, encoding="utf-8").read()
    s = re.sub(r"(?<!\\)%.*", "", s)
    d = os.path.dirname(os.path.abspath(tex))
    for m in re.findall(r"\\input\{((?:tab|fig)-[^}]*)\}", s):      # bang/hinh la \input
        q = os.path.join(d, m if m.endswith(".tex") else m + ".tex")
        if os.path.exists(q):
            s += "\n" + open(q, encoding="utf-8").read()
    low = s.lower()
    hit = set()
    for n in re.findall(r"\b(132|264|1584)\b", s):
        # chi tinh la "con chia cho UE" neu so vo xuat hien GAN mot tu mau-so-UE
        for m in re.finditer(r"\b%s\b" % n, s):
            w = low[max(0, m.start() - 400):m.end() + 400]
            # ⛔ '–†' / 'withdrawn' ngay canh nghia la o DA BI RUT, khong doi hoi nua
            if any(k.lower() in w for k in UE_DENOM) and not re.search(
                    r"withdraw|not reported|--\s*\\dag|–†|\\dag", w):
                hit.add(n)
                break
    return sorted(hit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", required=True)
    a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(a.tex))))
    root = os.path.dirname(os.path.abspath(os.path.dirname(a.tex)))

    floor = read_floor(root)
    if floor is None:
        return 1
    ladder = read_ladder(root)
    if not ladder:
        print("  ⛔ thieu results/r5_3_convergence_small.csv -- KHONG co nac do de doi chieu.")
        print("     Thieu du lieu khong duoc doc thanh dat: xem [[feedback-kiem-0-don-vi]].")
        return 1

    need = shells_still_divided(a.tex)
    print("  san dang dung: MSA_MIN_ITERS = %d vong (doc tu sim/traffic.py)" % floor)
    print("  vo con trich theo don vi chia-cho-UE: %s" % (", ".join(need) or "(khong co)"))
    if not need:
        print("  ⛔ KIEM 0 VO -- khong doc thanh sach. Neu that su moi don vi chia-cho-UE da")
        print("     duoc rut thi xoa cong nay, dung de no bao xanh tren tap rong.")
        return 1

    bad = 0
    for n in need:
        key = next((k for k in ladder if n in k), None)
        if key is None:
            print("  ⛔  vo %-5s: bai con chia cho UE nhung nac do KHONG CO vo nay" % n)
            bad += 1
            continue
        avail = sorted(ladder[key])
        at = [i for i in avail if i >= floor]
        if not at:
            print("  ⛔  vo %-5s: nac do chi toi %d vong, KHONG phu toi san %d"
                  % (n, max(avail), floor))
            bad += 1
            continue
        it = min(at)
        vals = ladder[key][it]
        worst = min(vals)
        ok = worst >= 1.0
        print("  %s  vo %-5s: PoA tai %d vong = %.4f (thap nhat tren %d seed)%s"
              % ("ok " if ok else "⛔ ", n, it, worst, len(vals),
                 "" if ok else "  <-- DUOI 1, tham chieu KHONG phai can bang"))
        if not ok:
            bad += 1

    print("  da kiem %d vo: %d dat, %d hong" % (len(need), len(need) - bad, bad))
    print("  => %s" % ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
