"""R2.7, final: every policy on the SAME instances, so the comparison is actually matched.

r2_7_warmstart_ecmp.py measured warm-started MSA and eps-ECMP on consecutive drifting slots, and
compared them against the GNN's 0.957 read out of p6_baselines.csv. That was a DIFFERENT instance
set: a different shell mix, different demand counts, no slot drift. Quoting the two side by side
was a comparison of convenience, and the honest version has to put every policy on identical
instances.

So this rebuilds the same drifting-slot instances, trains the GNN exactly as p6 trains it, and
evaluates all of them together:

    blind, UE, SO                      the references the paper already uses
    MSA cold T=2                       the paper's own solver, truncated to the GNN's budget
    MSA warm T=1, T=2                  Reviewer 2's "warm-started MSA", resumed at the cached k
    ECMP eps in {0, 0.05, 0.20}        Reviewer 2's "ECMP-style multipath", congestion-BLIND
    GNN                                the proposed method, 2 passes + 1 forward

`make_instance` in p5_gnn_router.py hardcodes t=0 and takes no hotspot drift, so the instance
builder is reproduced here with t and band threaded through. Everything else -- feature builder,
model, training loop, decode, TAU -- is imported, not reimplemented, so the GNN measured here is
the paper's GNN and not a lookalike.

The metric is the paper's: recovered = (blind - policy) / (blind - ue).
"""
import csv
import os
import statistics as st
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker, grid_isl_graph                  # noqa: E402
from traffic import gravity_demands, evaluate, ue_loads           # noqa: E402
from p5_gnn_router import (build_features, train, eval_instance,   # noqa: E402
                           TRAIN_WALKER, TRAIN_PAIRS, CAP, make_instance)
from r2_7_warmstart_ecmp import msa_from, ecmp_ttt, SLOT_S, DRIFT_PER_SLOT  # noqa: E402

SHELLS = [("w132", Walker(132, 12, 1, 53.0, 550.0), 600),
          ("w264", Walker(264, 24, 1, 53.0, 550.0), 1200)]
SEEDS = [0, 1, 2]
N_SLOTS = 4
N_TRAIN = int(os.environ.get("QWGNN_TRAIN", "10"))
OUT = os.path.join(ROOT, "results", "r2_7_matched_all.csv")


def slot_instance(walker, npairs, seed, t, band):
    """make_instance, but at time t with a drifted hotspot band. Same builder otherwise."""
    A_np, W_np = grid_isl_graph(walker, t, seam=False)
    pos = walker.positions(t)
    dem = gravity_demands(pos, npairs, np.random.default_rng(seed), hotspot_shift=band)
    X, ctx, rows, cols, bload = build_features(A_np, W_np, dem, need_eig=False)
    return {"A_np": A_np, "W_np": W_np, "dem": dem, "cap": CAP, "n": A_np.shape[0],
            "X": X, "ctx": ctx, "pos": pos, "bload": bload,
            "rows": rows, "cols": cols, "g_star": None, "tgt": None}


