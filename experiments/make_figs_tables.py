"""Sinh SAU BANG va BA HINH con lai tu CSV. Chay sau make_claims.py.

⛔ VI SAO CO TEP NAY. Kiem ke 27/08: bai co 14 bang/hinh, chi 5 duoc sinh ra tu du lieu
(`claims-macros.tex`, `fig-tau.tex`, `tab-fair.tex`, `tab-feasibility.tex`,
`tab-summary.tex`). CHIN cai con lai go tay thang trong `main.tex`: sau bang va ba hinh
voi tong 55 toa do.

Hau qua cu the: `fig:speedup` go cung `(132,21.8)(264,21.2)(1584,29.1)`. Do DUNG ba con
so nguoi doc ngoai dang bac (*"the 22x we report on the 132-shell becomes roughly 9x ...
the 21x on the 264-shell becomes roughly 2x"*, va *"the warm start was still not run on
1584, where the 29x is claimed"*). Chay lai thi nghiem ma khong dung toi hinh thi hinh
van ve ba con so do, canh mot doan van noi so khac. Do la mau thuan noi tai, va no se do
CHINH vong sua nay tao ra.

Nguyen tac: `main.tex` chi duoc chua `\\input`; moi con so o trong tep sinh ra.
`check_no_hardcoded.py` la cong chan chieu nguoc lai.

    python experiments/make_figs_tables.py
"""
import csv
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results")
PAPER = os.path.abspath(os.path.join(ROOT, "..", "paper"))

HDR = ("%% SINH TU make_figs_tables.py -- DUNG SUA TAY.\n"
       "%% Sua o day se bi ghi de o lan chay ke tiep; sua trong script hoac trong CSV.\n")


# ⛔ Chu thich va lenh dinh dang boc NGUYEN VAN tu ban goc. Viet lai ngan hon
# lam mat doan "Run set" cua tab:decode (noi dung, khong phai trinh bay) va lam
# tab:baselines mat \\footnotesize nen tran 17,7pt.
CAP_BASELINES = r"""\caption{Total travel time relative to blind (lower is better; blind $=1.00$), mean over $n{=}9$ instance-seed units per split. SO and UE are references; the rest are deployable. Bold marks the best deployable policy in each row, and it changes: the learned field in distribution, the one-pass blind multipath split out of it.}"""
PRE_BASELINES = r"""\setlength{\tabcolsep}{3pt}\footnotesize"""
CAP_DECODE = r"""\caption{Decoder comparison: TTT relative to blind and recovered fraction of the
blind-to-UE gain, mean $\pm$ std over $n{=}9$ units per split. The multipath decode \eqref{eq:split} closes most of the single-path
decoding gap. \emph{Run set:} this table is computed from its own independent set of seeds. Pooling every unit we have measured for the $264$-shell at $\tau=0.2$, across all three run sets, gives a median of $0.908$ spanning $0.863$ to $0.928$; the entries here and in the other tables are points inside that range, not corrections of one another (Section~\ref{sec:pooled}).}"""


def rd(n):
    with open(os.path.join(RES, n)) as f:
        return list(csv.DictReader(f))


def num(rows, col, flt=None):
    if flt:
        rows = [r for r in rows if all(r.get(k) == v for k, v in flt.items())]
    return [float(r[col]) for r in rows if r.get(col) not in (None, "", "nan")]


def w(name, body):
    p = os.path.join(PAPER, name)
    open(p, "w").write(HDR + body.rstrip() + "\n")
    return name


CAP_ABLATION = r"""\caption{Operator ablation: recovered fraction of the blind-to-UE gain (mean $\pm$ std,
$n{=}12$). The plain GCN is best out of distribution; the global quantum-walk operator
does not help and is the most variable. \emph{Run set:} this table is computed from its own independent set of seeds. Pooling every unit we have measured for the $264$-shell at $\tau=0.2$, across all three run sets, gives a median of $0.908$ spanning $0.863$ to $0.928$; the entries here and in the other tables are points inside that range, not corrections of one another (Section~\ref{sec:pooled}).}"""
PRE_ABLATION = r""""""
CAP_COST = r"""\caption{Per-slot routing cost in all-or-nothing ($\AoN$) shortest-path passes ($T$ is
the MSA iteration count, $\approx 20$). The GNN adds one forward to two passes; UE/SO
need $T$ passes.}"""
PRE_COST = r""""""


