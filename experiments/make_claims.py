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
    val = {"median": st.median, "mean": st.mean, "min": min, "max": max}[agg](vals)
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


def claim_r4():
    """Ket qua vong R4, sinh ra tu ban phan bien ngoai 17/08/2026."""
    # 2.2: so vong MSA can de hoi tu. Bang II cua bai ghi "T ~ 20" khong kem dieu kien,
    # va 20 dung la con so KHOI DONG LANH. Khoi dong am la doi thu that trong van hanh.
    for sh in ("w132", "w264"):
        for kind in ("cold", "warm"):
            claim_raw(f"msa_iters_{kind}_{sh}", "r4_2_warmstart_iters.csv", f"iters_{kind}",
                      {"shell": sh}, "median", 0,
                      f"so vong MSA de vao trong 0.5% TTT quy chieu, khoi dong {kind}, {sh}")

    # 3.5: proactive so voi blind tot nhat, GHEP CAP theo tung don vi, o TUNG muc troi.
    # 2.1a/2.1b: vo 1584, quet tau + baseline blind. Truoc do CA HAI deu vang mat o dung vo
    # cho con so headline, va bai tu neu luat "giu tau co dinh la dang do bo giai ma" o muc VI-I.
    r4 = list(csv.DictReader(open(os.path.join(RES, "r4_1_shell1584_controls.csv"))))
    for r in r4:
        r["gap_1584"] = round(float(r["recovered_gnn_tau8.0"]) - float(r["recovered_ecmp_eps0.2"]), 4)
    with open(os.path.join(RES, "r4_1_shell1584_controls.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(r4[0].keys())); w.writeheader(); w.writerows(r4)
    for cid, col in (("s1584_gnn_fixedtau", "recovered_gnn_tau0.2"),
                     ("s1584_gnn_besttau", "recovered_gnn_tau8.0"),
                     ("s1584_ecmp_best", "recovered_ecmp_eps0.2"),
                     ("s1584_gap", "gap_1584")):
        claim(cid, r4, "r4_1_shell1584_controls.csv", col, {"shell": "w1584_i53"},
              f"vo 1584: {col}")
    claim_raw("s1584_blind_over_ue", "r4_1_shell1584_controls.csv", "blind_over_ue",
              {"shell": "w1584_i53"}, "median", 0, "blind te hon can bang bao nhieu lan o 1584")
    claim_raw("s1584_ratio_fixedtau", "r4_1_shell1584_controls.csv", "ratio_ue_gnn_tau0.2",
              {"shell": "w1584_i53"}, "median", 1, "GNN o tau=0.2 cach can bang bao nhieu lan")
    claim_raw("s1584_ratio_besttau", "r4_1_shell1584_controls.csv", "ratio_ue_gnn_tau8.0",
              {"shell": "w1584_i53"}, "median", 1, "GNN o tau tot nhat cach can bang bao nhieu lan")

    # 4.2/4.3: hang so cua Menh de 1, dat bang so thay vi de o dang Theta().
    for sh in ("w132_i53", "w264_i53"):
        for cid, col, pl in ((f"bound_H_{sh}", "H_hops", 0),
                             (f"bound_c1H_ue_{sh}", "c1H_at_ue", 0),
                             (f"bound_c1H_blind_{sh}", "c1H_at_blind", 0),
                             (f"bound_propratio_{sh}", "prop_ratio", 2)):
            claim_raw(cid, "r4_3_bound_constants.csv", col, {"shell": sh}, "median", pl,
                      f"hang so Menh de 1: {col} tren {sh}")

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
    for who, col in (("gnn", "r_gnn"), ("ue", "r_ue"), ("so", "r_so"),
                     ("geo", "r_geo"), ("onestep", "r_1step")):
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

    open(os.path.join(PAPER, "fig-tau.tex"), "w").write(
        "% SINH TU make_claims.py -- DUNG SUA TAY\n"
        "\\begin{figure}[t]\n\\centering\n"
        # prostyle la kieu dung chung cua MOI hinh ket qua trong bai: font nhan, do day net,
        # mau luoi. Khong duoc bo qua no roi boc \resizebox, vi resizebox doi co chu theo mot
        # he so rieng nen hinh nay se khong cung co voi cac hinh con lai.
        "\\begin{tikzpicture}\n\\begin{axis}[prostyle,\n"
        "  xlabel={decoder temperature $\\tau$ (log scale)},\n"
        "  ylabel={recovered fraction},\n"
        "  xmode=log, log basis x=10, width=8.4cm, height=5.4cm,\n"
        "  legend pos=south east,\n"
        "  ymin=0.4, ymax=1.06, mark size=1.6pt]\n"
        + "\n".join(curves) + "\n"
        "\\draw[dashed,gray] (axis cs:0.2,0.4) -- (axis cs:0.2,1.02);\n"
        "\\node[font=\\scriptsize,gray!60!black,anchor=south west] at (axis cs:0.21,0.42)\n"
        "  {$\\tau{=}0.2$};\n"
        "\\end{axis}\n\\end{tikzpicture}\n"
        "\\caption{The decoder temperature is not a constant of the method. On the shell the model "
        "was trained on the curve peaks near $\\tau=0.1$ and falls away; on every larger or "
        "differently inclined shell it rises and then plateaus one to two orders of magnitude "
        "higher. The fixed value inherited from the training shell (dashed) sits far down the "
        "curve everywhere else, and the loss that causes was previously charged to the learned "
        "price field.}\n\\label{fig:tau}\n\\end{figure}\n")
    print("  + tab-feasibility.tex, tab-fair.tex, fig-tau.tex")


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
