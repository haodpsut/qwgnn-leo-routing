"""Is the off-distribution loss a limit of the method, or of how it was trained?

r2_7_eps_sweep.py showed the learned price field beating eps-ECMP by +0.315 on the shell it was
trained on and losing on all four shells it was not: 198, 264, 396, and a 264 at a different
inclination. That is a statement about ONE training recipe, the one p6 uses: ten instances, all
drawn from the 132-satellite shell. It is not yet a statement about learned price fields.

The two readings need separating:

  (a) the price field itself does not transfer, and the paper's third sub-problem has to be
      rewritten around what it can actually claim;
  (b) a model shown one constellation learns that constellation, and showing it several during
      training restores the advantage. Then the finding is a fixable recipe bug and the transfer
      claim survives in a stronger form, having now beaten a serious blind baseline.

CONTROLLING FOR THE OBVIOUS CONFOUND. A mixed-training model that also saw MORE data would tell us
nothing: any gain could be volume rather than diversity. So both arms get exactly the same number
of training instances, N_TRAIN. The single arm draws all of them from the 132 shell, as p6 does.
The mixed arm splits the same budget across three small shells that differ in size and in
inclination. Nothing else changes: same feature builder, same model, same epochs, same seed.

TEST SHELLS ARE UNSEEN BY BOTH ARMS. 264 and 396 at 53 degrees, and 264 at 70 degrees. The mixed
arm trains on 132/198 at 53 and 132 at 70, so it has seen neither test size nor the 70-degree
shell at test scale.
"""
import csv
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

from constellation import Walker                                    # noqa: E402
from traffic import evaluate                                        # noqa: E402
from p5_gnn_router import (train, eval_instance, CAP, make_instance)  # noqa: E402
from r2_7_warmstart_ecmp import msa_from, ecmp_ttt, SLOT_S, DRIFT_PER_SLOT  # noqa: E402
from r2_7_matched_all import slot_instance                           # noqa: E402

PAIRS_PER_SAT = 600 / 132.0
N_TRAIN = 12                       # ngan sach GIONG NHAU cho ca hai nhanh

SINGLE_MIX = [(Walker(132, 12, 1, 53.0, 550.0), 12)]                 # cong thuc cua p6
DIVERSE_MIX = [(Walker(132, 12, 1, 53.0, 550.0), 4),                 # cung tong = 12
               (Walker(198, 18, 1, 53.0, 550.0), 4),
               (Walker(132, 12, 1, 70.0, 550.0), 4)]

TEST_SHELLS = [("w264_i53", Walker(264, 24, 1, 53.0, 550.0)),
               ("w396_i53", Walker(396, 36, 1, 53.0, 550.0)),
               ("w264_i70", Walker(264, 24, 1, 70.0, 550.0))]
SEEDS = [0, 1, 2]
N_SLOTS = 3
EPSS = [0.05, 0.10, 0.20, 0.35, 0.50]
OUT = os.path.join(ROOT, "results", "r2_7_train_mix.csv")


def build(mix, tag):
    insts, s = [], 20_000
    for walker, k in mix:
        npairs = int(round(walker.T * PAIRS_PER_SAT))
        for _ in range(k):
            insts.append(make_instance(walker, npairs, s, need_eig=False))
            s += 1
    assert len(insts) == N_TRAIN, f"{tag}: {len(insts)} != {N_TRAIN}"
    print(f"  {tag:9s}: {len(insts)} thuc the tu "
          + ", ".join(f"{w.T}sat/inc{w.inc:g}x{k}" for w, k in mix), flush=True)
    return train("GCN", insts, seed=0)


