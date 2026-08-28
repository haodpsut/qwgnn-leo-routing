"""Ba hinh MOI cua vong sua 27/08, ve theo chuan `transaction-figure-kit/results`.

Quy uoc bat buoc (xem `paper-lab/transaction-figure-kit/results/make_results.py`):
  - phan biet series bang MAU + MARKER + KIEU NET, doc duoc khi in den trang
  - bang mau Okabe-Ito an toan cho nguoi mu mau
  - phong serif khop than bai, co 9; truc manh 0.6pt; bo vien tren va phai
  - khong luoi ruc, khong chartjunk, khong 3D, khong bong
  - xuat PDF vector, nhung font Type-42

Ba hinh, moi hinh tra loi MOT diem cua nguoi doc ngoai:

  fig:msa     hoi tu MSA theo quy mo  -> "the 1584 equilibrium reference is known
              non-convergent yet uncorrected values remain published"
  fig:denom   mau so troi theo so vong -> cho thay vi sao moi ti so quy chieu ve can bang
              o vo 1584 khong dung duoc, thay vi chi noi bang chu
  fig:host    phan phoi lech giua hai may -> "cross-host variability remains unquantified
              despite exceeding reported differences"

    python experiments/make_r5_figs.py   ->  results/figures/*.pdf + *.png
"""
import csv
import glob
import os
import statistics as st
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results")
# ⛔ GHI THANG VAO paper/figures. Ban cu ghi vao code/results/figures va KHONG co buoc
# nao chep sang, nen bai dung mot bo hinh con bo sinh cap nhat mot bo khac. Do 27/08:
# ca SAU hinh trong paper/figures deu lech ban sinh ra. Khong ai thay, vi hinh van hien
# ra binh thuong -- chi la hien ban cu. Mot hien vat phai co DUNG MOT cho o.
OUT = os.path.abspath(os.path.join(RES, "..", "..", "paper", "figures"))

mpl.rcParams.update({
    "font.family": "serif", "font.serif": ["DejaVu Serif"],
    "mathtext.fontset": "dejavuserif",
    "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
    "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.direction": "in", "ytick.direction": "in",
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "lines.linewidth": 1.1, "pdf.fonttype": 42, "ps.fonttype": 42,
})
C = {"blue": "#0072B2", "verm": "#D55E00", "green": "#009E73",
     "gray": "#555555", "orange": "#E69F00"}
COL = 3.35          # be rong mot cot IEEE, inch


def rd(n):
    with open(os.path.join(RES, n)) as f:
        return list(csv.DictReader(f))


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, "%s.%s" % (name, ext)),
                    # ⛔ pad 0.02in khong du: mot nhan truc nam ngoai hop "tight" 1.8pt, va no chi lo ra
                    # khi hinh roi vao COT TRAI (o cot phai thi 1.8pt do van con trong le trang).
                    # Nghia la cung mot hinh, cung mot ban, luc dat luc sai tuy vi tri float.
                    bbox_inches="tight", pad_inches=0.05,
                    **({"dpi": 200} if ext == "png" else {}))
    plt.close(fig)
    print("  ✅ results/figures/%s.pdf" % name)


def fig_msa():
    """PoA theo so vong, ba vo. Duong y=1 la RANG BUOC VAT LY, khong phai moc tuy y."""
    small, big = rd("r5_3_convergence_small.csv"), rd("r5_0_msa_ladder_1584.csv")
    series = [("$132$ satellites", "w132_i53", small, C["blue"], "o", "-"),
              ("$264$", "w264_i53", small, C["green"], "s", "--"),
              ("$1584$", "w1584_i53", big, C["verm"], "^", "-.")]
    fig, ax = plt.subplots(figsize=(COL, 2.25))
    ax.axhline(1.0, color=C["gray"], lw=0.8, ls=":", zorder=1)
    # nhan phai nam DUOI duong y=1 va o ria phai: dat tren-trai thi no de len duong 264
    ax.text(0.62, 0.997, "physical constraint", fontsize=7, color=C["gray"],
            ha="center", va="top", transform=ax.get_yaxis_transform())
    for lab, key, src, c, m, ls in series:
        xs = sorted({int(r["iters"]) for r in src if r["shell"] == key})
        ys = [st.median(float(r["poa"]) for r in src
                        if r["shell"] == key and int(r["iters"]) == x) for x in xs]
        ax.plot(xs, ys, color=c, marker=m, ls=ls, ms=3.4, label=lab, zorder=3)
    ax.set_xscale("log", base=2)
    # danh dau tai DUNG cac so vong da chay; de mac dinh thi truc in 2^5..2^9 khong khop
    allx = sorted({int(r["iters"]) for r in small} | {int(r["iters"]) for r in big})
    ax.set_xticks(allx)
    ax.set_xticklabels([str(x) for x in allx])
    ax.minorticks_off()
    ax.set_xlabel("MSA iterations")
    ax.set_ylabel(r"price of anarchy  $\mathrm{TTT_{UE}}/\mathrm{TTT_{SO}}$")
    ax.legend(frameon=False, loc="lower right")
    save(fig, "fig_msa_convergence")