# ---------------------------------------------------------------- tab:ablation
def tab_ablation():
    """Toan tu: GCN cuc bo / Heat khuech tan / QW buoc di luong tu.

    Doi chieu 27/08: bo sinh nay tai tao DUNG ca sau o dang in, nen bang nay KHONG cu.
    """
    r = rd("p5_ablation.csv")
    NICE = {"GCN": r"\textbf{GCN (local)}", "Heat": "Heat (global diffusion)",
            "QW": "QW (global quantum walk)"}
    SPLITS = ["in-dist", "ood-largeshell"]
    # ⛔ In dam chi khi khac biet CON GIU DUOC sau khi lam tron. GCN 0.9686 va Heat
    # 0.9678 deu ra 0.97; in dam mot trong hai la noi qua, va ban goc khong in dam cot do.
    best = {}
    for sp in SPLITS:
        mv = {k: st.mean(num(r, "recovered", {"prop": k, "split": sp})) for k in NICE}
        top = max(mv, key=mv.get)
        best[sp] = None if [k for k in mv if k != top and round(mv[k], 2) == round(mv[top], 2)] else top
    out = []
    for k in ("GCN", "Heat", "QW"):
        cells = []
        for sp in SPLITS:
            v = num(r, "recovered", {"prop": k, "split": sp})
            sd = ("%.2f" % st.stdev(v)).lstrip("0")
            body = r"%.2f{\scriptstyle\pm%s}" % (st.mean(v), sd)
            cells.append(r"$\mathbf{%s}$" % body if k == best[sp] else r"$%s$" % body)
        out.append("    " + NICE[k] + " & " + " & ".join(cells) + r" \\")
    return w("tab-ablation.tex",
             "\\begin{table}[t]\n  \\centering\\footnotesize\\setlength{\\tabcolsep}{3pt}\n  "
             + CAP_ABLATION + "\n  \\label{tab:ablation}\n  " + PRE_ABLATION
             + "\n  \\begin{tabular}{lcc}\n    \\toprule\n"
             + "    operator & in-distribution & OOD ($264$) \\\\\n    \\midrule\n"
             + "\n".join(out)
             + "\n    \\bottomrule\n  \\end{tabular}\n\\end{table}")


# -------------------------------------------------------------------- tab:cost
def tab_cost():
    """Chi phi moi khe theo so luot AoN.

    Cot trai la CAU TRUC (bao nhieu luot AoN), khong phai so do. Nhung hai gia tri T
    thi LA so do: bai in "T ~ 20" va "T ~ 2--6" go tay, trong khi CSV cho lanh 9-40
    (trung vi 20) va am 1-11 (trung vi 4). Dai thuc rong hon dai da in, nen in ca dai.
    """
    r = rd("r4_2_warmstart_iters.csv")
    cold = [int(x["iters_cold"]) for x in r]
    warm = [int(x["iters_warm"]) for x in r]
    tc, tw = int(round(st.median(cold))), int(round(st.median(warm)))
    rows = [
        r"    blind, geographic & $1$ \\",
        r"    blind multipath ($\varepsilon$-tolerant) & $1$ \\",
        r"    one-step correction & $2$ \\",
        r"    \textbf{GNN (ours)} & $2 + \text{1 forward}$ \\",
        r"    UE, SO (MSA), cold start & $T\approx %d$ (range $%d$--$%d$) \\" % (tc, min(cold), max(cold)),
        r"    UE, SO (MSA), warm start (Section~\ref{sec:warmstart}) & $T\approx %d$ (range $%d$--$%d$) \\" % (tw, min(warm), max(warm)),
    ]
    cap = CAP_COST.replace(r"$\approx 20$", r"$\approx %d$" % tc)
    return w("tab-cost.tex",
             "\\begin{table}[t]\n  \\centering\\footnotesize\\setlength{\\tabcolsep}{3pt}\n  "
             + cap + "\n  \\label{tab:cost}\n  " + PRE_COST
             + "\n  \\begin{tabular}{lc}\n    \\toprule\n"
             + "    policy & cost (\\AoN{} passes) \\\\\n    \\midrule\n"
             + "\n".join(rows)
             + "\n    \\bottomrule\n  \\end{tabular}\n\\end{table}")


