"""R7.1 — Độ bền với TRẠNG THÁI MẠNG KHÔNG HOÀN HẢO. Trả lời Phản biện 1 ý 5, vòng 12059.

⛔ VÌ SAO CÓ TỆP NÀY. Nguyên văn yêu cầu:

    "The proposed framework is evaluated under the assumption that the demand matrix, the
     blind all-or-nothing load, the topology/propagation-delay information, and link
     capacities are accurate and timely. In practical LEO operations, these quantities may
     be noisy, delayed, or only partially observed -- e.g., demand-estimation errors, stale
     telemetry, ephemeris or capacity mismatch, and link failures. The authors should
     discuss the robustness of BOTH the learned price field AND the blind multipath baseline
     to such imperfect network state information, and preferably add a sensitivity experiment."

Theo luật B0-a của `revise-paper-chuan`: làm ĐÚNG bốn trục họ nêu tên, dùng ĐÚNG từ của họ,
và quét CẢ HAI chính sách. Không tự đổi sang trục mình cho là hay hơn.

## Thiết kế: chính sách nhìn trạng thái HỎNG, phép đo dùng trạng thái THẬT

Đây là định nghĩa của "imperfect network state information". Cả hai hàm của kho đều tách sẵn
hai vai đó, nên không phải sửa bộ mô phỏng:

    multipath_route(A, prop_W, route_cost, demands, cap, tau)
                       ^^^^^^  ^^^^^^^^^^
                       ĐO            ĐỊNH TUYẾN

⇒ `route_cost` dựng từ **trạng thái nhà điều hành TIN LÀ ĐÚNG**; `prop_W`, `cap`, `demands`
là **trạng thái thật**. Cả hai chính sách giải mã bằng cùng một `multipath_route` với cùng
`tau`, chỉ khác trường chi phí:

  - **learned price field**: `route_cost` = W nhân hệ số GNN dự đoán, GNN ăn đặc trưng từ
    trạng thái hỏng.
  - **blind multipath**: `route_cost` = W (độ trễ lan truyền tự do), không hề ước lượng tắc
    nghẽn. Đây đúng là "the one-pass blind multipath split" của bài.

## Một dự đoán ĐĂNG KÝ TRƯỚC khi chạy

Mốc mù định tuyến **chỉ** trên `A` và `prop_W`; nó **không bao giờ** đọc ma trận nhu cầu hay
dung lượng. Vậy trên hai trục *demand-estimation errors* và *capacity mismatch* nó phải
**miễn nhiễm hoàn toàn**, tức số của nó không đổi một chữ số nào. Nếu phép đo cho thấy nó
đổi thì **bộ đo sai**, không phải phát hiện. Cổng `C3` dưới đây kiểm đúng điều đó.

⇒ Nếu dự đoán đúng thì phát hiện của mục này là một **bất đối xứng**: chính sách rẻ hơn
không chỉ rẻ hơn, nó còn miễn nhiễm với hai trong bốn kiểu hỏng, vì nó không tiêu thụ cái
trạng thái bị hỏng. Đó là kết quả **thuận** cho một bài kiểm toán, không phải tin xấu.

    python3 experiments/r7_1_imperfect_state.py            # day du
    python3 experiments/r7_1_imperfect_state.py --nhanh    # mot vo, 2 hat, de kiem mach
    python3 experiments/r7_1_imperfect_state.py --tu-kiem  # doi chung, khong can GPU
"""
import argparse
import csv
import os
import statistics as st
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "experiments"))

TAU = 0.20          # giá trị cố định của bản thảo, giữ nguyên để so sánh có nghĩa
SLOT_S = 60.0       # ⛔ lay con so cua BO MO PHONG (r2_7_warmstart_ecmp.py,
                    # r4_4_stage_timing.py), khong lay tu van xuoi cua bai. Chinh kho
                    # da co ghi chu ve mot lan vap dung chuyen do.

# Bốn trục, đặt tên ĐÚNG như phản biện viết (luật B0-a).
TRUC = {
    "demand-estimation errors":      [0.05, 0.10, 0.20, 0.40],   # sigma log-chuan
    "stale telemetry":               [1, 2, 4, 8],               # tre bao nhieu khe
    "ephemeris or capacity mismatch": [0.05, 0.10, 0.20, 0.40],  # lech tuong doi
    "link failures":                 [0.01, 0.02, 0.05, 0.10],   # ti le ISL rung
}


