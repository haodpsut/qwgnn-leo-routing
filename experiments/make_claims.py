"""Derive claims.json and the results summary table from the result CSVs. Nothing is typed by hand.

WHY. G3 writing preflight blocks on "no results summary table": a reader should see every headline
number and where it comes from in one place, before the sections that derive them. For an audit
paper that table IS the paper, so it is worth generating rather than transcribing.

And the manuscript has never been through the pipeline: there is no claims.json, which is why
Reviewer 1 had to catch a 93 vs 94 mismatch between Tables VI, VII and VIII by eye.

THE MANIFEST MUST LET THE GATE RECOMPUTE, NOT TRUST ME. verify_numbers.py takes
{id, paper_value, csv, column, filter, agg} and recomputes the value itself. A manifest that only
recorded "this came from that CSV" would prove provenance and nothing else, and provenance says
nothing about whether the aggregation was right. My first version did exactly that and the gate
rejected all 29 claims for a missing `column`, which is the gate working.

`filter` matches columns by equality, so a threshold like "offered load above 4x capacity" cannot
be written as a filter. Rather than dropping the threshold or hiding it inside this script, the
band is written back into the experiment CSV as a LABEL COLUMN. The label then travels with the
data, the filter is a plain equality, and a reader opening the CSV can see which rows a headline
number was computed over without reading any code.
"""
import csv
import io
import json
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
PAPER = os.path.abspath(os.path.join(ROOT, "..", "paper"))
OUT_JSON = os.path.join(PAPER, "claims.json")
OUT_TEX = os.path.join(PAPER, "tab-summary.tex")

C = []


def load(name):
    p = os.path.join(RES, name)
    if not os.path.exists(p):
        raise SystemExit(f"thieu {name}: chay lai thi nghiem truoc")
    return list(csv.DictReader(open(p)))


def add_band(name, src_col, bands):
    """Write a label column back into the experiment CSV so a threshold becomes a plain filter."""
    p = os.path.join(RES, name)
    rows = list(csv.DictReader(open(p)))
    if "load_band" in rows[0]:
        return rows
    for r in rows:
        v = float(r[src_col])
        r["load_band"] = next(lbl for lbl, lo, hi in bands if lo <= v < hi)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  + them cot 'load_band' vao {name}")
    return rows


def claim(cid, rows, csvfile, column, flt, note, places=3):
    sel = [r for r in rows if all(str(r[k]) == str(v) for k, v in flt.items())]
    if not sel:
        raise SystemExit(f"{cid}: filter {flt} khong khop dong nao")
    val = st.median(float(r[column]) for r in sel)
    C.append({"id": cid, "paper_value": f"{val:.{places}f}",
              # Duong dan phai tuong doi voi THU MUC BAI, vi cong chay tu do (G7 cd vao paper/).
              # Ghi tuong doi voi goc du an thi chay tay o goc thi dung, ma cong thi hong,
              # va no hong theo kieu te nhat: bao 49/49 SAI thay vi bao khong tim thay file.
              "csv": f"../code/results/{csvfile}", "column": column,
              "filter": flt, "agg": "median", "places": places,
              "unit_of_analysis": rows[0].get("unit_of_analysis", "?"), "note": note})
    return val


def claim_raw(cid, csvfile, column, flt, agg, places, note, scale=None):
    """Neo mot con so THUA KE tu ban cu. Khac claim(): lay trung binh (dung nhu bai ghi
    'mean over seeds and instances') va cho phep scale, vi CSV ghi phan so con bai in phan tram."""
    rows = list(csv.DictReader(open(os.path.join(RES, csvfile))))
    sel = [r for r in rows if all(str(r[k]) == str(v) for k, v in flt.items())]
    if not sel:
        raise SystemExit(f"{cid}: filter {flt} khong khop dong nao trong {csvfile}")
    # LOI CUA CHINH TOI, bat duoc khi them claim so vong: ham nay GHI agg vao ban ghi nhung
    # luon tinh MEAN. Cong tinh lai theo agg da ghi, nen mot claim khai median se lech ngay.
    # Cong bat duoc, nhung dung ra ham khong duoc noi doi ngay tu dau.
    vals = [float(r[column]) for r in sel]
    val = {"median": st.median, "mean": st.mean, "min": min, "max": max,
           "sum": sum}[agg](vals)
    if scale:
        val = eval(scale, {"__builtins__": {}}, {"x": val})
    rec = {"id": cid, "paper_value": f"{val:.{places}f}",
           "csv": f"../code/results/{csvfile}", "column": column, "filter": flt,
           "agg": agg, "places": places,
           "unit_of_analysis": rows[0].get("unit_of_analysis", "seed-x-instance"), "note": note}
    if scale:
        rec["scale"] = scale
    C.append(rec)
    return val


def add_proact_deltas():
    """Ghi hieu GHEP CAP proactive - blind(eps tot nhat) vao CSV, cho TUNG muc troi.

    Bang tom tat truoc do chi in mot hang o muc troi 1.5, va hang do cho thay baseline mu
    THANG 0.984 so voi 0.737 ma khong cau nao trong bai nhac toi. Doc ca luoi thi thay no
    khong phai mot hang la: proactive thua o CA NAM muc troi ngoai phan phoi, ke ca muc 0.
    """
    name = "r2_7_proactive_vs_ecmp.csv"
    p = os.path.join(RES, name)
    rows = list(csv.DictReader(open(p)))
    if "gap_proact" in rows[0]:
        return rows
    epss = [k for k in rows[0] if k.startswith("recovered_ecmp")]
    for shell in {r["shell"] for r in rows}:
        sel = [r for r in rows if r["shell"] == shell]
        be = max(epss, key=lambda e: st.median(float(r[e]) for r in sel))
        for r in sel:
            r["best_eps_col"] = be
            r["gap_proact"] = round(float(r["recovered_proact"]) - float(r[be]), 4)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  + them cot 'gap_proact' vao {name}")
    return rows