CAP_SCALE_OLD = r"""\caption{Inductive transfer (train on $132$) and inference cost. Recovered fraction of
the blind-to-UE gain (mean $\pm$ std), and one-shot GNN routing versus the MSA solve. All rows use the fixed decoder temperature $\tau=0.2$; Section~\ref{sec:two-causes} shows this setting is near-optimal only on the training shell and depresses every transfer number here. \emph{Run set:} this table is computed from its own independent set of seeds. Pooling every unit we have measured for the $264$-shell at $\tau=0.2$, across all three run sets, gives a median of $0.908$ spanning $0.863$ to $0.928$; the entries here and in the other tables are points inside that range, not corrections of one another (Section~\ref{sec:pooled}). $^{\dagger}$Measured at the fixed $\tau=0.2$ and without the blind multipath comparator. Section~\ref{sec:s1584} supplies both on this shell: a temperature sweep raises the learned field to $0.980$, the blind split reaches $0.994$, and the equilibrium reference itself has not converged at this scale.}"""
PRE_SCALE = r""""""


# ------------------------------------------------------------------- tab:scale
def tab_scale():
    """Chuyen giao quy nap va chi phi suy dien -- viet lai cho trung thuc.

    Ba cot cu co ba so phan khac nhau:

    `recovered`  : giu o vo 132/264 (loi giai can bang HOI TU o do). RUT o vo 1584 vi
                   PoA = 0.9844 sau 320 vong va khoang cach toi 1 chi co he so ~0.55 moi
                   lan gap doi ⇒ khong co mau so dang tin. Thay bang ti so so voi BLIND,
                   do truc tiep, khong can UE.
    `GNN (s)`    : so cu 0.05/0.23/8.4 boc tu LOG CUA MAY KHAC. Do lai tren VPS ra
                   0.10/0.50/16.3, dung GAP DOI tren ca ba vo. Dung so do tren may nay.
    `speedup vs UE`: BO HAN. (a) o 1584 mau so khong ton tai; (b) o 132/264 mau so la UE
                   KHOI DONG LANH trong khi chinh bai chung minh am chi can 1-11 vong so
                   voi 9-40; (c) so cu tron hai may. Thay bang **phan cua mot khe 60 s**,
                   do duoc va co nghia van hanh.
    """
    r = rd("p5_router.csv")
    t = rd("r4_4_stage_timing.csv")
    u = rd("r5_4_shell1584_uefree.csv")
    slot = float(t[0]["slot_s"])

    def tim(ns):
        return st.mean(num(t, "t_total_s", {"n_sat": ns}))

    def rec(split):
        v = num(r, "recovered", {"split": split})
        return st.mean(v), st.stdev(v)

    rows = []
    for lab, ns, split in (("in-dist", "132", "in-dist"), ("OOD", "264", "ood-largeshell")):
        m, s = rec(split)
        rows.append(r"    %s & $%s$ & $%.2f{\scriptstyle\pm%s}$ & $%.2f$ & $%.1f\%%$ \\"
                    % (lab, ns, m, ("%.2f" % s).lstrip("0"), tim(ns), 100 * tim(ns) / slot))
    g = st.median(num(u, "rel_best_gnn"))
    e = st.median(num(u, "rel_best_ecmp"))
    t1584 = tim("1584")
    rows.append(r"    OOD & $1584$ & \multicolumn{1}{c}{--$^{\dagger}$} & $%.1f$ & $%.1f\%%$ \\"
                % (t1584, 100 * t1584 / slot))
    cap = (r"\caption{Inductive transfer (train on $132$) and inference cost, all measured "
           r"on one machine in a single run. Recovered fraction of the blind-to-UE gain "
           r"(mean $\pm$ std) and one-shot GNN routing time as a share of the $%.0f$~s slot. "
           r"$^{\dagger}$At $1584$ the equilibrium reference does not converge "
           r"(Section~\ref{sec:s1584}: the price of anarchy stays below one through $320$ "
           r"MSA iterations), so no recovered fraction is reported there; measured against "
           r"blind instead, the learned field reaches $%.4f$ and the blind multipath split "
           r"$%.4f$, and the blind split wins on every seed. We no longer report a speedup "
           r"against the equilibrium solve: at $1584$ that denominator does not exist, and "
           r"at the smaller shells it would be taken against a cold-started solver that "
           r"Section~\ref{sec:warmstart} shows needs only $1$--$11$ iterations when warm "
           r"started.}" % (slot, g, e))
    return w("tab-scale.tex",
             "\\begin{table}[t]\n  \\centering\\footnotesize\\setlength{\\tabcolsep}{3pt}\n  "
             + cap + "\n  \\label{tab:scale}\n  " + PRE_SCALE
             + "\n  \\begin{tabular}{llccc}\n    \\toprule\n"
             + "    shell & sats & recovered & GNN (s) & share of slot \\\\\n    \\midrule\n"
             + "\n".join(rows)
             + "\n    \\bottomrule\n  \\end{tabular}\n\\end{table}")