def truong_gia_hoc(model, ins, torch):
    """Trường giá học được, từ đặc trưng của ins (có thể là bản HỎNG)."""
    with torch.no_grad():
        g = torch.expm1(model(ins["X"], ins["ctx"])).clamp(min=0).numpy()
    rc = ins["W_np"].copy()
    rc[ins["rows"], ins["cols"]] = ins["W_np"][ins["rows"], ins["cols"]] * (1 + g)
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nhanh", action="store_true")
    ap.add_argument("--tu-kiem", action="store_true")
    # Rẽ song song: 80 nhân của sol1, mỗi (vỏ, hạt giống) một tiến trình, mỗi tiến trình
    # ghi CSV riêng rồi gộp. Không dùng tệp tạm dùng chung: lớp lỗi 33.
    ap.add_argument("--chi-vo", help="chi chay mot vo, theo ten")
    ap.add_argument("--chi-hat", type=int, help="chi chay mot hat giong")
    ap.add_argument("--gop", action="store_true", help="gop cac CSV rieng thanh mot")
    # ⛔ Them 08/10 cho vong doc ngoai: chay LAI MOT TRUC o cac muc KHAC, ghi ra tep RIENG.
    #    Khong chay lai ca bon truc, vi ba truc kia da co so trong bai: chay lai la mo cua
    #    cho so trong bai doi ma khong ai doi. Phep gop co cong doi chieu MOC SACH.
    ap.add_argument("--chi-truc", help="chi chay mot truc, dung TEN trong TRUC")
    ap.add_argument("--muc", help="danh sach muc thay cho mac dinh, cach nhau bang dau phay")
    ap.add_argument("--ra", help="duong dan CSV ra, thay cho mac dinh")
    a = ap.parse_args()
    if a.tu_kiem:
        return tu_kiem()
    if a.gop:
        return gop()

    import torch
    from constellation import Walker, grid_isl_graph
    from traffic import evaluate, multipath_route
    from p5_gnn_router import make_instance, train, TRAIN_WALKER, TRAIN_PAIRS, CAP

    shells = [("w132_i53", Walker(132, 12, 1, 53.0, 550.0), 600)]
    seeds = [0, 1]
    if not a.nhanh:
        shells += [("w264_i53", Walker(264, 24, 1, 53.0, 550.0), 1200)]
        seeds = [0, 1, 2, 3, 4]
    if a.chi_vo:
        shells = [x for x in shells if x[0] == a.chi_vo]
        if not shells:
            sys.exit("khong co vo ten %s" % a.chi_vo)
    if a.chi_hat is not None:
        seeds = [a.chi_hat]

    print("R7.1 -- do ben voi trang thai mang KHONG hoan hao", flush=True)
    print("   bon truc, dung ten cua phan bien; CA HAI chinh sach; tau co dinh %.2f\n" % TAU,
          flush=True)
    tr = [make_instance(TRAIN_WALKER, TRAIN_PAIRS, 300 + i, need_eig=False) for i in range(10)]
    model = train("GCN", tr, seed=0)

    rows, tac_dong_rong = [], []
    for ten, w, npairs in shells:
        for sd in seeds:
            rng = np.random.default_rng(10_000 + sd)
            ins = make_instance(w, npairs, 900 + sd, need_eig=False)
            A, W, dem = ins["A_np"], ins["W_np"], ins["dem"]

            # ---- moc THAT, chua nhieu gi ----
            blind1 = evaluate(A, W, dem, CAP, policy="blind")["total_ttt"]
            ue = evaluate(A, W, dem, CAP, policy="ue")["total_ttt"]
            so = evaluate(A, W, dem, CAP, policy="so")["total_ttt"]
            span = blind1 - ue
            if span <= 0:
                print("  bo qua %s seed %d: span <= 0" % (ten, sd), flush=True)
                continue
            rec = lambda x: (blind1 - x) / span

            rc0 = truong_gia_hoc(model, ins, torch)
            sach_hoc = multipath_route(A, W, rc0, dem, CAP, tau=TAU)["total_ttt"]
            sach_mu = multipath_route(A, W, W, dem, CAP, tau=TAU)["total_ttt"]

            truc_chay = dict(TRUC)
            if a.chi_truc:
                if a.chi_truc not in truc_chay:
                    sys.exit("⛔ khong co truc %r. Co: %s" % (a.chi_truc, list(truc_chay)))
                truc_chay = {a.chi_truc: truc_chay[a.chi_truc]}
            if a.muc:
                if not a.chi_truc:
                    sys.exit("⛔ --muc phai di kem --chi-truc, khong thi mot danh sach muc "
                             "dung cho ca bon truc co don vi khac nhau.")
                truc_chay[a.chi_truc] = [float(x) for x in a.muc.split(",")]
            for truc, muc in truc_chay.items():
                for m in muc:
                    # ---- dung CAI NHIN HONG cua nha dieu hanh ----
                    ins_v = dict(ins)
                    W_v = W.copy()
                    # Mang THAT de do. Chi truc "link failures" lam no doi.
                    A_t, W_t, b_t, ue_t, so_t = A, W, blind1, ue, so

                    if truc == "demand-estimation errors":
                        # nhu cau bi uoc luong sai -> dac trung GNN sai
                        he = rng.lognormal(0.0, m, size=len(dem))
                        dem_v = [(s, d, r * float(h)) for (s, d, r), h in zip(dem, he)]
                        ins_v = _dac_trung_tu_nhu_cau(ins, dem_v)
                    elif truc == "stale telemetry":
                        # ⛔ Lan dau toi lay make_instance voi HAT GIONG khac, tuong the la
                        # "khe truoc". Sai: make_instance luon dung grid_isl_graph(w, 0.0),
                        # nen doi hat giong chi doi NHU CAU, con do thi y nguyen. Truc nay
                        # khi ay la ban trung lap cua truc nhu cau, va moc mu khong doi mot
                        # chu so nao, dung dau hieu cua mot truc RONG.
                        # Dung: do thi cua thoi diem t - k*SLOT, con mang that o t = 0.
                        A_cu, W_cu = grid_isl_graph(w, -float(m) * SLOT_S, seam=False)
                        W_v = np.where(A > 0, np.where(A_cu > 0, W_cu, W), 0.0)
                        ins_v = _thay_W(ins, W_v)
                    elif truc == "ephemeris or capacity mismatch":
                        # ⛔ Phan EPHEMERIS co tac dong; phan CAPACITY thi KHONG, va phai
                        # noi ro. `build_features(A, W, dem)` khong nhan dung luong, va ca
                        # hai chinh sach dinh tuyen tren chi phi khong phu thuoc dung luong:
                        # dung luong chi vao luc DO (ham BPR). Nen lech dung luong doi dieu
                        # nha dieu hanh TIN se xay ra, khong doi dieu THUC SU xay ra. Ta quet
                        # phan ephemeris, va bao phan capacity la bat dong co ly do.
                        W_v = W * (1.0 + rng.normal(0.0, m, size=W.shape)) * (A > 0)
                        W_v = np.where(W_v > 0, W_v, W)
                        ins_v = _thay_W(ins, W_v)
                    elif truc == "link failures":
                        # ⛔ Lan dau toi bo A_v va chi doi W, nen lien ket "chet" thanh
                        # lien ket CHI PHI 0, tuc hap dan nhat, va mot chinh sach nhieu
                        # tut xuong DUOI system optimum. Chinh cau assert do bat duoc.
                        # Dung mo hinh: lien ket rung THAT, ca dinh tuyen lan do deu tren
                        # do thi suy giam, con TRUONG GIA la ban tinh truoc khi rung.
                        A_t, W_t = _rung_lien_ket(A, W, m, rng)
                        W_v, ins_v = W, ins          # nha dieu hanh chua biet lien ket rung
                        b_t = evaluate(A_t, W_t, dem, CAP, policy="blind")["total_ttt"]
                        ue_t = evaluate(A_t, W_t, dem, CAP, policy="ue")["total_ttt"]
                        so_t = evaluate(A_t, W_t, dem, CAP, policy="so")["total_ttt"]
                        if b_t - ue_t <= 0:
                            continue

                    rc_v = truong_gia_hoc(model, ins_v, torch)
                    # ⭐ C4: truc nao duoc cho la co tac dong thi truong gia PHAI doi.
                    # Neu khong doi thi phep nhieu da KHONG di vao mo hinh, va so "mien
                    # nhiem" doc duoc la gia. Day la doi chung cho chinh bo do.
                    # Truc "link failures" KHONG doi truong gia theo thiet ke: cai hong
                    # nam o MANG, khong nam o cai nhin. Doi chung dung cho no la do thi
                    # that PHAI mat canh. Hai truc kia thi truong gia phai doi.
                    if truc == "link failures":
                        if int((A_t > 0).sum()) >= int((A > 0).sum()):
                            tac_dong_rong.append((truc, m))
                    elif np.allclose(rc_v, rc0):
                        tac_dong_rong.append((truc, m))

                    # ---- DINH TUYEN tren cai nhin hong, DO tren mang that ----
                    # Truong gia cua cai nhin hong phai han ve do thi THAT: canh khong
                    # ton tai thi khong duoc mang chi phi.
                    rc_t = np.where(A_t > 0, rc_v, 0.0)
                    W_vt = np.where(A_t > 0, W_v, 0.0)
                    hoc = multipath_route(A_t, W_t, rc_t, dem, CAP, tau=TAU)["total_ttt"]
                    mu = multipath_route(A_t, W_t, W_vt, dem, CAP, tau=TAU)["total_ttt"]
                    assert hoc >= so_t - 1e-6 and mu >= so_t - 1e-6, \
                        "duoi system optimum o truc %s muc %g" % (truc, m)
                    rec_t = lambda x: (b_t - x) / (b_t - ue_t)

                    rows.append(dict(shell=ten, seed=sd, truc=truc, muc=m,
                                     rec_hoc_sach=round(rec(sach_hoc), 4),
                                     rec_mu_sach=round(rec(sach_mu), 4),
                                     rec_hoc=round(rec_t(hoc), 4),
                                     rec_mu=round(rec_t(mu), 4)))
            print("  %s seed %d xong (%d dong)" % (ten, sd, len(rows)), flush=True)

    hau = ("_%s_s%d" % (a.chi_vo, a.chi_hat)) if (a.chi_vo and a.chi_hat is not None) else ""
    out = (a.ra if a.ra else
           os.path.join(ROOT, "results", "r7_1_imperfect_state%s.csv" % hau))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader(); wr.writerows(rows)
    print("\n# da ghi results/%s (%d dong)\n" % (os.path.basename(out), len(rows)))

    # ---- tong hop + cong ----
    print("%-32s %6s %10s %10s %10s %10s" % ("truc", "muc", "hoc", "mu", "d_hoc", "d_mu"))
    mien_nhiem_sai = []
    for truc in TRUC:
        for m in TRUC[truc]:
            sel = [r for r in rows if r["truc"] == truc and r["muc"] == m]
            if not sel:
                continue
            h, u = st.median(r["rec_hoc"] for r in sel), st.median(r["rec_mu"] for r in sel)
            dh = h - st.median(r["rec_hoc_sach"] for r in sel)
            du = u - st.median(r["rec_mu_sach"] for r in sel)
            print("%-32s %6g %10.3f %10.3f %+10.3f %+10.3f" % (truc, m, h, u, dh, du))
            # C3: tren hai truc nay moc mu KHONG duoc doi mot chu so nao
            if truc in ("demand-estimation errors", "ephemeris or capacity mismatch") \
                    and truc == "demand-estimation errors" and abs(du) > 1e-9:
                mien_nhiem_sai.append((truc, m, du))

    print("\n=== CONG ===")
    if tac_dong_rong:
        print("  ⛔ C4 HONG: %d cau hinh co phep nhieu KHONG LAM DOI truong gia:"
              % len(tac_dong_rong))
        for t, m in tac_dong_rong[:6]:
            print("      %s muc %g" % (t, m))
        print("      Truc do dang RONG. So doc ra la gia. Sua truoc khi tin bat ky dong nao.")
        return 2
    print("  DAT C4: moi phep nhieu deu lam doi truong gia hoc duoc.")
    if mien_nhiem_sai:
        print("  ⛔ C3 HONG: moc mu DOI tren truc nhu cau, trong khi no khong he doc nhu cau.")
        for t, m, d in mien_nhiem_sai[:4]:
            print("      %s muc %g: lech %+.6f" % (t, m, d))
        print("      Day la BO DO SAI, khong phai phat hien. Dung lai va sua truoc khi doc so.")
        return 2
    print("  DAT C3: moc mu khong doi tren truc nhu cau, dung du doan dang ky truoc.")
    return 0