def add_ue_ratios():
    """Ghi TY LE so voi can bang vao CSV: blind/UE va chinh sach/UE.

    Y 2.4 cua phan bien ngoai. 'Recovered fraction' co mau so (blind - UE). Khi blind benh hoan
    thi mau so khong lo va MOI chinh sach biet trai tai deu duoc diem cao. Cung con so 0.94
    nghia la 3.4x can bang o vo 132 nhung 47x o vo 1584. Ty le so voi UE la thu do KHONG bi
    hieu ung do, nen no phai di kem moi phan gap thu hoi.
    """
    name = "p6_baselines.csv"
    p = os.path.join(RES, name)
    rows = list(csv.DictReader(open(p)))
    if "ratio_gnn_over_ue" in rows[0]:
        return rows
    for r in rows:
        ue = float(r["r_ue"])
        r["ratio_gnn_over_ue"] = round(float(r["r_gnn"]) / ue, 3)
        r["ratio_blind_over_ue"] = round(1.0 / ue, 2)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  + them cot ty le so voi UE vao {name}")
    return rows


def pool_264_fixedtau():
    """Gop MOI don vi do phan gap thu hoi cua vo 264 o tau=0.2, tu MOI run set, vao mot CSV.

    Phan bien ngoai (y 3.1-3.3) dem duoc BA gia tri cho dai luong nay: 0.915 (r2_7_eps_sweep),
    0.885 (r2_7_fair_tuned_wide) va 0.93 (Bang VIII). Ca ba deu tra nguoc dung ve CSV cua
    chung; chung den tu ba lan chay khac nhau. Xuat xu dung KHONG bao dam nhat quan, va dat
    ba con so canh nhau trong mot bang tu xung la "moi con so headline" thi doc gia khong the
    biet cai nao la cai nao.

    Cach chua khong phai chon lay mot con, ma la GOP roi bao ca do rong. Sau khi gop:
    17 don vi, trung vi 0.889, khoang [0.838, 0.923].
    """
    out, rows = [], None
    for f, col, flt in (("r2_7_eps_sweep.csv", "recovered_gnn", lambda r: r["shell"] == "w264_i53"),
                        ("r2_7_fair_tuned_wide.csv", "recovered_gnn_tau0.2",
                         lambda r: r["shell"] == "w264_i53"),
                        ("r1_1_tau_sweep.csv", "recovered_tau0.2", lambda r: "264" in r["shell"])):
        for r in csv.DictReader(open(os.path.join(RES, f))):
            if flt(r):
                out.append({"run_set": f, "shell": "w264_i53", "tau": "0.2",
                            "seed": r.get("seed", ""), "recovered": float(r[col]),
                            "unit_of_analysis": "vo-x-seed(-x-lat-cat)"})
    p = os.path.join(RES, "pooled_w264_fixedtau.csv")
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"  + gop {len(out)} don vi tu 3 run set -> pooled_w264_fixedtau.csv")
    return out


def emit_macros():
    """Sinh paper/claims-macros.tex de bai GOI so thay vi GO so.

    VI SAO. Ngay 18/08 chay lai toan bo thi nghiem tren mot may khac: 66/116 claim doi gia
    tri, va 44 trong so do van con gia tri CU nam trong main.tex. Cong truy so bao 116/116
    XANH suot, vi no chi doi chieu claims.json voi CSV va khong bao gio doc bai. Mot con so
    go tay vao van xuoi la mot ban sao khong ai dong bo.

    Va sua tay thi nguy hiem: chuoi "0.008" vua la gia tri cua gap_fair_w198_i53 vua la mot
    p-value o dong ngay ben canh. Thay the mu se lam hong bai ma khong ai thay.

    Dung: $\clm{gap-fair-w198-i53}$ thay cho $0.008$. Gach duoi doi thanh gach ngang vi
    gach duoi la ky tu dac biet trong LaTeX.
    """
    lines = [r"% SINH TU make_claims.py -- DUNG SUA TAY.",
             r"% Dinh nghia mot lan; bai goi bang \clm{ten-claim}.",
             r"\makeatletter",
             r"\newcommand{\defclaim}[2]{\expandafter\gdef\csname cl@#1\endcsname{#2}}",
             r"\newcommand{\clm}[1]{%",
             r"  \ifcsname cl@#1\endcsname\csname cl@#1\endcsname",
             r"  \else\textbf{??#1??}\PackageWarning{claims}{khong co claim #1}\fi}",
             r"\makeatother"]
    for c in sorted(C, key=lambda x: x["id"]):
        lines.append("\\defclaim{%s}{%s}" % (c["id"].replace("_", "-"), c["paper_value"]))
    open(os.path.join(PAPER, "claims-macros.tex"), "w").write("\n".join(lines) + "\n")
    print(f"  + {len(C)} macro -> paper/claims-macros.tex")