def main():
    print("R2.7 FINAL -- moi chinh sach tren CUNG thuc the\n")
    print(f"huan luyen GNN nhu p6: {N_TRAIN} thuc the tren {TRAIN_WALKER.T} sat, "
          f"{TRAIN_PAIRS} cap ...", flush=True)
    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 10_000 + i, need_eig=False)
          for i in range(N_TRAIN)]
    model = train("GCN", tr, seed=0)
    print("xong.\n")

    cols = ["cold_T2", "warm_T1", "warm_T2", "ecmp0", "ecmp05", "ecmp20", "gnn"]
    print(f"{'shell':6s} {'sd':>2} {'khe':>3} | " + " ".join(f"{c:>8s}" for c in cols))
    rows = []
    for name, w, npairs in SHELLS:
        for seed in SEEDS:
            warm = None
            for k in range(N_SLOTS):
                t, band = k * SLOT_S, k * DRIFT_PER_SLOT
                ins = slot_instance(w, npairs, seed, t, band)
                A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]
                _, conv = msa_from(A, W, dem, CAP, 20)
                if k == 0:
                    warm = conv
                    continue
                blind = evaluate(A, W, dem, CAP, policy="blind")["total_ttt"]
                ue = evaluate(A, W, dem, CAP, policy="ue")["total_ttt"]
                so = evaluate(A, W, dem, CAP, policy="so")["total_ttt"]
                span = blind - ue
                rec = lambda x: (blind - x) / span if span > 0 else float("nan")
                vals = {
                    "cold_T2": msa_from(A, W, dem, CAP, 2)[0],
                    "warm_T1": msa_from(A, W, dem, CAP, 1, load0=warm, k0=20)[0],
                    "warm_T2": msa_from(A, W, dem, CAP, 2, load0=warm, k0=20)[0],
                    "ecmp0": ecmp_ttt(A, W, dem, CAP, eps=0.0),
                    "ecmp05": ecmp_ttt(A, W, dem, CAP, eps=0.05),
                    "ecmp20": ecmp_ttt(A, W, dem, CAP, eps=0.20),
                    "gnn": eval_instance(model, ins)["gnn"],
                }
                for c, v in vals.items():
                    assert v >= so - 1e-6, f"{c} = {v:.3f} < system optimum {so:.3f}: BUG"
                row = {"shell": name, "seed": seed, "slot": k,
                       "blind_ttt": round(blind, 4), "ue_ttt": round(ue, 4),
                       "so_ttt": round(so, 4), "unit_of_analysis": "shell-x-seed-x-slot"}
                row.update({f"recovered_{c}": round(rec(v), 4) for c, v in vals.items()})
                rows.append(row)
                print(f"{name:6s} {seed:>2} {k:>3} | "
                      + " ".join(f"{rec(vals[c]):>8.3f}" for c in cols))
                warm = conv

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    label = {"cold_T2": "MSA lanh T=2      (2 luot)",
             "warm_T1": "MSA NONG  T=1      (1 luot)",
             "warm_T2": "MSA NONG  T=2      (2 luot)",
             "ecmp0": "ECMP eps=0        (1 luot)",
             "ecmp05": "ECMP eps=0.05     (1 luot)",
             "ecmp20": "ECMP eps=0.20     (1 luot)",
             "gnn": "GNN (de xuat)     (2 luot + fwd)"}
    print("=== TRUNG VI tren CUNG thuc the ===")
    med = {c: st.median(r[f"recovered_{c}"] for r in rows) for c in cols}
    for c in cols:
        print(f"  {label[c]:32s} {med[c]:>7.3f}")

    # Cham theo TUNG VO, khong gop. Ban dau toi lay "doi thu manh nhat theo trung vi GOP" roi
    # in "GNN thang 18/18" -- dung voi doi thu DO, nhung no giau mat rang tren vo 264 mot doi thu
    # KHAC thang tuyet doi. Trung vi gop la mot proxy, va no vua che mat mot lan DOI DAU.
    print("\n=== PHAN QUYET R2.7, cham RIENG tung vo ===")
    flip = False
    for shell in [s_[0] for s_ in SHELLS]:
        sel = [r for r in rows if r["shell"] == shell]
        med = {c: st.median(r[f"recovered_{c}"] for r in sel) for c in cols}
        rivals = [c for c in cols if c != "gnn"]
        best = max(rivals, key=lambda c: med[c])
        d = med["gnn"] - med[best]
        wins = sum(1 for r in sel if r["recovered_gnn"] > r[f"recovered_{best}"])
        tag = "GNN THANG" if d > 0 else "⛔ GNN THUA"
        print(f"  {shell}: doi thu manh nhat = {label[best].strip():28s} {med[best]:.3f}")
        print(f"        GNN {med['gnn']:.3f}, chenh {d:+.3f}, thang {wins}/{len(sel)} don vi  [{tag}]")
        flip |= d < 0
    print()
    if flip:
        print("  ⛔ CO VO MA GNN THUA. R2.7 CHUA tra loi duoc.")
        print("     Doi thu thang la mot heuristic MU tac nghen, mot luot, re hon GNN.")
        print("     Va no thang tren vo NGOAI PHAN PHOI, tuc dung cho bai tuyen bo chuyen giao.")
    else:
        print("  R2.7 tra loi duoc tren moi vo.")
    print(f"\n  {len(rows)} don vi (2 vo x 3 seed x 3 khe). Don vi phan tich = (vo, seed, khe).")
    print("  ECMP eps la mot THAM SO: o eps=0.05 GNN thang ca hai vo. Phai bao ca DAI eps,")
    print("  dung chon mot gia tri roi ket luan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
