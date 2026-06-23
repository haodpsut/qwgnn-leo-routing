# PLAN — QW-GNN LEO Routing paper

Repo dự kiến: `haodpsut/qwgnn-leo-routing`. Venue: IEEE TNSM (chính), TWC (stretch).
Nguyên tắc: param-matched, multi-seed, báo cáo trung thực cả khi không thắng.

---

## Giai đoạn & cổng kill

### P0 — Smoke kill-test trụ 1  ✅ ĐÃ XONG
- `smoke/` torus tổng hợp, QW vs Heat vs GCN param-matched.
- Kết quả: QW thắng 12/12 ô, giảm lỗi node-xa ~52%, gap tuyệt đối nở theo đường
  kính (+0.07 hop/hop). **GO.** Caveat `|.|` để xử lý ở P2 bằng control.

### P1 — Pipeline Hypatia (dữ liệu thật)
- Cài Hypatia (Kassing et al., SIGCOMM'20) + ns-3 backend, hoặc StarPerf nếu
  Hypatia kẹt build trên Windows (nhiều khả năng phải chạy trong WSL/Linux).
- Sinh topology theo thời gian cho 1 shell Starlink (53°, 1584 sat, 72×22) +
  1 shell nhỏ (vd Iridium-like 66 sat) cho OOD.
- Xuất chuỗi `{G_t, W_t}`: ma trận kề + trọng số delay theo slot (vd 1 s),
  cộng mô hình traffic (gravity / uniform) để có congestion term + ground-truth
  end-to-end delay/throughput/loss.
- **Artefact:** `data/` bộ snapshot graph + nhãn `phi_t^d` (BFS/Dijkstra) +
  packet-level metrics để eval hệ thống.
- **Cổng kill P1:** lặp lại tín hiệu trụ 1 trên graph Hypatia thật (QW > Heat ở
  node xa, gap nở theo quy mô shell). Nếu KHÔNG lặp lại → bỏ trụ 1, chuyển sang
  paper "proactive + inductive GNN" thuần (vẫn đủ bài).

### P2 — Mô hình + baseline + control
- Chuyển QW-prop sang **Chebyshev degree-M** (localized, O(M|E|)) thay expm dày.
- Baselines (param-matched): GCN, GAT, GraphSAGE, Heat, **complex-diffusion
  control**, **abs-only Heat control**, **deep-GCN (depth = đường kính)**.
- Baselines phi-GNN: Dijkstra (delay & hop), một DRL-routing (vd DRL-OR / DQN
  routing), shortest-path oblivious.
- **Cổng kill P2:** complex-diffusion control phải KÉM hơn QW thật → mới chứng
  minh "ballistic phase" làm việc thật, không phải chỉ "complex capacity".

### P3 — Ba trụ trên dữ liệu thật
- Trụ 1: far-node MAE phi + slope theo đường kính, đa seed, stratified.
- Trụ 2 (proactive): so reactive (chỉ `G_t`) vs proactive (dùng `G_{t+h}` đã biết)
  qua các seam/handover event → delay/loss sau handover, route churn.
- Trụ 3 (scale-invariance): train shell nhỏ → zero-shot shell Starlink; đo margin
  vs baseline theo mức tăng đường kính. Kèm inference latency (routing real-time).
- Metrics hệ thống: end-to-end delay, throughput, packet loss, queue stability,
  route stability, thời gian inference.

### P4 — Figures + viết
- Figures TikZ/CSV (theo house style): kiến trúc QW-GNN, ballistic-vs-diffusive
  illustration, far-MAE vs diameter, proactive delay-CDF, OOD scaling curve,
  ablation bar.
- Viết theo transaction-architect: formulation chặt + định lý cận receptive-field
  (nếu đẩy TWC), bảng ablation đầy đủ, response-letter-ready.
- Tuân thủ: không em-dash/en-dash; comment code tiếng Anh; verify figure bằng PNG.

## Cấu trúc repo dự kiến
```
qwgnn-leo-routing/
  smoke/            # P0 (đã có, sẽ copy từ ntn-paper-01/smoke)
  sim/              # Hypatia/StarPerf wrappers, ephemeris -> graph sequence
  data/             # snapshots + labels (gitignored, script tái tạo)
  models/           # gcn, gat, sage, heat, complexdiff, qw (Chebyshev)
  experiments/      # P1..P3 runners, configs, seeds
  results/          # csv
  paper/            # main.tex, figs, make_figs_data.py
  FORMULATION.md PLAN.md README.md
```

## Rủi ro & dự phòng
- Hypatia build trên Windows khó → dùng WSL/Linux hoặc StarPerf (Python thuần).
- QW không lặp lại trên graph thật (topology Starlink gần lưới đều, đường kính
  ~vài chục) → fallback paper proactive+inductive GNN.
- Chebyshev xấp xỉ U(tau) mất hiệu ứng ballistic ở M nhỏ → quét M, báo cáo
  trade-off chính xác/chi phí.
- DRL-routing baseline tốn công train → ưu tiên một baseline DRL chuẩn, không sa đà.

## Mốc quyết định gần nhất
1. Dựng `sim/` + tái tạo tín hiệu trụ 1 trên 1 shell Hypatia (cổng kill P1).
2. Nếu PASS → P2 control complex-diffusion (cổng kill P2). Hai cổng này quyết
   định paper đi tiếp dạng QW hay pivot proactive-GNN.