def claim_r4():
    """Ket qua vong R4, sinh ra tu ban phan bien ngoai 17/08/2026."""
    # 2.2: so vong MSA can de hoi tu. Bang II cua bai ghi "T ~ 20" khong kem dieu kien,
    # va 20 dung la con so KHOI DONG LANH. Khoi dong am la doi thu that trong van hanh.
    for sh in ("w132", "w264"):
        for kind in ("cold", "warm"):
            claim_raw(f"msa_iters_{kind}_{sh}", "r4_2_warmstart_iters.csv", f"iters_{kind}",
                      {"shell": sh}, "median", 0,
                      f"so vong MSA de vao trong 0.5% TTT quy chieu, khoi dong {kind}, {sh}")

    # ⛔ VO 1584 -- KHONG con claim nao chia cho can bang. Cac claim cu (s1584_gnn_besttau,
    # s1584_ecmp_best, s1584_gap, s1584_blind_over_ue, s1584_ratio_*) deu lay tu
    # r4_1_shell1584_controls.csv, tuc deu chia cho mot loi giai MSA co PoA < 1 tren ca ba
    # instance. PoA < 1 la khong the xay ra, nen mau so do khong phai can bang va cac ti so
    # khong "kem chinh xac" ma KHONG XAC DINH. Xoa han thay vi noi long dung sai.
    #
    # Thay bang cac dai luong QUY CHIEU BLIND tu r5_4_shell1584_uefree.py: blind do truc tiep,
    # khong can giai can bang lan nao, nen thu hang giua hai chinh sach van dung nguyen.
    u, src = [], None
    for fn in sorted(os.listdir(RES)):
        if fn.startswith("r5_4_shell1584_uefree") and fn.endswith(".csv"):
            u += list(csv.DictReader(open(os.path.join(RES, fn)))); src = fn
    if not u:
        raise SystemExit("thieu r5_4_shell1584_uefree*.csv: vo 1584 khong con nguon nao khac")
    claim("s1584_relblind_gnn", u, src, "rel_best_gnn", {}, "vo 1584, GNN / blind", places=4)
    claim("s1584_relblind_ecmp", u, src, "rel_best_ecmp", {}, "vo 1584, blind-mp / blind", places=4)
    claim("s1584_margin", u, src, "margin_pct", {}, "cach biet blind-vs-GNN, %", places=0)
    # ⛔ MOT DEM CUNG PHAI TAI TINH DUOC. Ban truoc ghi cac so nay voi ten cot gia
    # "(dem tren cac dong)", va cong verify_numbers bao ERR tren ca nam -- dung: no khong
    # co cach nao suy lai chung tu CSV. Cach sua khong phai noi long cong ma la ghi cot
    # THAT vao CSV, roi de phep gop san (sum/min/max) lam viec dem. Nho vay moi con so
    # dem van co the doi chieu nguoc ve du lieu nhu moi con so khac.
    for fn in sorted(os.listdir(RES)):
        if not (fn.startswith("r5_4_shell1584_uefree") and fn.endswith(".csv")):
            continue
        q = os.path.join(RES, fn)
        rr = list(csv.DictReader(open(q)))
        if not rr or "ecmp_win" in rr[0]:
            continue
        for r in rr:
            r["ecmp_win"] = 1 if r["winner"] == "ecmp" else 0
            r["unit"] = 1
        with open(q, "w", newline="") as f:
            wtr = csv.DictWriter(f, fieldnames=list(rr[0].keys()))
            wtr.writeheader(); wtr.writerows(rr)
        print("  + them cot 'ecmp_win', 'unit' vao %s" % fn)

    for cid, col, agg, pl, note in (
            ("s1584_margin_lo", "margin_pct", "min", 0, "cach biet blind-vs-GNN nho nhat, %"),
            ("s1584_margin_hi", "margin_pct", "max", 0, "cach biet blind-vs-GNN lon nhat, %"),
            ("s1584_ecmp_wins", "ecmp_win", "sum", 0, "so instance blind thang"),
            ("s1584_n_inst", "unit", "sum", 0, "so instance do o vo 1584"),
            ("s1584_tau_edge", "tau_at_grid_edge", "sum", 0,
             "so instance co tau toi uu nam O BIEN luoi")):
        claim_raw(cid, src, col, {}, agg, pl, note)

    # 4.2/4.3: hang so cua Menh de 1, dat bang so thay vi de o dang Theta().
    for sh in ("w132_i53", "w264_i53"):
        for cid, col, pl in ((f"bound_H_{sh}", "H_hops", 0),
                             (f"bound_c1H_ue_{sh}", "c1H_at_ue", 0),
                             (f"bound_c1H_blind_{sh}", "c1H_at_blind", 0),
                             (f"bound_propratio_{sh}", "prop_ratio", 2)):
            claim_raw(cid, "r4_3_bound_constants.csv", col, {"shell": sh}, "median", pl,
                      f"hang so Menh de 1: {col} tren {sh}")

    for load, tag in (("300", "lo"), ("1000", "hi")):
        claim_raw(f"poa_{tag}", "poa.csv", "poa", {"load": load}, "mean", 3,
                  f"price of anarchy tai {load} nhu cau")

    # 2.3: phan ra thoi gian theo chang, doi chieu voi lat cat 60s cua MO PHONG (khong phai
    # "vai giay" cua van xuoi). Chi phi nam o hai chang PHU THUOC NHU CAU, con chang duy nhat
    # tien tinh duoc la forward, von gan nhu mien phi.
    for sh in ("w132", "w264", "w1584"):
        for cid, col, pl in ((f"time_total_{sh}", "t_total_s", 2),
                             (f"time_feat_{sh}", "t_features_s", 3),
                             (f"time_fwd_{sh}", "t_forward_s", 3),
                             (f"time_dec_{sh}", "t_decode_s", 3),
                             (f"time_frac_{sh}", "frac_of_slot", 3)):
            claim_raw(cid, "r4_4_stage_timing.csv", col, {"shell": sh}, "median", pl,
                      f"phan ra thoi gian: {col} tren {sh}")

    # R4.5: ty le hoa chinh xac. Bai tung viet "khong mot cap nao", va do lai thi CO 527 cap
    # tren 335709. Ket luan (ECMP sach vo gan nhu vo dung) van dung, loi khang dinh tuyet doi
    # thi sai. Con so 2620 cu chi nam trong mot dong chu thich ma, khong co artifact nao.
    ties = list(csv.DictReader(open(os.path.join(RES, "r4_5_exact_ties.csv"))))
    for sh in ("w132_i53", "w264_i53", "w264_i70"):
        claim_raw(f"tiefrac_{sh}", "r4_5_exact_ties.csv", "tie_fraction", {"shell": sh},
                  "median", 4, f"ty le cap nut-dich co hoa chi phi chinh xac, {sh}")
    claim_raw("tie_pairs_total", "r4_5_exact_ties.csv", "exact_tie_pairs", {}, "sum", 0,
              "tong so cap co hoa tren moi vo va seed")
    claim_raw("tie_pairs_examined", "r4_5_exact_ties.csv", "node_dest_pairs", {}, "sum", 0,
              "tong so cap nut-dich da xet")
    # Truong hop XAU NHAT tren moi vo va seed. Neu ke ca truong hop te nhat cung be thi ket
    # luan "ECMP sach vo gan nhu vo dung" moi vung; bao trung vi la bao cho minh de.
    claim_raw("tiefrac_worst", "r4_5_exact_ties.csv", "tie_fraction", {}, "max", 4,
              "ty le hoa lon nhat tren moi vo va seed")

    # Bang IV (tab:headroom) co 15 con so va truoc do KHONG claim nao cham toi, du chinh no cho
    # ty so 41x ma cam bay P4 dua vao. Neo tung o.
    for pr in ("100", "300", "600", "1000", "1600"):
        f = {"shell": "starlink_mini132", "pairs": pr}
        claim_raw(f"hr_blind_{pr}", "p4_headroom.csv", "blind_ttt", f, "mean", 1,
                  f"TTT tuyet doi cua blind, vo 132, {pr} nhu cau")
        claim_raw(f"hr_ue_{pr}", "p4_headroom.csv", "ue_ttt", f, "mean", 1,
                  f"TTT tuyet doi cua UE, vo 132, {pr} nhu cau")

    pool = pool_264_fixedtau()
    claim("pooled_w264_fixedtau", pool, "pooled_w264_fixedtau.csv", "recovered",
          {"shell": "w264_i53"}, "gop MOI run set do cung dai luong nay")
    claim_raw("pooled_w264_lo", "pooled_w264_fixedtau.csv", "recovered",
              {"shell": "w264_i53"}, "min", 3, "can duoi cua khoang gop")
    claim_raw("pooled_w264_hi", "pooled_w264_fixedtau.csv", "recovered",
              {"shell": "w264_i53"}, "max", 3, "can tren cua khoang gop")

    ub = add_ue_ratios()
    for split, tag in (("in-dist", "indist"), ("ood", "ood")):
        for col, nm in (("ratio_gnn_over_ue", "ratio_gnn_ue"),
                        ("ratio_blind_over_ue", "ratio_blind_ue")):
            claim(f"{nm}_{tag}", ub, "p6_baselines.csv", col, {"split": split},
                  f"ty le so voi can bang, {col}, {split}", places=2)

    pr = add_proact_deltas()
    for sh in ("w132", "w264"):
        for d in ("0.0", "1.5"):
            claim(f"proact_gap_{sh}_drift{d.replace('.','')}", pr,
                  "r2_7_proactive_vs_ecmp.csv", "gap_proact", {"shell": sh, "drift": d},
                  f"hieu ghep cap proactive - blind(eps tot), {sh}, troi {d}")
    # Van xuoi viet "trails it by 0.247", tuc DO LON cua mot hieu AM. Neo rieng do lon,
    # neu khong cong se doi chieu 0.247 voi -0.247 va bao khong khop ma khong ai sai ca.
    for sh, d in (("w264", "1.5"), ("w264", "0.0")):
        claim_raw(f"proact_deficit_{sh}_drift{d.replace('.','')}",
                  "r2_7_proactive_vs_ecmp.csv", "gap_proact", {"shell": sh, "drift": d},
                  "median", 3, f"do lon thieu hut cua proactive so voi blind, {sh}, troi {d}",
                  scale="-x")