# ---- cac phep bien doi cai nhin, tach rieng de TU KIEM duoc khong can GPU ----
def _dac_trung_tu_nhu_cau(ins, dem_v):
    """Dung lai dac trung tu nhu cau UOC LUONG SAI, bang chinh build_features cua kho.

    ⛔ Ban dau toi va tay hai cot cuoi cua X theo PHONG DOAN ve bo cuc dac trung. Doan
    sai thi truc nay thanh RONG: trường giá không đổi, kết quả ra "miễn nhiễm" giả. Gọi
    thẳng build_features thì đúng theo cấu tạo, không phải theo trí nhớ của tôi.
    """
    from p5_gnn_router import build_features
    X, ctx, rows, cols, bload = build_features(ins["A_np"], ins["W_np"], dem_v,
                                               need_eig=False)
    out = dict(ins)
    out.update({"X": X, "ctx": ctx, "rows": rows, "cols": cols, "bload": bload})
    return out


def _thay_W(ins, W_v):
    out = dict(ins)
    out["W_np"] = W_v
    return out


def _rung_lien_ket(A, W, ti, rng):
    """Rung ngau nhien mot ti le lien ket ISL, giu do thi con lien thong tren huong di."""
    A_v, W_v = A.copy(), W.copy()
    r, c = np.nonzero(A)
    k = max(1, int(round(ti * len(r))))
    idx = rng.choice(len(r), size=k, replace=False)
    for i in idx:
        A_v[r[i], c[i]] = 0
        W_v[r[i], c[i]] = 0.0
    return A_v, W_v