def fig_denom():
    """blind/UE o vo 1584 theo so vong: mau so chua dung lai."""
    big = rd("r5_0_msa_ladder_1584.csv")
    xs = [int(r["iters"]) for r in big]
    ys = [float(r["blind_over_ue"]) for r in big]
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    ax.plot(xs, ys, color=C["verm"], marker="^", ls="-.", ms=3.6)
    ax.annotate("value the paper\npreviously reported", xy=(xs[0], ys[0]),
                xytext=(xs[0] * 1.4, ys[0] + 190), fontsize=7, color=C["gray"],
                arrowprops=dict(arrowstyle="->", lw=0.6, color=C["gray"]))
    ax.set_xscale("log", base=2)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs])
    ax.minorticks_off()
    ax.set_xlabel("MSA iterations")
    ax.set_ylabel(r"$\mathrm{TTT_{blind}}/\mathrm{TTT_{UE}}$  ($1584$ shell)")
    save(fig, "fig_denominator_drift")


def fig_host():
    """Lech giua hai may, TACH nhom khong-cham-torch khoi nhom qua-torch.

    ⛔ BAN CU VE TU MOT PHEP SO KHONG HOP LE. No diff `/tmp/res_before` voi `results/` va
    goi ket qua la "lech giua hai may". Doi chieu 27/08 cho thay CA HAI thu muc deu mang
    nhan `Linux-x86_64-sol1`, va so o lech la 1094/3345 chu khong phai 17/2999 nhu ghi chep
    noi bo. Hai bac chenh nhau ⇒ hai thu muc do khac nhau vi doi MA NGUON (san MSA 20 -> 40),
    khong phai vi doi may. Mot hinh ve tu do se minh hoa mot dieu khong duoc do.

    Ban nay doc `r6_0_host_control_*.csv`: cung bam ma nguon, cung seed, cung tham so, chi
    khac MAY. Va no ve HAI duong, vi day moi la dieu bai muon noi: nhom A (Dijkstra, MSA,
    TTT -- khong mot dong torch) lech toi 8.5e-04, nhom B (qua mo hinh) lech toi 1.0e-01.
    Ve chung mot duong thi che mat dung cai khac biet hai bac ay.
    """
    files = sorted(glob.glob(os.path.join(RES, "r6_0_host_control_*.csv")))
    if len(files) < 2:
        print("  ⚠ can hai tep r6_0_host_control_*.csv (moi may mot tep) -> bo qua fig_host")
        return
    per = {}
    for p in files:
        rows = list(csv.DictReader(open(p)))
        if rows:
            per[rows[0]["tag"]] = rows
    if len(per) < 2:
        print("  ⚠ hai tep cung mot tag -> bo qua fig_host")
        return
    ta, tb = sorted(per)
    sha = {t: per[t][0].get("code_sha", "?") for t in (ta, tb)}
    if len(set(sha.values())) != 1:
        print("  ⛔ hai may chay hai ban ma khac nhau %s -> KHONG ve" % sha)
        return
    ka = {(x["shell"], x["seed"]): x for x in per[ta]}
    kb = {(x["shell"], x["seed"]): x for x in per[tb]}

    groups = {"A_": [], "B_": []}
    for k in sorted(set(ka) & set(kb)):
        for col in ka[k]:
            pre = col[:2]
            if pre not in groups:
                continue
            try:
                u, v = float(ka[k][col]), float(kb[k][col])
            except (TypeError, ValueError):
                continue
            groups[pre].append(abs(u - v) / max(abs(u), abs(v), 1e-300))

    fig, ax = plt.subplots(figsize=(COL, 2.1))
    LAB = {"A_": "no network (shortest path, MSA, travel time)",
           "B_": "through the network"}
    for pre, colr in (("A_", C["blue"]), ("B_", C["orange"])):
        d = sorted(x for x in groups[pre] if x > 0)
        if not d:
            continue
        ys = [(i + 1) / len(d) for i in range(len(d))]
        ax.step(d, ys, where="post", color=colr, lw=1.3, label=LAB[pre])
    # ⛔ Dai hieu ung bien VAN phai co mat: cau hoi that su khong phai "co lech khong" ma la
    # "lech co lon bang cai bai dang tuyen bo khong". Bo dai nay di thi hinh mat y nghia.
    lo, hi = 0.002, 0.020
    ax.axvspan(lo, hi, color=C["gray"], alpha=0.13, lw=0)
    ax.text(hi * 1.3, 0.32, "effect sizes the\nboundary claims\nrest on\n($0.002$--$0.020$)",
            fontsize=7, color=C["gray"], ha="left", va="center")
    ax.set_xscale("log")
    ax.set_xlabel("relative difference between the two hosts")
    ax.set_ylabel("empirical CDF")
    ax.legend(fontsize=7, loc="upper left", frameon=False)
    save(fig, "fig_host_delta")