def claim_inherited():
    """Cac so headline mang tu ban bi reject sang. Truoc do KHONG con nao duoc neo: cong bao
    49/49 xanh nhung 49 claim ay deu thuoc phan viet moi, nen con so do chi noi ve mot nua bai."""
    # blind multipath da duoc them vao chinh thi nghiem nay (y 2.6 cua phan bien ngoai): bang
    # ket qua CHINH truoc do thieu dung doi thu manh nhat, va caption chi thua nhan thieu.
    # Do tren CUNG instance de khoi phai ghep so tu run set khac.
    for who, col in (("gnn", "r_gnn"), ("ue", "r_ue"), ("so", "r_so"),
                     ("geo", "r_geo"), ("onestep", "r_1step"), ("ecmp", "r_ecmp")):
        for split in ("in-dist", "ood"):
            claim_raw(f"rel_{who}_{split.replace('-','')}", "p6_baselines.csv", col,
                      {"split": split}, "mean", 2,
                      f"thoi gian di chuyen tuong doi so voi blind, {who}, {split}")
    for prop in ("GCN", "Heat", "QW"):
        for split, tag in (("in-dist", "indist"), ("ood-largeshell", "ood")):
            # Bai in dang THAP PHAN cho moi "recovered fraction" (dai luong ten la fraction thi
            # in 97% la tu mau thuan). Truoc do nua bai in %, nua bai in thap phan.
            claim_raw(f"abl_{prop.lower()}_{tag}", "p5_ablation.csv", "recovered",
                      {"prop": prop, "split": split}, "mean", 2,
                      f"phan gap thu hoi ({prop}, {split})")


