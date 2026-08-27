"""Is the eps-ECMP win on the 264 shell robust, or was it one lucky point?

r2_7_matched_all.py found the learned price field beaten 0/9 on the 264-satellite shell by
eps-ECMP at eps=0.20, a congestion-BLIND one-pass heuristic, while winning 9/9 on the 132 shell it
was trained on. Two things could produce that, and they call for opposite responses:

  (a) eps-ECMP genuinely gets stronger as the shell grows, because a bigger grid offers more
      near-equal-cost detours to spread across. Then the paper's transfer claim is in real trouble
      and the contribution has to move to an axis blind spreading cannot reach.
  (b) eps=0.20 happens to sit at a sweet spot for that one shell. Then it is a sampling artefact
      of picking one knob value, and the fix is to report the sweep.

The two are told apart by sweeping eps across a LADDER of shell sizes rather than testing one
value on one shell. Sizes 132 to 396 keep the plane structure and scale the grid; the 70-degree
shell changes inclination instead, which is also one of the transfer axes Reviewer 2 asked about
in comment 6, so this run does double duty.

Demand is scaled with the constellation so offered load per satellite stays comparable, otherwise
a bigger shell is simply a lighter-loaded one and the comparison drifts for a reason that has
nothing to do with routing.
"""
import csv
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                   # noqa: E402
from traffic import evaluate                                       # noqa: E402
from p5_gnn_router import (train, eval_instance, TRAIN_WALKER,      # noqa: E402
                           TRAIN_PAIRS, CAP, make_instance)
from r2_7_warmstart_ecmp import msa_from, ecmp_ttt, SLOT_S, DRIFT_PER_SLOT  # noqa: E402
from r2_7_matched_all import slot_instance                          # noqa: E402

PAIRS_PER_SAT = 600 / 132.0
SHELLS = [
    ("w132_i53", Walker(132, 12, 1, 53.0, 550.0)),      # da huan luyen
    ("w198_i53", Walker(198, 18, 1, 53.0, 550.0)),
    ("w264_i53", Walker(264, 24, 1, 53.0, 550.0)),
    ("w396_i53", Walker(396, 36, 1, 53.0, 550.0)),
    ("w264_i70", Walker(264, 24, 1, 70.0, 550.0)),      # doi NGHIENG, khong doi kich thuoc
]
SEEDS = [0, 1, 2]
N_SLOTS = 3                       # khe 0 lam am cache, khe 1-2 duoc cham
EPSS = [0.0, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50]
OUT = os.path.join(ROOT, "results", "r2_7_eps_sweep.csv")