def main():
    print(f"R2.7d -- da dang HUAN LUYEN co cuu duoc chuyen giao khong?")
    print(f"ngan sach GIONG NHAU: {N_TRAIN} thuc the moi nhanh\n", flush=True)
    models = {"single": build(SINGLE_MIX, "single"), "mix": build(DIVERSE_MIX, "mix")}
    print(flush=True)

    rows = []
    print(f"{'vo':10s} {'sd':>2} {'khe':>3} {'single':>7} {'mix':>7} | "
          + " ".join(f"e={e:<4g}".rjust(7) for e in EPSS), flush=True)
    for name, w in TEST_SHELLS:
        npairs = int(round(w.T * PAIRS_PER_SAT))
        for seed in SEEDS:
            for k in range(N_SLOTS):
                t, band = k * SLOT_S, k * DRIFT_PER_SLOT
                ins = slot_instance(w, npairs, seed, t, band)
                A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]
                if k == 0:
                    continue
                blind = evaluate(A, W, dem, CAP, policy="blind")["total_ttt"]
                ue = evaluate(A, W, dem, CAP, policy="ue")["total_ttt"]
                so = evaluate(A, W, dem, CAP, policy="so")["total_ttt"]
                span = blind - ue
                rec = lambda x: (blind - x) / span if span > 0 else float("nan")
                row = {"shell": name, "n_sat": w.T, "inc": w.inc, "seed": seed, "slot": k,
                       # ⛔ GHI CA TI SO QUY CHIEU BLIND. `recovered` chia cho (blind - ue), nen no vo
                       # nghia o bat ky vo nao co tham chieu can bang khong dat PoA >= 1. Do 27/08:
                       # vo 396 dat 0.9854 o 160 vong va van duoi 1, vo 1584 khong bao gio dat. Ti so
                       # voi blind do TRUC TIEP nen no van dung o dung nhung vo ma `recovered` chet.
                       "blind_ttt": round(blind, 4), "ue_ttt": round(ue, 4),
                       "poa": round(ue / so, 6) if so > 0 else float("nan"),
                       "unit_of_analysis": "vo-x-seed-x-khe"}
                for tag, m in models.items():
                    v = eval_instance(m, ins)["gnn"]
                    assert v >= so - 1e-6, f"{tag} {v:.3f} < SO {so:.3f}"
                    row[f"recovered_{tag}"] = round(rec(v), 4)
                    row[f"rel_{tag}"] = round(v / blind, 6) if blind > 0 else float("nan")
                for e in EPSS:
                    v = ecmp_ttt(A, W, dem, CAP, eps=e)
                    assert v >= so - 1e-6, f"ecmp{e} {v:.3f} < SO {so:.3f}"
                    row[f"recovered_ecmp_{e}"] = round(rec(v), 4)
                    row[f"rel_ecmp_{e}"] = round(v / blind, 6) if blind > 0 else float("nan")
                rows.append(row)
                print(f"{name:10s} {seed:>2} {k:>3} {row['recovered_single']:>7.3f} "
                      f"{row['recovered_mix']:>7.3f} | "
                      + " ".join(f"{row[f'recovered_ecmp_{e}']:>7.3f}" for e in EPSS), flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n# da ghi results/{os.path.basename(OUT)} ({len(rows)} dong)\n")

    print("=== TRUNG VI theo vo THU (ca hai nhanh deu CHUA THAY cac vo nay) ===")
    print(f"{'vo':10s} {'single':>8} {'mix':>8} {'ecmp tot':>9} {'eps':>5} | "
          f"{'mix - single':>12} {'mix - ecmp':>11}")
    verdict = []
    for name, w in TEST_SHELLS:
        sel = [r for r in rows if r["shell"] == name]
        s_ = st.median(r["recovered_single"] for r in sel)
        m_ = st.median(r["recovered_mix"] for r in sel)
        me = {e: st.median(r[f"recovered_ecmp_{e}"] for r in sel) for e in EPSS}
        be = max(EPSS, key=lambda e: me[e])
        verdict.append((name, s_, m_, me[be], be, len(sel), sel))
        print(f"{name:10s} {s_:>8.3f} {m_:>8.3f} {me[be]:>9.3f} {be:>5g} | "
              f"{m_-s_:>+12.3f} {m_-me[be]:>+11.3f}")

    print("\n=== PHAN QUYET ===")
    helped = sum(1 for v in verdict if v[2] > v[1] + 0.005)
    beats = [v for v in verdict if v[2] > v[3]]
    print(f"  da dang giup tren {helped}/{len(verdict)} vo thu")
    for name, s_, m_, e_, be, n, sel in verdict:
        w = sum(1 for r in sel if r["recovered_mix"] > r[f"recovered_ecmp_{be}"])
        tag = "mix THANG ecmp" if m_ > e_ else "⛔ mix van THUA ecmp"
        print(f"  {name:10s}: single {s_:.3f} -> mix {m_:.3f} (ecmp {e_:.3f} o eps={be:g}), "
              f"thang {w}/{n}  [{tag}]")
    print()
    if len(beats) == len(verdict):
        print("  ✅ Da dang huan luyen CUU duoc chuyen giao tren MOI vo thu.")
        print("     Day la loi CONG THUC HUAN LUYEN, sua duoc, va tuyen bo chuyen giao song")
        print("     o dang manh hon vi da vuot mot baseline mu nghiem tuc.")
    elif beats:
        print(f"  Cuu duoc {len(beats)}/{len(verdict)} vo. Chua du de giu nguyen tuyen bo.")
    else:
        print("  ⛔ Da dang KHONG cuu duoc. Truong gia hoc duoc khong vuot noi trai tai mu")
        print("     o ngoai phan phoi, du duoc thay nhieu vo. Phai DOI TRUC tuyen bo sang thu")
        print("     ma ecmp khong lam duoc: chu dong truoc hotspot troi, hoac on dinh giua khe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