# --------------------------------------------------------------------- tab:msa
def tab_msa():
    """Thang hoi tu MSA theo QUY MO -- bang MOI cua vong sua 27/08.

    Tra loi thang diem cua nguoi doc ngoai: *"the 1584 equilibrium reference is known
    non-convergent yet uncorrected values remain published"*. Bang nay cho thay ba dieu
    ma mot cau van khong cho thay duoc: vo 132 dat PoA>1 tu 20 vong, vo 264 tu 40, con
    vo 1584 khong dat o bat ky nac nao thu duoc.
    """
    small = rd("r5_3_convergence_small.csv")
    big = rd("r5_0_msa_ladder_1584.csv")
    iters = sorted({int(x["iters"]) for x in small} | {int(x["iters"]) for x in big})
    shells = [("$132$", "w132_i53", small), ("$264$", "w264_i53", small),
              ("$1584$", "w1584_i53", big)]
    out = []
    for lab, key, src in shells:
        cells = []
        for it in iters:
            v = [float(x["poa"]) for x in src
                 if x["shell"] == key and int(x["iters"]) == it]
            if not v:
                cells.append("--")
            else:
                m = st.median(v)
                # in dam nac DAU TIEN thoa rang buoc vat ly PoA >= 1
                first_ok = all(
                    st.median([float(y["poa"]) for y in src
                               if y["shell"] == key and int(y["iters"]) == j] or [0]) < 1.0
                    for j in iters if j < it) and m >= 1.0
                cells.append((r"$\mathbf{%.4f}$" if first_ok else r"$%.4f$") % m)
        out.append("    %s & %s \\\\" % (lab, " & ".join(cells)))
    # ⛔ Hinh "mau so troi" ve CUNG du lieu nay o dang khac. Gop no vao day thanh mot
    # dong thay vi giu mot float rieng: bai dang 16 trang va do la trung lap tu tao ra.
    bl = []
    for it in iters:
        v = [float(x["blind_over_ue"]) for x in big if int(x["iters"]) == it]
        bl.append(("$%.0f$" % st.median(v)) if v else "--")
    out.append(r"    \midrule" + "\n    blind/UE, $1584$ & "
               + " & ".join(bl) + r" \\")
    return w("tab-msa.tex",
             "\\begin{table}[t]\n  \\centering\\footnotesize\\setlength{\\tabcolsep}{3pt}\n"
             "  \\caption{Price of anarchy $\\mathrm{TTT}_{\\mathrm{UE}}/\\mathrm{TTT}_{\\mathrm{SO}}$ "
             "against MSA iteration count, median over seeds. Values below one are "
             "impossible and mark a solve that has not converged; bold is the first "
             "iteration count at which a shell satisfies the constraint. The $1584$-shell "
             "never does: the gap to one shrinks by about $0.55$ per doubling, so the "
             "extrapolated requirement exceeds $2500$ iterations. The last row shows why no "
             "ratio is reported on that shell: its denominator moves by $63\\%$ across the "
             "ladder and has not settled.}\n"
             "  \\label{tab:msa}\n  \\begin{tabular}{l" + "c" * len(iters) + "}\n"
             "    \\toprule\n    shell & " + " & ".join("$%d$" % i for i in iters)
             + " \\\\\n    \\midrule\n" + "\n".join(out)
             + "\n    \\bottomrule\n  \\end{tabular}\n\\end{table}")


