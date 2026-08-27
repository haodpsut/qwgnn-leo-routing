"""Cong: khong dai luong nao con CHIA CHO can bang o mot vo ma can bang do khong dat chuan.

    python code/scripts/check_msa_reference.py --paper paper --code code

⛔ VI SAO CO FILE NAY. 27/08/2026, nguoi doc ngoai bat mot loi khong cong nao trong 14 cong
nhin thay: vo 264 lay tham chieu can bang giai o T=20, va tai T=20 no cho

    PoA = TTT_UE / TTT_SO = 0.9976 < 1

Day la dieu KHONG THE XAY RA: can bang nguoi dung khong the tot hon toi uu he thong. Nen
0.9976 khong phai "gan 1", no la bang chung rang loi giai CHUA phai can bang. Vay ma moi
dai luong cua vo 264 trong bai deu chia cho no.

Vi sao 14 cong deu xanh: `traffic.py` khai HAI tieu chi dung trong chu thich -- (1) PoA >= 1
va (2) |dUE| < 0.5% -- nhung than ham chi cai dat (2). O vo 264, (2) dat ngay tu 20 vong,
nen ham dung som va bao "da hoi tu". Mot tieu chi duoc VIET ra ma khong duoc CAI DAT thi
khong ai kiem, va lop cong truy-so khong the thay: xuat xu cua 0.9976 hoan toan dung, chi co
GIA TRI la bang chung tu bac bo.

⛔ BAN DAU TIEN CUA CONG NAY SAI, va sai theo dung kieu bai nay di vach ra. No quet VAN XUOI
tim tu "recovered" dung gan "1584", va tra ve TAM bao dong, CA TAM deu gia: tat ca deu la
cau NOI RANG dai luong do da bi rut, hoac giai thich chinh lop loi nay. Do la kiem TEN chu
khong kiem BAN CHAT -- va mot cong bao tam bao dong gia se bi bo qua, tuc no te hon khong co
cong. Xem [[feedback-cong-kiem-ten-thay-vi-ban-chat]] va [[feedback-siet-cong-phai-do-bao-dong-gia]].

BAN NAY KIEM DU LIEU, KHONG KIEM VAN XUOI:

  1. `paper/claims.json`: moi con so cua bai deu neo o day kem CSV, COT va BO LOC. Mot claim
     bi tinh la "chia cho can bang" khi TEN COT cua no noi vay (recovered / ratio_ue /
     blind_over_ue / speedup_vs_ue). Vo lay tu bo loc va tu chinh cac dong CSV, khong tu van
     ban quanh do. Van xuoi co the noi bat cu gi; mot claim thi tro thang toi so.
  2. Cac tep bang SINH RA: dong nao vua mang so vo vua nam duoi mot cot mau-so-UE.
  3. San so vong doc tu chinh `sim/traffic.py`, nac PoA doc tu `r5_3_convergence_small.csv`.

MIEN TRU phai khai TUNG DONG, kem ly do, o ALLOW ben duoi. Mot dai luong chan doan (vi du
blind/UE in theo tung so vong DE CHO THAY mau so troi) la hop le, nhung no phai duoc khai la
chan doan chu khong duoc lang le lot qua.
"""
import argparse
import csv
import json
import os
import re
import sys

# Cot co mau so la CAN BANG. Khop theo tien to/chuoi con, vi CSV dat ten kieu
# recovered_gnn_tau8.0, ratio_ue_gnn_tau0.2, blind_over_ue.
UE_COLS = ("recovered", "ratio_ue", "blind_over_ue", "speedup_vs_ue", "over_ue")

# Mien tru, khai tung dong. Khoa: (tep, nhan dong). Gia tri: ly do.
ALLOW = {
    ("tab-msa.tex", "blind/UE"):
        "dai luong CHAN DOAN: in theo tung so vong de cho thay chinh mau so troi. No la "
        "bang chung ve tham chieu, khong phai mot ket qua duoc bao cao.",
}


def floor_from_code(code):
    s = open(os.path.join(code, "sim", "traffic.py"), encoding="utf-8").read()
    m = re.search(r"^MSA_MIN_ITERS\s*=\s*(\d+)", s, re.M)
    return int(m.group(1)) if m else None


def ladder(code):
    p = os.path.join(code, "results", "r5_3_convergence_small.csv")
    if not os.path.exists(p):
        return None
    out = {}
    for r in csv.DictReader(open(p, encoding="utf-8")):
        try:
            it, poa = int(float(r["iters"])), float(r["poa"])
        except (KeyError, ValueError):
            continue
        out.setdefault(r.get("shell", "?"), {}).setdefault(it, []).append(poa)
    return out


def shell_of(text):
    # ⛔ KHONG dung \b o dau: ten vo trong CSV la "w132", "w264_i53", va giua 'w' voi '1'
    # khong co ranh gioi tu, nen \b(132)\b truot HET. Ban dau tien cua cong nay bao
    # "kiem 0 don vi" tren mot bai con nguyen 30 claim chia cho can bang, chi vi cai \b do.
    m = re.search(r"(?<!\d)(1584|396|264|198|132)(?!\d)", str(text))
    return m.group(1) if m else None