def main():
    print("R2.7c -- quet eps tren THANG kich thuoc vo + mot vo doi nghieng\n", flush=True)
    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 10_000 + i, need_eig=False) for i in range(10)]
    model = train("GCN", tr, seed=0)
    print(f"da huan luyen tren {TRAIN_WALKER.T} sat.\n", flush=True)

    rows = []
    hdr = f"{'vo':10s} {'sd':>2} {'khe':>3} {'gnn':>7} | " + " ".join(f"e={e:<4g}".rjust(7)
                                                                     for e in EPSS)
    print(hdr, flush=True)
    for name, w in SHELLS:
        npairs = int(round(w.T * PAIRS_PER_SAT))
        for seed in SEEDS:
            warm = None
            for k in range(N_SLOTS):
                t, band = k * SLOT_S, k * DRIFT_PER_SLOT
                ins = slot_instance(w, npairs, seed, t, band)
                A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]
                if k == 0:
                    _, warm = msa_from(A, W, dem, CAP, 20)
                    continue
                blind = evaluate(A, W, dem, CAP, policy="blind")["total_ttt"]
                ue = evaluate(A, W, dem, CAP, policy="ue")["total_ttt"]
                so = evaluate(A, W, dem, CAP, policy="so")["total_ttt"]
                span = blind - ue
                rec = lambda x: (blind - x) / span if span > 0 else float("nan")
                gnn = eval_instance(model, ins)["gnn"]
                assert gnn >= so - 1e-6, f"GNN {gnn:.3f} < SO {so:.3f}"
                row = {"shell": name, "n_sat": w.T, "inc": w.inc if hasattr(w, "inc") else "",
                       "pairs": npairs, "seed": seed, "slot": k,
                       "recovered_gnn": round(rec(gnn), 4),
                       # ⛔ GHI CA TI SO QUY CHIEU BLIND. `recovered` chia cho (blind - ue), nen no vo
                       # nghia o bat ky vo nao co tham chieu can bang khong dat PoA >= 1. Do 27/08:
                       # vo 396 dat 0.9854 o 160 vong va van duoi 1, vo 1584 khong bao gio dat. Ti so
                       # voi blind do TRUC TIEP nen no van dung o dung nhung vo ma `recovered` chet.
                       "blind_ttt": round(blind, 4), "ue_ttt": round(ue, 4),
                       "poa": round(ue / so, 6) if so > 0 else float("nan"),
                       "rel_gnn": round(gnn / blind, 6) if blind > 0 else float("nan"), 
                       "unit_of_analysis": "vo-x-seed-x-khe"}
                cells = []
                for e in EPSS:
                    v = ecmp_ttt(A, W, dem, CAP, eps=e)
                    assert v >= so - 1e-6, f"ECMP eps={e} = {v:.3f} < SO {so:.3f}"
                    row[f"recovered_ecmp_{e}"] = round(rec(v), 4)
                    row[f"rel_ecmp_{e}"] = round(v / blind, 6) if blind > 0 else float("nan")
                    cells.append(f"{rec(v):>7.3f}")
                rows.append(row)
                print(f"{name:10s} {seed:>2} {k:>3} {rec(gnn):>7.3f} | " + " ".join(cells),
                      flush=True)
                _, warm = msa_from(A, W, dem, CAP, 20)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== TRUNG VI theo vo: GNN vs eps-ECMP tot nhat ===")
    print(f"{'vo':10s} {'n_sat':>5} {'GNN':>7} | " + " ".join(f"e={e:<4g}".rjust(7) for e in EPSS)
          + f" | {'eps tot nhat':>12s} {'chenh':>7s}")
    verdict = []
    for name, w in SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        if not sel:
            continue
        g = st.median(r["recovered_gnn"] for r in sel)
        me = {e: st.median(r[f"recovered_ecmp_{e}"] for r in sel) for e in EPSS}
        be = max(EPSS, key=lambda e: me[e])
        d = g - me[be]
        loses = sum(1 for r in sel if r["recovered_gnn"] < r[f"recovered_ecmp_{be}"])
        verdict.append((name, w.T, g, be, me[be], d, loses, len(sel)))
        print(f"{name:10s} {w.T:>5d} {g:>7.3f} | "
              + " ".join(f"{me[e]:>7.3f}" for e in EPSS)
              + f" | {be:>12g} {d:>+7.3f}")

    print("\n=== PHAN QUYET ===")
    for name, nsat, g, be, mv, d, loses, n in verdict:
        tag = "GNN thang" if d > 0 else "⛔ GNN THUA"
        print(f"  {name:10s} ({nsat:>3d} sat): GNN {g:.3f} vs ECMP eps={be:g} {mv:.3f} "
              f"= {d:+.3f}, thua {loses}/{n} don vi  [{tag}]")
    lost = [v for v in verdict if v[5] < 0]
    grow = [v for v in verdict if "i53" in v[0]]
    print()
    if not lost:
        print("  KHONG vo nao GNN thua => ket qua 264 truoc day la mot DIEM le, khong ben.")
    else:
        print(f"  GNN thua o {len(lost)}/{len(verdict)} vo: "
              + ", ".join(f"{v[0]}({v[1]} sat)" for v in lost))
        if len(lost) > 1:
            print("  => KHONG phai diem le. Phai doi truc tuyen bo.")
        else:
            print("  => Mot vo duy nhat. Can them vo truoc khi ket luan.")
    if len(grow) >= 3:
        ds = [v[5] for v in sorted(grow, key=lambda v: v[1])]
        print(f"\n  Theo thang kich thuoc {[v[1] for v in sorted(grow, key=lambda v: v[1])]}: "
              f"chenh = {[f'{x:+.3f}' for x in ds]}")
        print("  " + ("Chenh GIAM khi vo lon dan => eps-ECMP manh len theo kich thuoc, day la CO CHE."
                      if ds == sorted(ds, reverse=True) else
                      "Chenh KHONG don dieu theo kich thuoc => chua ket luan duoc ve co che."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