# ---------------------------------------------------------------- tab:baselines
def tab_baselines():
    r = rd("p6_baselines.csv")
    out = []
    for split, lab in (("in-dist", "in-distribution"), ("ood", "OOD ($264$)")):
        s = [x for x in r if x["split"] == split]
        if not s:
            continue
        # ⛔ Dung cot ti so TUNG DON VI (r_*) roi lay TRUNG BINH, dung nhu chu thich
        # bang tuyen bo. Ban go tay co MOT o lech quy uoc: nam o dung trung binh, rieng
        # o GNN dung TRUNG VI (0.1137 -> 0.11 thay vi 0.1203 -> 0.12), va do la o cua
        # chinh phuong phap de xuat. Bo sinh khong duoc phep co ngoai le nhu vay.
        cell = lambda c: st.mean(num(s, c))
        vals = {"so": cell("r_so"), "ue": cell("r_ue"), "geo": cell("r_geo"),
                "one": cell("r_1step"), "ecmp": cell("r_ecmp"), "gnn": cell("r_gnn")}
        # in dam CHINH SACH TRIEN KHAI DUOC tot nhat; SO/UE la moc quy chieu, khong tinh
        best = min(("geo", "one", "ecmp", "gnn"), key=lambda k: vals[k])
        f = lambda k: (r"$\mathbf{%.2f}$" if k == best else r"$%.2f$") % vals[k]
        out.append("    %s & $%.2f$ & $%.2f$ & %s & %s & %s & %s \\\\"
                   % (lab, vals["so"], vals["ue"], f("geo"), f("one"), f("ecmp"), f("gnn")))
    return w("tab-baselines.tex", r"""\begin{table}[t]
  \centering
  """ + CAP_BASELINES + r"""
  \label{tab:baselines}
  """ + PRE_BASELINES + r"""
  \begin{tabular}{lcccccc}
    \toprule
    split & SO & UE & geographic & one-step & blind mp & \textbf{GNN} \\
    \midrule
""" + "\n".join(out) + r"""
    \bottomrule
  \end{tabular}
\end{table}""")


# ------------------------------------------------------------------ tab:decode
def tab_decode():
    r = rd("p8_decoder.csv")
    out = []
    for split, lab in (("in-dist", "in-dist (TTT/blind)"), ("ood", "OOD ($264$, TTT/blind)")):
        s = [x for x in r if x["split"] == split]
        if not s:
            continue
        sp, mp, ue = num(s, "r_gnn_sp"), num(s, "r_gnn_mp"), num(s, "r_ue")
        m = lambda v: (st.mean(v), st.stdev(v))
        (a, sa), (b, sb) = m(sp), m(mp)
        out.append(r"    %s & $%.2f{\scriptstyle\pm%s}$ & $\mathbf{%.2f{\scriptstyle\pm%s}}$ & $%.2f$ \\"
                   % (lab, a, ("%.2f" % sa).lstrip("0"), b, ("%.2f" % sb).lstrip("0"),
                      st.mean(ue)))
        # phan thu hoi: (blind - x) / (blind - ue), blind = 1 theo dinh nghia cot
        rec = lambda v: [(1 - x) / (1 - u) for x, u in zip(v, ue)]
        (ra, rsa), (rb, rsb) = m(rec(sp)), m(rec(mp))
        out.append(r"    \quad recovered & $%.2f{\scriptstyle\pm%s}$ & $\mathbf{%.2f{\scriptstyle\pm%s}}$ & -- \\"
                   % (ra, ("%.2f" % rsa).lstrip("0"), rb, ("%.2f" % rsb).lstrip("0")))
    return w("tab-decode.tex", r"""\begin{table}[t]
  \centering\footnotesize\setlength{\tabcolsep}{3pt}
  """ + CAP_DECODE + r"""
  \label{tab:decode}
  \begin{tabular}{lccc}
    \toprule
    & single-path & multipath & UE \\
    \midrule
""" + "\n".join(out) + r"""
    \bottomrule
  \end{tabular}
\end{table}""")