def claims_dividing_by_ue(paper, code):
    """-> {vo: [id claim]}  doc tu claims.json, khong doc van xuoi."""
    p = os.path.join(paper, "claims.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    out = {}
    for c in (d["claims"] if isinstance(d, dict) else d):
        col = str(c.get("column", ""))
        if not any(k in col for k in UE_COLS):
            continue
        # Vo lay tu BO LOC truoc; neu bo loc khong noi thi doc cac dong CSV that su duoc chon.
        sh = shell_of(" ".join(str(v) for v in (c.get("filter") or {}).values()))
        if sh is None:
            q = os.path.join(paper, c.get("csv", ""))
            if os.path.exists(q):
                rows = list(csv.DictReader(open(q, encoding="utf-8")))
                flt = c.get("filter") or {}
                sel = [r for r in rows
                       if all(str(r.get(k)) == str(v) for k, v in flt.items())]
                shells = {shell_of(r.get("shell") or r.get("n_sat") or "") for r in sel}
                shells.discard(None)
                if len(shells) == 1:
                    sh = shells.pop()
        if sh:
            out.setdefault(sh, []).append(c["id"])
    return out


def rows_dividing_by_ue(paper):
    """-> [(tep, nhan dong, vo)] doc cac bang SINH RA."""
    hits = []
    for f in sorted(os.listdir(paper)):
        if not (f.startswith("tab-") and f.endswith(".tex")):
            continue
        s = open(os.path.join(paper, f), encoding="utf-8").read()
        body = s[s.find(r"\toprule"):] if r"\toprule" in s else ""
        for line in body.split("\\\\"):
            # Nhan trong bang la van xuoi ("blind/UE", "recovered fraction"), khong phai ten
            # cot CSV. Chuan hoa ca hai ve chi con chu cai roi so khop chuoi con.
            norm = re.sub(r"[^a-z]", "", line.lower())
            if not any(re.sub(r"[^a-z]", "", k) in norm for k in UE_COLS) and \
               not re.search(r"blind.{0,4}ue|ue.{0,4}ratio", line.lower()):
                continue
            sh = shell_of(line)
            if sh:
                lab = " ".join(line.split("&")[0].split())[:40]
                hits.append((f, lab, sh))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    ap.add_argument("--code", required=True)
    a = ap.parse_args()
    paper, code = os.path.abspath(a.paper), os.path.abspath(a.code)

    floor = floor_from_code(code)
    lad = ladder(code)
    if floor is None:
        print("  ⛔ khong doc duoc MSA_MIN_ITERS trong sim/traffic.py")
        return 1
    if not lad:
        print("  ⛔ thieu results/r5_3_convergence_small.csv -- khong co nac do de doi chieu;")
        print("     thieu du lieu KHONG duoc doc thanh dat.")
        return 1
    cl = claims_dividing_by_ue(paper, code)
    if cl is None:
        print("  ⛔ thieu paper/claims.json -- chay make_claims.py truoc")
        return 1

    print("  san dang dung: MSA_MIN_ITERS = %d vong (doc tu sim/traffic.py)" % floor)

    units, bad = 0, 0
    for sh in sorted(cl, key=int):
        ids = cl[sh]
        units += 1
        key = next((k for k in lad if sh in k), None)
        if key is None:
            bad += 1
            print("  ⛔  vo %-5s: %d claim chia cho can bang, ma nac do KHONG CO vo nay"
                  % (sh, len(ids)))
            print("      %s" % ", ".join(sorted(ids)[:6]))
            continue
        at = sorted(i for i in lad[key] if i >= floor)
        if not at:
            bad += 1
            print("  ⛔  vo %-5s: nac do chi toi %d vong, khong phu toi san %d"
                  % (sh, max(lad[key]), floor))
            continue
        worst = min(lad[key][at[0]])
        ok = worst >= 1.0
        if not ok:
            bad += 1
        print("  %s  vo %-5s: %2d claim chia cho can bang | PoA tai %d vong = %.4f%s"
              % ("ok " if ok else "⛔ ", sh, len(ids), at[0], worst,
                 "" if ok else "  <-- DUOI 1, tham chieu khong phai can bang"))

    for f, lab, sh in rows_dividing_by_ue(paper):
        why = next((v for (ff, ll), v in ALLOW.items() if ff == f and ll in lab), None)
        units += 1
        if why:
            print("  --  %-14s dong %-22s vo %-5s: mien tru da khai" % (f, lab, sh))
            continue
        key = next((k for k in lad if sh in k), None)
        at = sorted(i for i in (lad.get(key) or {}) if i >= floor)
        worst = min(lad[key][at[0]]) if at else None
        if worst is None or worst < 1.0:
            bad += 1
            print("  ⛔  %-14s dong %-22s vo %-5s: bang in dai luong chia cho can bang"
                  % (f, lab, sh))
        else:
            print("  ok  %-14s dong %-22s vo %-5s" % (f, lab, sh))

    if units == 0:
        print("  ⛔ KIEM 0 DON VI -- khong duoc doc thanh sach. Neu that su khong con dai")
        print("     luong nao chia cho can bang thi xoa cong nay di.")
        return 1
    print("  da kiem %d don vi: %d dat, %d hong" % (units, units - bad, bad))
    print("  => %s" % ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