def add_fair_deltas(name):
    """Ghi hieu theo TUNG DONG vao CSV: GNN(tau tot) - ECMP(eps tot), va gia phai tra cho tau co dinh."""
    p = os.path.join(RES, name)
    rows = list(csv.DictReader(open(p)))
    if "gap_fair" in rows[0]:
        return rows
    taus = sorted({k.split("tau")[1] for k in rows[0] if "recovered_gnn_tau" in k}, key=float)
    epss = sorted({k.split("eps")[1] for k in rows[0] if "recovered_ecmp_eps" in k}, key=float)
    for shell in {r["shell"] for r in rows}:
        sel = [r for r in rows if r["shell"] == shell]
        bt = max(taus, key=lambda t: st.median(float(r[f"recovered_gnn_tau{t}"]) for r in sel))
        be = max(epss, key=lambda e: st.median(float(r[f"recovered_ecmp_eps{e}"]) for r in sel))
        for r in sel:
            r["best_tau"] = bt
            r["best_eps"] = be
            r["gap_fair"] = round(float(r[f"recovered_gnn_tau{bt}"])
                                  - float(r[f"recovered_ecmp_eps{be}"]), 4)
            r["cost_of_fixed_tau"] = round(float(r[f"recovered_gnn_tau{bt}"])
                                           - float(r["recovered_gnn_tau0.2"]), 4)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  + them cot dan xuat vao {name}")
    return rows


def sign_test_p(k, n):
    """p hai phia cua kiem dinh dau. Khong dung scipy de artifact chay duoc tren cai dat tran.

    Vi sao can: cot "wins" in 8/8 va 6/8 canh nhau nhu the chung cung loai bang chung. Khong
    phai: 8/8 cho p=0.0078, con 6/8 cho p=0.289, tuc mot cai la bang chung va cai kia thi khong.
    In ti so ma khong in p la de nguoi doc tu suy ra dieu bai khong do duoc.
    """
    from math import comb
    tail = sum(comb(n, i) for i in range(min(k, n - k) + 1))
    return min(1.0, 2.0 * tail / (2 ** n))


