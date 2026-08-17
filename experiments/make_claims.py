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

    os.makedirs(PAPER, exist_ok=True)
    json.dump(C, open(OUT_JSON, "w"), indent=2, ensure_ascii=False)
    g = lambda cid: next(c["paper_value"] for c in C if c["id"] == cid)
    open(OUT_TEX, "w").write(r"""% SINH TU code/experiments/make_claims.py -- DUNG SUA TAY.
\begin{table}[t]
\centering\small
\caption{Every headline number in this study and where it is derived. Recovered fraction is
$(\mathrm{blind}-\mathrm{policy})/(\mathrm{blind}-\mathrm{UE})$; the unit of analysis is
(shell, seed, slot) throughout, and every value is the median over those units.}
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
& GNN, training shell & """ + g("recovered_gnn_w132") + r""" \\
& strongest cheap rival, training shell & """ + g("recovered_best_rival_w132") + r""" \\
& GNN, unseen shell & """ + g("recovered_gnn_w264") + r""" \\
& strongest cheap rival, unseen shell & """ + g("recovered_best_rival_w264") + r""" \\
\midrule
\multicolumn{3}{@{}l}{\emph{How far does it transfer?}}\\
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
\multicolumn{3}{@{}l}{\emph{Does proactivity reach an axis blind spreading cannot?}}\\
& proactive / blind multipath, trained shell & """ + g("proact_w132_drift15") + " / " + g("proact_ecmp_w132_drift15") + r""" \\
& proactive / blind multipath, unseen shell & """ + g("proact_w264_drift15") + " / " + g("proact_ecmp_w264_drift15") + r""" \\
\bottomrule
\end{tabular}
\end{table}
""")
    print(f"\n# {len(C)} claim -> paper/claims.json")
    print(f"# bang tom tat -> paper/tab-summary.tex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