def fig_bound():
    """Khoang cach toi UE theo sai so gia, hai bo giai ma."""
    r = sorted(rd("p9_bound.csv"), key=lambda x: float(x["rel_err"]))
    x = [float(v["rel_err"]) for v in r]
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    for col, sd, lab, c, m, ls in (
            ("gap_sp_pct", "gap_sp_std", "single-path decode", C["verm"], "o", "-"),
            ("gap_mp_pct", "gap_mp_std", "multipath decode", C["blue"], "s", "--")):
        y = [float(v[col]) for v in r]
        e = [float(v[sd]) for v in r]
        ax.errorbar(x, y, yerr=e, color=c, marker=m, ls=ls, ms=3.4, capsize=1.8,
                    elinewidth=0.6, label=lab)
    floor = float(r[0]["gap_mp_pct"])
    ax.axhline(floor, color=C["gray"], lw=0.7, ls=":")
    ax.text(x[-1], floor, r"$\delta_{\mathrm{dec}}\approx%.1f\%%$  " % floor,
            fontsize=7, color=C["gray"], ha="right", va="bottom")
    ax.set_xlabel(r"relative price error  $\|\hat g-g^\star\|/\bar g$")
    ax.set_ylabel(r"gap to UE (\%)" if False else "gap to UE (%)")
    ax.legend(frameon=False, loc="upper left")
    save(fig, "fig_bound")


def fig_proactive():
    """Phan ung so voi chu dong khi diem nong troi trong mot khe."""
    r = rd("p7_proactive.csv")
    ds = sorted({float(v["drift"]) for v in r})
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    for col, lab, c, m, ls in (("r_react", "reactive", C["verm"], "o", "-"),
                               ("r_proact", "proactive", C["blue"], "s", "--")):
        y = [st.mean([float(v[col]) for v in r if abs(float(v["drift"]) - d) < 1e-9])
             for d in ds]
        e = [st.stdev([float(v[col]) for v in r if abs(float(v["drift"]) - d) < 1e-9])
             if len([1 for v in r if abs(float(v["drift"]) - d) < 1e-9]) > 1 else 0.0
             for d in ds]
        ax.errorbar(ds, y, yerr=e, color=c, marker=m, ls=ls, ms=3.4, capsize=1.8,
                    elinewidth=0.6, label=lab)
    ax.set_xlabel("hotspot drift within a slot")
    ax.set_ylabel("TTT relative to blind")
    ax.legend(frameon=False, loc="upper left")
    save(fig, "fig_proactive")