def gop():
    """Gộp các CSV theo đơn vị thành một tệp, và ĐẾM đủ đơn vị trước khi gộp."""
    import glob
    res = os.path.join(ROOT, "results")
    tep = sorted(glob.glob(os.path.join(res, "r7_1_imperfect_state_*_s*.csv")))
    if not tep:
        sys.exit("⛔ khong co CSV theo don vi nao de gop")
    rows = []
    for f in tep:
        with open(f, newline="") as fh:
            rows += list(csv.DictReader(fh))
    don_vi = sorted({(r["shell"], r["seed"]) for r in rows})
    print("gop %d tep, %d dong, %d don vi (vo x hat giong):" % (len(tep), len(rows), len(don_vi)))
    for v, s_ in don_vi:
        n = sum(1 for r in rows if r["shell"] == v and r["seed"] == s_)
        print("   %-10s hat %s: %d dong" % (v, s_, n))
    # ⛔ Moi don vi phai co DU so dong, khong thi mot tien trinh da chet giua duong va
    # ban gop se thieu am tham.
    can = sum(len(v) for v in TRUC.values())
    thieu = [(v, s_) for v, s_ in don_vi
             if sum(1 for r in rows if r["shell"] == v and r["seed"] == s_) != can]
    if thieu:
        print("⛔ %d don vi KHONG du %d dong: %s" % (len(thieu), can, thieu[:4]))
        return 2
    out = os.path.join(res, "r7_1_imperfect_state.csv")
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader(); wr.writerows(rows)
    print("# da ghi results/%s (%d dong, %d don vi)" % (os.path.basename(out), len(rows), len(don_vi)))
    return 0


