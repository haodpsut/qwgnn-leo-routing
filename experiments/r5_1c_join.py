"""R5.1c -- gom cac don vi cua r5_1b thanh MOT CSV, va ap rang buoc vat ly o day.

    python r5_1c_join.py /tmp/r5run  ->  results/r5_1_shell1584_converged.csv

⛔ VI SAO KIEM O DAY chu khong o tung don vi: mot don vi chi biet gia tri cua chinh no.
Rang buoc "SO <= UE" va "moi chinh sach >= SO" chi kiem duoc khi da co du ca ba, tuc o
buoc gom. Ban `r4_1` cu ghi nhan vi pham roi chay tiep, va do la duong dan toi viec cong
bo so cua mot loi giai chua hoi tu suot chin ngay.

Nen o day vi pham la LOI, khong phai ghi chu:
  - SO > UE  -> loi giai chua hoi tu -> DUNG, khong ghi CSV
  - mot chinh sach < SO -> khong the xay ra -> DUNG

Va neu toi uu tau nam o BIEN luoi thi in canh bao ro rang: con so do la CHAN DUOI, khong
duoc trich nhu mot gia tri da do duoc.
"""
import csv
import glob
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "r5_1_shell1584_converged.csv")


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "/tmp/r5run"
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "*.out"))):
        t = open(p).read().strip()
        if not t:
            print("  ⛔ THIEU ket qua: %s (don vi chua chay xong)" % os.path.basename(p))
            return 1
        seed, job, param, iters, ttt, secs = t.split(",")
        rows.append(dict(seed=int(seed), job=job, param=param, iters=iters,
                         ttt=float(ttt), secs=float(secs)))
    if not rows:
        print("  ⛔ KHONG CO don vi nao trong %s -- kiem 0 don vi, khong phai sach" % d)
        return 1

    seeds = sorted({r["seed"] for r in rows})
    get = lambda s, j, p="": next((r["ttt"] for r in rows
                                   if r["seed"] == s and r["job"] == j and r["param"] == p), None)
    taus = sorted({float(r["param"]) for r in rows if r["job"] == "gnn"})
    epss = sorted({float(r["param"]) for r in rows if r["job"] == "ecmp"})

    out = []
    for s in seeds:
        blind, ue, so = get(s, "blind"), get(s, "ue"), get(s, "so")
        if None in (blind, ue, so):
            print("  ⛔ seed %d thieu blind/ue/so" % s)
            return 1
        if so > ue + 1e-6:
            print("  ⛔ DUNG: seed %d co PoA=%.4f < 1 (SO=%.1f > UE=%.1f)." % (s, ue / so, so, ue))
            print("     Loi giai VAN chua hoi tu o so vong da dung. Khong duoc ha nguong:")
            print("     hoac tang so vong, hoac RUT moi tuyen bo quy chieu ve can bang o vo nay.")
            return 1
        span = blind - ue
        row = dict(shell="w1584_i53", n_sat=1584, seed=s, unit_of_analysis="vo-x-seed",
                   iters=int(next(r["iters"] for r in rows if r["seed"] == s and r["job"] == "ue")),
                   blind_ttt=round(blind, 4), ue_ttt=round(ue, 4), so_ttt=round(so, 4),
                   poa=round(ue / so, 4), blind_over_ue=round(blind / ue, 2))
        for t in taus:
            v = get(s, "gnn", ("%g" % t) if ("%g" % t) in {r["param"] for r in rows} else str(t))
            if v is None:
                print("  ⛔ seed %d thieu gnn tau=%g" % (s, t))
                return 1
            if v < so - 1e-6:
                print("  ⛔ seed %d: gnn tau=%g cho TTT %.1f DUOI system optimum %.1f" % (s, t, v, so))
                return 1
            row["recovered_gnn_tau%g" % t] = round((blind - v) / span, 4)
            row["ratio_ue_gnn_tau%g" % t] = round(v / ue, 2)
        for e in epss:
            v = get(s, "ecmp", ("%g" % e) if ("%g" % e) in {r["param"] for r in rows} else str(e))
            if v is None or v < so - 1e-6:
                print("  ⛔ seed %d: ecmp eps=%g thieu hoac duoi SO" % (s, e))
                return 1
            row["recovered_ecmp_eps%g" % e] = round((blind - v) / span, 4)
            row["ratio_ue_ecmp_eps%g" % e] = round(v / ue, 2)
        out.append(row)

    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        wr.writeheader()
        wr.writerows(out)

    med = lambda k: st.median(r[k] for r in out)
    bt = max(taus, key=lambda t: med("recovered_gnn_tau%g" % t))
    be = max(epss, key=lambda e: med("recovered_ecmp_eps%g" % e))
    print("=" * 74)
    print("  VO 1584, loi giai %d vong, %d seed" % (out[0]["iters"], len(out)))
    print("=" * 74)
    print("  PoA        : %.4f  (phai >= 1)" % med("poa"))
    print("  blind / UE : %.1f" % med("blind_over_ue"))
    print("  GNN tot nhat  : %.3f o tau=%g" % (med("recovered_gnn_tau%g" % bt), bt))
    print("  blind tot nhat: %.3f o eps=%g" % (med("recovered_ecmp_eps%g" % be), be))
    if bt == taus[-1]:
        print("  ⚠ toi uu tau NAM O BIEN luoi (%g): con so tren la CHAN DUOI, khong phai" % bt)
        print("    gia tri da do duoc. Noi dai luoi truoc khi trich no vao bai.")
    else:
        print("  ✅ toi uu tau nam BEN TRONG luoi")
    print("  => da ghi results/%s" % os.path.basename(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