# ---------------------------------------------------------------- tab:headroom
def tab_headroom():
    # ⛔ Chu thich bang noi ro "on the $132$-shell", nen phai LOC theo vo do, khong gop
    # ca hai vo. Toi da gop nham o ban dau va ra so lech het; bat duoc vi doi chieu voi
    # ban dang in truoc khi thay. Vo 132 la vo mo hinh duoc HUAN LUYEN tren.
    SHELL = "starlink_mini132"
    r = [x for x in rd("p4_headroom.csv") if x["shell"] == SHELL]
    levels = sorted({int(x["pairs"]) for x in r})
    def row(col):
        return [st.mean(num(r, col, {"pairs": str(p)})) for p in levels]
    b, u = row("blind_ttt"), row("ue_ttt")
    f = lambda v: " & ".join("$%.1f$" % x for x in v)
    nice = ["$%d$" % p for p in levels]
    shells = levels
    return w("tab-headroom.tex", r"""\begin{table}[t]
  \centering\footnotesize\setlength{\tabcolsep}{3pt}
  \caption{Absolute travel time (arbitrary units) of blind versus UE on the $132$-shell
  as offered load grows, and their ratio. Mean over seeds.}
  \label{tab:headroom}
  \begin{tabular}{l%s}
    \toprule
    demands & %s \\
    \midrule
    blind & %s \\
    UE & %s \\
    ratio & %s \\
    \bottomrule
  \end{tabular}
\end{table}""" % ("c" * len(shells), " & ".join(nice), f(b), f(u),
                  " & ".join("$%.1f$" % (x / y) for x, y in zip(b, u))))


# ------------------------------------------------------------------- fig:bound
def fig_bound():
    r = sorted(rd("p9_bound.csv"), key=lambda x: float(x["rel_err"]))
    co = lambda c, s: " ".join("(%.4f,%.4f) +- (0,%.4f)"
                               % (float(x["rel_err"]), float(x[c]), float(x[s])) for x in r)
    floor = float(r[0]["gap_mp_pct"])
    return w("fig-bound.tex", r"""\begin{figure}[t]
  \centering
  \begin{tikzpicture}
  \begin{axis}[width=\columnwidth, height=4.4cm, xlabel={relative price error
      $\|\hat g - g^\star\|/\bar g$}, ylabel={gap to UE (\%%)},
      legend style={font=\scriptsize, at={(0.02,0.98)}, anchor=north west},
      tick label style={font=\scriptsize}, label style={font=\scriptsize},
      grid=both, grid style={line width=.1pt, draw=gray!20}]
  \addplot[cRed, smark, error bars/.cd, y dir=both, y explicit] coordinates {%s};
  \addlegendentry{single-path decode}
  \addplot[cNavy, pmark, error bars/.cd, y dir=both, y explicit] coordinates {%s};
  \addlegendentry{multipath decode}
  \node[font=\scriptsize, cNavy, anchor=south west] at (axis cs:0.0,%.1f)
    {$\delta_{\mathrm{dec}}\!\approx\!%.1f\%%$};
  \end{axis}
  \end{tikzpicture}
  \caption{Travel-time gap to UE against injected price error. The gap grows
  monotonically and flattens to a floor $\delta_{\mathrm{dec}}$ as the error vanishes,
  which is the \emph{shape} Proposition~\ref{prop:bound} predicts. It is not a
  validation of the bound: Section~\ref{sec:bound} shows the numerical bound is vacuous
  at every operating point measured here.}
  \label{fig:bound}
\end{figure}""" % (co("gap_sp_pct", "gap_sp_std"), co("gap_mp_pct", "gap_mp_std"),
                   floor + 0.4, floor))


