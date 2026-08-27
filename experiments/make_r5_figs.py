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
OUT = os.path.join(RES, "figures")

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
                    bbox_inches="tight", pad_inches=0.02,
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
    """Phan phoi lech giua hai may, doi chieu voi cac hieu ung bien cua bai."""
    a_d, b_d = "/tmp/res_before", os.path.join(RES)
    if not os.path.isdir(a_d):
        print("  ⚠ khong co /tmp/res_before -> bo qua fig_host")
        return
    deltas = []
    for p in sorted(glob.glob(os.path.join(a_d, "*.csv"))):
        q = os.path.join(b_d, os.path.basename(p))
        if not os.path.exists(q):
            continue
        A, B = list(csv.DictReader(open(p))), list(csv.DictReader(open(q)))
        if not A or not B or len(A) != len(B) or A[0].keys() != B[0].keys():
            continue
        for x, y in zip(A, B):
            for k in x:
                if any(t in k for t in ("_s", "seconds", "frac_of_slot", "speedup")):
                    continue
                try:
                    u, v = float(x[k]), float(y[k])
                except (TypeError, ValueError):
                    continue
                if u != v:
                    deltas.append(abs(u - v) / max(abs(u), abs(v), 1e-12))
    if not deltas:
        print("  ⚠ khong co o nao lech -> bo qua fig_host")
        return
    deltas.sort()
    ys = [(i + 1) / len(deltas) for i in range(len(deltas))]
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    ax.step(deltas, ys, where="post", color=C["blue"], lw=1.2)
    # ba nguong 0.002 / 0.007 / 0.020 nam qua gan nhau tren truc log nen ba nhan de
    # len nhau. Ve MOT DAI phu kin khoang do, mot nhan duy nhat: doc duoc va cung y.
    lo, hi = 0.002, 0.020
    ax.axvspan(lo, hi, color=C["orange"], alpha=0.13, lw=0)
    ax.axvline(hi, color=C["orange"], lw=0.7, ls="--")
    ax.text(hi * 1.25, 0.30, "effect sizes the\nboundary claims\nrest on\n($0.002$--$0.020$)",
            fontsize=7, color=C["gray"], ha="left", va="center")
    ax.set_xscale("log")
    ax.set_xlabel("relative change of a reported cell")
    ax.set_ylabel("empirical CDF")

    save(fig, "fig_host_delta")



# ═══════════════════════════════════════════════════════════════════════════
# BA HINH DU LIEU CU, ve lai theo CUNG stylesheet cua kit.
# Truoc do chung ve bang pgfplots voi bo mau TU DAT (cNavy/cRed/cAmber...), tuc moi
# hinh mot kieu va khong an toan cho nguoi mu mau. Nay dung Okabe-Ito, phan biet bang
# MAU + MARKER + KIEU NET, va xuat PDF vector giong ba hinh moi.
# ═══════════════════════════════════════════════════════════════════════════

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
    try:
        r = rd("r1_1_tau_sweep.csv")
    except FileNotFoundError:
        print("  ⚠ khong co r1_1_tau_sweep.csv -> bo qua fig_tau")
        return
    # ⛔ Giu NGUYEN ten cot, dung tai tao no tu so: cot la "recovered_tau1.0" con
    # "%g" % 1.0 cho "1" -> KeyError. Cung lop loi da vap o cot `drift`.
    cols = sorted((k for k in r[0] if k.startswith("recovered_tau")),
                  key=lambda k: float(k.split("tau")[1]))
    taus = [float(k.split("tau")[1]) for k in cols]
    shells = []
    for v in r:
        if v["shell"] not in shells:
            shells.append(v["shell"])
    sty = [(C["blue"], "o", "-"), (C["green"], "s", "--"), (C["verm"], "^", "-.")]
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    for i, sh in enumerate(shells):
        c, m, ls = sty[i % len(sty)]
        y = [st.median([float(v[k]) for v in r if v["shell"] == sh]) for k in cols]
        ax.plot(taus, y, color=c, marker=m, ls=ls, ms=3.4,
                label=sh)
    ax.set_xscale("log")
    ax.set_xlabel(r"decoder softmin temperature  $\tau$")
    ax.set_ylabel("recovered fraction")
    ax.legend(frameon=False, loc="lower left", ncol=1)
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
    for fn in (fig_msa, fig_denom, fig_host, fig_bound, fig_proactive, fig_tau, fig_inference_cost):
        try:
            fn()
        except Exception as e:
            print("  ⛔ %-12s LOI: %s" % (fn.__name__, e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