def fig_tau():
    """Phan thu hoi theo nhiet do bo giai ma, theo tung vo."""
    # ⛔ VE TU r2_7_fair_tuned_wide, KHONG tu r1_1_tau_sweep. r1_1 chi co HAI vo, nen hinh
    # hien hai duong trong khi muc noi ve BA vo chua tung thay -- nguoi doc ngoai bat dung
    # dieu do. fair_tuned_wide quet cung luoi tau tren ca bon vo, tuc no la nguon khop voi
    # cau van. Va nhan dung ky hieu cua bai ($132$, $264$ o $70^\circ$), khong dung ten cot
    # trong CSV ("w132 (trained)"): ten noi bo cua du lieu khong phai ngon ngu cua bai.
    try:
        r = rd("r2_7_fair_tuned_wide.csv")
    except FileNotFoundError:
        print("  ⚠ khong co r2_7_fair_tuned_wide.csv -> bo qua fig_tau")
        return
    # ⛔ Giu NGUYEN ten cot, dung tai tao no tu so: cot la "recovered_tau1.0" con
    # "%g" % 1.0 cho "1" -> KeyError. Cung lop loi da vap o cot `drift`.
    cols = sorted((k for k in r[0] if k.startswith("recovered_gnn_tau")),
                  key=lambda k: float(k.split("tau")[1]))
    taus = [float(k.split("tau")[1]) for k in cols]
    shells = []
    for v in r:
        if v["shell"] not in shells:
            shells.append(v["shell"])
    def nice(k):
        n = "".join(c for c in k.split("_")[0] if c.isdigit())
        inc = k.split("_i")[1] if "_i" in k else ""
        base = "$%s$" % n + (" (trained)" if n == "132" else "")
        return base + (r" at $70^\circ$" if inc == "70" else "")
    sty = [(C["blue"], "o", "-"), (C["green"], "s", "--"), (C["verm"], "^", "-."),
           (C["orange"], "D", ":")]
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    for i, sh in enumerate(shells):
        c, m, ls = sty[i % len(sty)]
        y = [st.median([float(v[k]) for v in r if v["shell"] == sh]) for k in cols]
        ax.plot(taus, y, color=c, marker=m, ls=ls, ms=3.4,
                label=nice(sh))
    # ⛔ Chu thich hinh noi "gia tri co dinh ke thua (dashed)" nhung hinh KHONG he ve duong
    # do -- chu thich mo ta mot thu khong ton tai. Duong nay chinh la dieu muc VI-I muon chi
    # ra, nen ve no chu khong sua chu thich cho khop voi mot hinh thieu.
    TAU_FIXED = 0.2
    ax.axvline(TAU_FIXED, color=C["gray"], lw=0.8, ls="--")
    ax.text(TAU_FIXED * 1.08, ax.get_ylim()[0], r"  inherited $\tau=%.1f$" % TAU_FIXED,
            fontsize=7, color=C["gray"], ha="left", va="bottom")
    ax.set_xscale("log")
    ax.set_xlabel(r"decoder softmin temperature  $\tau$")
    ax.set_ylabel("recovered fraction")
    ax.legend(frameon=False, loc="lower left", ncol=2, fontsize=7)
    save(fig, "fig_tau")



def fig_inference_cost():
    """Chi phi suy dien theo quy mo chom -- THAY cho hinh "speedup vs UE" cu.

    ⛔ Hinh cu ve he so tang toc so voi loi giai can bang. Ba con so do (22x/21x/29x)
    boc tu LOG CUA MAY KHAC, va mau so la UE KHOI DONG LANH trong khi chinh bai chung
    minh am chi can 1-11 vong. O vo 1584 mau so con khong hoi tu. Ca ba ly do deu du de
    bo cot do.

    Thay bang thu do duoc tren MOT may trong MOT lan chay va co nghia van hanh: thoi
    gian dinh tuyen mot lan, va no chiem bao nhieu phan cua khe 60 giay.
    """
    t = rd("r4_4_stage_timing.csv")
    ns = sorted({int(x["n_sat"]) for x in t})
    slot = float(t[0]["slot_s"])
    tot = [st.mean([float(x["t_total_s"]) for x in t if int(x["n_sat"]) == n]) for n in ns]
    # tach ba chang de thay cho nao dat: dac trung / forward / giai ma
    parts = [("features", "t_features_s", C["blue"], "o", "-"),
             ("GNN forward", "t_forward_s", C["green"], "s", "--"),
             ("decode", "t_decode_s", C["verm"], "^", "-.")]
    fig, ax = plt.subplots(figsize=(COL, 2.2))
    for lab, col, c, m, ls in parts:
        y = [st.mean([float(x[col]) for x in t if int(x["n_sat"]) == n]) for n in ns]
        ax.plot(ns, y, color=c, marker=m, ls=ls, ms=3.4, label=lab)
    ax.plot(ns, tot, color=C["gray"], marker="D", ls=":", ms=3.2, label="total")
    ax.axhline(slot, color=C["orange"], lw=0.8, ls="--")
    ax.text(ns[0], slot * 1.12, "$%.0f$ s slot" % slot, fontsize=7, color=C["orange"])
    ax.set_xscale("log", base=2); ax.set_yscale("log")
    ax.set_xticks(ns); ax.set_xticklabels([str(n) for n in ns]); ax.minorticks_off()
    ax.set_xlabel("satellites in shell")
    ax.set_ylabel("time per slot (s)")
    ax.legend(frameon=False, loc="upper left", fontsize=7)
    save(fig, "fig_inference_cost")


def main():
    # ⛔ fig_denom da bi GOP thanh mot dong cua tab-msa (xem tab_msa trong make_figs_tables).
    # Giu no trong danh sach nay thi moi lan chay lai sinh ra mot hinh KHONG AI DUNG: bai
    # khong \input no, ma no van nam trong goi nop. Phat hien duoc bang phep kiem BYTE (tim
    # manh luong byte cua tung tep hinh trong PDF cuoi) chu khong bang bat ky cong chu nao.
    for fn in (fig_msa, fig_host, fig_bound, fig_proactive, fig_tau, fig_inference_cost):
        try:
            fn()
        except Exception as e:
            print("  ⛔ %-12s LOI: %s" % (fn.__name__, e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