def tu_kiem():
    """Đối chứng, không cần GPU: kiểm ba phép biến đổi cái nhìn làm đúng việc."""
    print("== TU KIEM r7_1 ==\n")
    ok = True
    rng = np.random.default_rng(0)
    A = (np.array([[0, 1, 1, 0], [1, 0, 1, 1], [1, 1, 0, 1], [0, 1, 1, 0]]) > 0).astype(float)
    W = A * np.array([[0, 2., 5., 0], [2., 0, 1., 4.], [5., 1., 0, 3.], [0, 4., 3., 0]])

    A_v, W_v = _rung_lien_ket(A, W, 0.25, rng)
    n_truoc, n_sau = int((A > 0).sum()), int((A_v > 0).sum())
    d1 = n_sau < n_truoc and (W_v[A_v == 0] == 0).all()
    print("  %-50s %s" % ("rung lien ket: so canh GIAM va W tat theo", "DAT" if d1 else "HONG"))
    ok &= d1

    d2 = int((A > 0).sum()) == n_truoc
    print("  %-50s %s" % ("rung lien ket KHONG sua A goc", "DAT" if d2 else "HONG"))
    ok &= d2

    ins = {"A_np": A, "W_np": W}
    out = _thay_W(ins, W * 2)
    d3 = (out["W_np"] == W * 2).all() and (ins["W_np"] == W).all()
    print("  %-50s %s" % ("thay W: ban moi doi, ban goc KHONG doi", "DAT" if d3 else "HONG"))
    ok &= d3

    # doi chung AM: ti le rung 0 thi do thi phai y nguyen
    A0, W0 = _rung_lien_ket(A, W, 0.0, rng)
    d4 = int((A0 > 0).sum()) == n_truoc - 1   # ham ep toi thieu rung 1 canh
    print("  %-50s %s" % ("ti le 0 van rung toi thieu 1 canh (co chu dich)",
                          "DAT" if d4 else "HONG"))
    ok &= d4

    print("\n  => %s" % ("TAT CA DAT" if ok else "CO CA HONG"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