def emit_tables_and_figure():
    """Sinh HAI bang va MOT hinh tu CSV.

    Bay luot do sinh ra 11 file ket qua va khong mot bang hay hinh nao. Voi mot bai do dac
    thi do la thieu sot nang: nguoi doc khong nhin duoc HINH DANG cua bat cu thu gi, chi doc
    duoc cac con so roi rac trong van xuoi. Duong cong nhiet do la vi du ro nhat -- no QUAY DAU
    tren vo huan luyen va TRAI PHANG tren vo lon, va khong cau van nao thay duoc mot hinh.
    """
    feas = load("r3_2_feasibility.csv")
    loss = load("r3_2_loss_models.csv")
    fair = load("r2_7_fair_tuned_wide.csv")
    BANDS = [("le1x", "$\\le 1\\times$"), ("1to2x", "$1$--$2\\times$"),
             ("2to4x", "$2$--$4\\times$"), ("gt4x", "$>4\\times$")]
    rows = []
    for key, lbl in BANDS:
        f = [r for r in feas if r["load_band"] == key]
        l = [r for r in loss if r["load_band"] == key]
        if not f:
            continue
        m = lambda rs, c: st.median(float(r[c]) for r in rs)
        rows.append(f"{lbl} & {len(f)} & {m(f,'gain_bpr_pct'):.1f} & {m(l,'gain_product_pct'):.1f} & "
                    f"{m(l,'gain_bottleneck_pct'):.1f} & {m(l,'gain_maxmin_pct'):.1f} \\\\")
    open(os.path.join(PAPER, "tab-feasibility.tex"), "w").write(
        "% SINH TU make_claims.py -- DUNG SUA TAY\n"
        "\\begin{table}[t]\n\\centering\\small\n"
        "\\caption{The congestion-aware advantage measured two ways on the same configurations. "
        "The delay column is the BPR travel-time reduction; the three loss columns are the increase "
        "in delivered rate under three feasibility models that disagree about how multi-hop loss "
        "compounds. Rows are bands of the offered load blind routing places on its busiest link; "
        "median over (shell, load, seed).}\n"
        "\\label{tab:feasibility}\n"
        "\\begin{tabular}{@{}lrrrrr@{}}\n\\toprule\n"
        "offered load & $n$ & delay (\\%) & \\multicolumn{3}{c}{delivered rate (\\%)} \\\\\n"
        "\\cmidrule(l){4-6}\n & & (BPR) & product & bottleneck & max-min \\\\\n\\midrule\n"
        + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

    TAUS = sorted({k.split("tau")[1] for k in fair[0] if "recovered_gnn_tau" in k}, key=float)
    EPSS = sorted({k.split("eps")[1] for k in fair[0] if "recovered_ecmp_eps" in k}, key=float)
    NICE = {"w132_i53": "$132$, $53^\\circ$ (trained)", "w198_i53": "$198$, $53^\\circ$",
            "w264_i53": "$264$, $53^\\circ$", "w264_i70": "$264$, $70^\\circ$"}
    body, curves = [], []
    for sh in ["w132_i53", "w198_i53", "w264_i53", "w264_i70"]:
        sel = [r for r in fair if r["shell"] == sh]
        mt = {t: st.median(float(r[f"recovered_gnn_tau{t}"]) for r in sel) for t in TAUS}
        me = {e: st.median(float(r[f"recovered_ecmp_eps{e}"]) for r in sel) for e in EPSS}
        bt, be = max(TAUS, key=lambda t: mt[t]), max(EPSS, key=lambda e: me[e])
        w = sum(1 for r in sel if float(r[f"recovered_gnn_tau{bt}"])
                > float(r[f"recovered_ecmp_eps{be}"]))
        gap = st.median(float(r["gap_fair"]) for r in sel)
        pv = sign_test_p(w, len(sel))
        ps = f"{pv:.3f}" if pv >= 0.001 else "<0.001"
        body.append(f"{NICE[sh]} & {mt['0.2']:.3f} & {mt[bt]:.3f} & {float(bt):g} & "
                    f"{me[be]:.3f} & {float(be):g} & ${gap:+.3f}$ & {w}/{len(sel)} & ${ps}$ \\\\")
        curves.append("\\addplot coordinates {"
                      + " ".join(f"({float(t):g},{mt[t]:.4f})" for t in TAUS)
                      + "};\n\\addlegendentry{" + NICE[sh] + "}")
    open(os.path.join(PAPER, "tab-fair.tex"), "w").write(
        "% SINH TU make_claims.py -- DUNG SUA TAY\n"
        "\\begin{table}[t]\n\\centering\\small\n"
        "\\caption{Learned price field against blind multipath spreading, both tuned "
        "per shell over fixed grids, eight instances each. Recovered fraction of the "
        "blind-to-equilibrium gap. The gap column is the median of the per-instance difference, "
        "not the difference of the medians. $\\tau$ is the decoder temperature and "
        "$\\varepsilon$ the path-cost tolerance. The $p$ column is a two-sided sign test on the win count: with eight instances, $8/8$ is evidence and $6/8$ is not, and printing the ratio alone invites the reader to treat them alike.}\n"
        "\\label{tab:fair}\n\\begin{tabular}{@{}lrrrrrrrr@{}}\n\\toprule\n"
        "shell & \\multicolumn{3}{c}{learned} & \\multicolumn{2}{c}{blind} & gap & wins & $p$ \\\\\n"
        "\\cmidrule(lr){2-4}\\cmidrule(lr){5-6}\n"
        " & $\\tau{=}0.2$ & best & $\\tau^\\star$ & best & $\\varepsilon^\\star$ & & & \\\\\n"
        "\\midrule\n" + "\n".join(body) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

    # ⛔ KHONG ghi fig-tau.tex nua (27/08/2026). Ban pgfplots o day va ban PDF do
    # make_r5_figs.py ve tren stylesheet nha cung tro toi paper/fig-tau.tex, nen ban nao
    # chay SAU se de len ban kia. Hau qua da xay ra: ban sach va ban danh dau cua cung mot
    # lan nop hien hai hinh khac nhau, tuy thu tu chay. Mot duong dan phai co DUNG MOT
    # nguoi ghi. Hinh ket qua thuoc ve make_r5_figs.py; tep nay chi lo claim va bang.
    print("  + tab-feasibility.tex, tab-fair.tex  (fig-tau.tex: xem make_r5_figs.py)")


def fit_to_column(*files):
    """Dat CUNG mot co chu va cung mat do cot cho moi bang sinh ra.

    Ban truoc boc \\resizebox{\\columnwidth} cho ca ba. Chung deu vua khung, nhung resizebox co
    MOI BANG MOT TI LE khac nhau tuy so cot, nen Bang IX va Bang X nam sat nhau tren cung mot trang
    ma chu to nho khac han. Vua khung khong phai la dong bo.

    Cach dung: khong co anh, ma dat \\scriptsize va thu hep \\tabcolsep cho tat ca. Moi bang khi
    do render o dung mot co, va be rong duoc dieu chinh bang mat do cot chu khong bang phep co.
    """
    for f in files:
        q = os.path.join(PAPER, f)
        t = io.open(q, encoding="utf-8").read()
        t = t.replace("\\resizebox{\\columnwidth}{!}{%\n", "").replace("\\end{tabular}}", "\\end{tabular}")
        if "\\tabcolsep" not in t:
            t = t.replace("\\centering\\small",
                          "\\centering\\scriptsize\\setlength{\\tabcolsep}{3.4pt}")
        io.open(q, "w", encoding="utf-8").write(t)
        print(f"  + dong bo co chu: {f}")


def main():
    BANDS = [("le1x", 0, 1.0), ("1to2x", 1.0, 2.0), ("2to4x", 2.0, 4.0), ("gt4x", 4.0, 1e9)]
    feas = add_band("r3_2_feasibility.csv", "blind_maxutil", BANDS)
    loss = add_band("r3_2_loss_models.csv", "blind_maxutil", BANDS)
    matched, sweep, mix, pro = (load("r2_7_matched_all.csv"), load("r2_7_eps_sweep.csv"),
                                load("r2_7_train_mix.csv"), load("r2_7_proactive_vs_ecmp.csv"))

    F = {"load_band": "gt4x"}
    claim("bpr_gain_overload", feas, "r3_2_feasibility.csv", "gain_bpr_pct", F,
          "khoang cach do bang do tre BPR, thuoc do CU", places=1)
    claim("goodput_gain_overload", feas, "r3_2_feasibility.csv", "gain_goodput_pct", F,
          "cung cau hinh, ep kha thi theo dung luong", places=1)
    for m in ("product", "bottleneck", "maxmin"):
        claim(f"goodput_gain_{m}", loss, "r3_2_loss_models.csv", f"gain_{m}_pct", F,
              f"mo hinh mat mat '{m}'", places=1)

    RIVALS = ("cold_T2", "warm_T1", "warm_T2", "ecmp05", "ecmp20")
    for shell in ("w132", "w264"):
        f = {"shell": shell}
        claim(f"recovered_gnn_{shell}", matched, "r2_7_matched_all.csv", "recovered_gnn", f,
              f"GNN tren vo {shell}")
        best = max(RIVALS, key=lambda k: st.median(
            float(r[f"recovered_{k}"]) for r in matched if r["shell"] == shell))
        claim(f"recovered_best_rival_{shell}", matched, "r2_7_matched_all.csv",
              f"recovered_{best}", f, f"doi thu manh nhat tren {shell}: {best}")

    EPSS = [k.split("recovered_ecmp_")[1] for k in sweep[0] if k.startswith("recovered_ecmp_")]
    for shell in sorted({r["shell"] for r in sweep}):
        f = {"shell": shell}
        claim(f"sweep_gnn_{shell}", sweep, "r2_7_eps_sweep.csv", "recovered_gnn", f,
              "GNN, huan luyen tren vo 132")
        be = max(EPSS, key=lambda e: st.median(
            float(r[f"recovered_ecmp_{e}"]) for r in sweep if r["shell"] == shell))
        claim(f"sweep_ecmp_{shell}", sweep, "r2_7_eps_sweep.csv", f"recovered_ecmp_{be}", f,
              f"eps-ECMP tot nhat tren vo nay: eps={be}")

    for shell in sorted({r["shell"] for r in mix}):
        for arm in ("single", "mix"):
            claim(f"mix_{arm}_{shell}", mix, "r2_7_train_mix.csv", f"recovered_{arm}",
                  {"shell": shell}, f"nhanh {arm}, cung ngan sach 12 thuc the")

    PE = [k.split("recovered_")[1] for k in pro[0] if k.startswith("recovered_ecmp")]
    for shell in ("w132", "w264"):
        f = {"shell": shell, "drift": "1.5"}
        claim(f"proact_{shell}_drift15", pro, "r2_7_proactive_vs_ecmp.csv", "recovered_proact",
              f, "dinh tuyen chu dong, muc troi lon nhat")
        be = max(PE, key=lambda e: st.median(
            float(r[f"recovered_{e}"]) for r in pro
            if r["shell"] == shell and r["drift"] == "1.5"))
        claim(f"proact_ecmp_{shell}_drift15", pro, "r2_7_proactive_vs_ecmp.csv",
              f"recovered_{be}", f, f"trai tai mu tot nhat cung canh: {be}")

    # --- so cong bang: CA HAI ben chinh theo tung vo, 8 don vi/vo ---
    # HIEU va KHOANG la dai luong DAN XUAT. verify_numbers tinh tren MOT cot voi mot phep
    # tong hop, nen no khong dien ta duoc "trung vi(A) tru trung vi(B)". Thay vi de mach truy
    # so dut o day, ghi hieu tung dong nguoc vao CSV: no thanh mot cot binh thuong, cong tu
    # tinh lai duoc, va nguoi mo CSV thay ngay hieu duoc lay theo tung don vi chu khong phai
    # tru hai con so da tong hop.
    fair = add_fair_deltas("r2_7_fair_tuned_wide.csv")
    TAUS = sorted({k.split("tau")[1] for k in fair[0] if "recovered_gnn_tau" in k},
                  key=float)
    EPSS = sorted({k.split("eps")[1] for k in fair[0] if "recovered_ecmp_eps" in k}, key=float)
    for shell in sorted({r["shell"] for r in fair}):
        f = {"shell": shell}
        sel = [r for r in fair if r["shell"] == shell]
        bt = max(TAUS, key=lambda t: st.median(float(r[f"recovered_gnn_tau{t}"]) for r in sel))
        be = max(EPSS, key=lambda e: st.median(float(r[f"recovered_ecmp_eps{e}"]) for r in sel))
        claim(f"fair_gnn_{shell}", fair, "r2_7_fair_tuned_wide.csv", f"recovered_gnn_tau{bt}", f,
              f"GNN o nhiet do tot nhat cho vo nay: tau={bt}")
        claim(f"fair_ecmp_{shell}", fair, "r2_7_fair_tuned_wide.csv", f"recovered_ecmp_eps{be}", f,
              f"eps-ECMP o dung sai tot nhat cho vo nay: eps={be}")
        claim(f"fair_gnn_fixedtau_{shell}", fair, "r2_7_fair_tuned_wide.csv",
              "recovered_gnn_tau0.2", f, "GNN o tau=0.2 co dinh trong ban thao")

    for shell in sorted({r["shell"] for r in fair}):
        f = {"shell": shell}
        claim(f"gap_fair_{shell}", fair, "r2_7_fair_tuned_wide.csv", "gap_fair", f,
              "hieu theo tung don vi: GNN(tau tot) - ECMP(eps tot)")
        claim(f"cost_fixed_tau_{shell}", fair, "r2_7_fair_tuned_wide.csv", "cost_of_fixed_tau", f,
              "gia phai tra vi giu tau=0.2 thay vi tau tot nhat cho vo nay")

    claim_inherited()
    claim_r4()

    os.makedirs(PAPER, exist_ok=True)
    json.dump(C, open(OUT_JSON, "w"), indent=2, ensure_ascii=False)
    emit_macros()
    g = lambda cid: next(c["paper_value"] for c in C if c["id"] == cid)
    open(OUT_TEX, "w").write(r"""% SINH TU code/experiments/make_claims.py -- DUNG SUA TAY.
\begin{table}[t]
\centering\small
\caption{Every headline number in this study and where it is derived. Recovered fraction is
$(\mathrm{blind}-\mathrm{policy})/(\mathrm{blind}-\mathrm{UE})$; the unit of analysis is
(shell, seed, slot) throughout, and every value is the median over those units. Blocks come from
different experiments and are labelled with their run set: entries for the same shell and the same
$\tau$ therefore differ between blocks, and Section~\ref{sec:pooled} pools them rather than
picking one. Read down a block, not across blocks.}
\label{tab:summary}
\begin{tabular}{@{}llr@{}}
\toprule
question & quantity & value \\
\midrule
\multicolumn{3}{@{}l}{\emph{Does the headline survive capacity feasibility?}}\\
& gap under BPR delay, offered load $>4\times$ & """ + g("bpr_gain_overload") + r"""\% \\
& gap in delivered rate, same rows & """ + g("goodput_gain_overload") + r"""\% \\
& \quad bottleneck loss instead of compounding & """ + g("goodput_gain_bottleneck") + r"""\% \\
& \quad max-min fair sharing & """ + g("goodput_gain_maxmin") + r"""\% \\
\midrule
\multicolumn{3}{@{}l}{\emph{Does it beat a blind baseline at matched budget?}}\\
\multicolumn{3}{@{}l}{\quad\scriptsize\itshape both sides tuned per shell (Table~\ref{tab:fair}); run set \texttt{r2\_7\_fair\_tuned\_wide}}\\
& learned / blind, training shell & """ + g("fair_gnn_w132_i53") + " / " + g("fair_ecmp_w132_i53") + r""" \\
& learned / blind, unseen 264 & """ + g("fair_gnn_w264_i53") + " / " + g("fair_ecmp_w264_i53") + r""" \\
\multicolumn{3}{@{}l}{\quad\scriptsize\itshape at the fixed decoder setting $\tau=0.2$; same run set}\\
& learned / blind, unseen 264 & """ + g("fair_gnn_fixedtau_w264_i53") + " / " + g("fair_ecmp_w264_i53") + r""" \\
\midrule
\multicolumn{3}{@{}l}{\emph{How far does it transfer, at the fixed $\tau=0.2$?}}\\
\multicolumn{3}{@{}l}{\quad\scriptsize\itshape a DIFFERENT run set (\texttt{r2\_7\_eps\_sweep}); see Section~\ref{sec:pooled}}\\
& GNN / blind multipath, 132 sat (trained) & """ + g("sweep_gnn_w132_i53") + " / " + g("sweep_ecmp_w132_i53") + r""" \\
& GNN / blind multipath, 198 sat & """ + g("sweep_gnn_w198_i53") + " / " + g("sweep_ecmp_w198_i53") + r""" \\
& GNN / blind multipath, 264 sat & """ + g("sweep_gnn_w264_i53") + " / " + g("sweep_ecmp_w264_i53") + r""" \\
& GNN / blind multipath, 396 sat & """ + g("sweep_gnn_w396_i53") + " / " + g("sweep_ecmp_w396_i53") + r""" \\
& GNN / blind multipath, 264 sat at $70^\circ$ & """ + g("sweep_gnn_w264_i70") + " / " + g("sweep_ecmp_w264_i70") + r""" \\
\midrule
\multicolumn{3}{@{}l}{\emph{Does diverse training restore it? (same instance budget)}}\\
& single-shell training, unseen 264 & """ + g("mix_single_w264_i53") + r""" \\
& mixed training, unseen 264 & """ + g("mix_mix_w264_i53") + r""" \\
\midrule
\multicolumn{3}{@{}l}{\emph{Does proactivity reach an axis blind multipath cannot?}}\\
& proactive / blind multipath, trained shell & """ + g("proact_w132_drift15") + " / " + g("proact_ecmp_w132_drift15") + r""" \\
& proactive / blind multipath, unseen shell & """ + g("proact_w264_drift15") + " / " + g("proact_ecmp_w264_drift15") + r""" \\
\bottomrule
\end{tabular}
\end{table}
""")
    print(f"\n# {len(C)} claim -> paper/claims.json")
    print(f"# bang tom tat -> paper/tab-summary.tex")
    emit_tables_and_figure()
    fit_to_column('tab-summary.tex', 'tab-feasibility.tex', 'tab-fair.tex')
    return 0


if __name__ == "__main__":
    sys.exit(main())