# --------------------------------------------------------------- fig:proactive
def fig_proactive():
    r = rd("p7_proactive.csv")
    drifts = sorted({float(x["drift"]) for x in r})
    def at(d, col):
        # so bang SO THUC: CSV ghi "0.0" con "%g" % 0.0 cho "0", nen so chuoi khong khop
        return [float(x[col]) for x in r if abs(float(x["drift"]) - d) < 1e-9]
    def series(col):
        return " ".join("(%.2f,%.4f) +- (0,%.4f)"
                        % (d, st.mean(at(d, col)), st.stdev(at(d, col))) for d in drifts)
    return w("fig-proactive.tex", r"""\begin{figure}[t]
  \centering
  \begin{tikzpicture}
  \begin{axis}[width=\columnwidth, height=4.4cm, xlabel={hotspot drift},
      ylabel={TTT relative to blind}, legend style={font=\scriptsize,
      at={(0.02,0.98)}, anchor=north west}, tick label style={font=\scriptsize},
      label style={font=\scriptsize}, grid=both,
      grid style={line width=.1pt, draw=gray!20}]
  \addplot[name path=R, cRed, pmark, error bars/.cd, y dir=both, y explicit]
    coordinates {%s}; \addlegendentry{reactive}
  \addplot[name path=P, cNavy, smark, error bars/.cd, y dir=both, y explicit]
    coordinates {%s}; \addlegendentry{proactive}
  \addplot[cNavy!12, forget plot] fill between[of=R and P];
  \end{axis}
  \end{tikzpicture}
  \caption{Reactive versus proactive routing as the hotspot drifts within a slot.
  Shading marks the gap the forecast buys.}
  \label{fig:proactive}
\end{figure}""" % (series("r_react"), series("r_proact")))


# ----------------------------------------------------------------- fig:speedup
def fig_speedup():
    """Tang toc suy dien so voi loi giai MSA, theo co vo.

    ⛔ Ba con so cu (21.8, 21.2, 29.1) go cung trong main.tex la dung ba con so nguoi
    doc ngoai bac. Nay tinh tu r4_4_stage_timing.csv (thoi gian suy dien) chia cho thoi
    gian MSA doc tu cung tep neu co; thieu cot MSA thi KHONG doan, ma bao ra.
    """
    r = rd("r4_4_stage_timing.csv")
    cols = set(r[0])
    ref = next((c for c in ("t_msa_s", "t_ue_s", "ref_ttt_s", "msa_s") if c in cols), None)
    shells = []
    for x in r:
        if x["n_sat"] not in shells:
            shells.append(x["n_sat"])
    if ref is None:
        return w("fig-speedup.tex", r"""%% ⛔ CHUA SINH DUOC. r4_4_stage_timing.csv khong co cot thoi gian MSA,
%% nen khong tinh duoc he so tang toc ma khong doan. Chay lai phep do voi cot do,
%% hoac bo hinh nay. KHONG go tay toa do vao main.tex.
\begin{figure}[t]\centering
  \fbox{\parbox{0.9\columnwidth}{\footnotesize Figure pending: inference speedup
  requires an MSA reference time column in \texttt{r4\_4\_stage\_timing.csv}.}}
  \caption{Inference speedup over the equilibrium solve.}
  \label{fig:speedup}
\end{figure}""")
    pts = " ".join("(%s,%.1f)" % (s, st.mean(num(r, ref, {"n_sat": s}))
                                  / st.mean(num(r, "t_total_s", {"n_sat": s})))
                   for s in shells)
    return w("fig-speedup.tex", r"""\begin{figure}[t]
  \centering
  \begin{tikzpicture}
  \begin{axis}[width=\columnwidth, height=4.2cm, xmode=log, log basis x=2,
      xlabel={satellites}, ylabel={speedup over MSA ($\times$)},
      tick label style={font=\scriptsize}, label style={font=\scriptsize},
      grid=both, grid style={line width=.1pt, draw=gray!20}]
  \addplot[name path=A, cNavy, pmark] coordinates {%s};
  \end{axis}
  \end{tikzpicture}
  \caption{Inference cost against the equilibrium solve it replaces.}
  \label{fig:speedup}
\end{figure}""" % pts)


def main():
    made = []
    for fn in (tab_baselines, tab_decode, tab_headroom, tab_ablation, tab_cost, tab_scale, tab_msa,
               fig_bound, fig_proactive, fig_speedup):
        try:
            made.append(fn())
        except Exception as e:
            print("  ⛔ %-18s LOI: %s" % (fn.__name__, e))
    for n in made:
        print("  ✅ paper/%s" % n)
    print("  => sinh %d/10 hien vat" % len(made))
    return 0 if len(made) == 10 else 1


if __name__ == "__main__":
    sys.exit(main())
