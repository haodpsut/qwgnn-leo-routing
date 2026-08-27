# Xuất xứ của mọi con số trong `results/`

**Máy đo: `sol1.swin.edu.vn`, Xeon Gold 6148, 80 nhân, Linux-x86_64.**
Ngày chạy lại toàn bộ: **27/08/2026**.

## Vì sao ghi rõ máy

Cùng script, cùng seed, lời giải MSA ở vỏ 1584 cho `UE = 11391,6` trên máy này và
`11141,3` trên một máy khác, **lệch 2,20%**, mà phần đó không đụng tới torch một dòng
nào. Bản trước của bài khai rằng *"every quantity avoiding the network agreed to the
printed digit"*; lời khai đó **sai**. `results/figures/fig_host_delta.pdf` vẽ phân phối
đầy đủ của độ lệch giữa hai máy.

⇒ **Mọi số của bài phải đến từ một máy.** Kết quả ở đây đều từ `sol1`.

## Cách chạy lại

```bash
python run_all.py                        # 28 thí nghiệm song song + 5 chạy riêng
python experiments/r5_4_shell1584_uefree.py --seeds 0 1 2
python experiments/make_claims.py        # macro + hai cột dẫn xuất
python experiments/make_figs_tables.py   # 11 bảng/hình LaTeX
python experiments/make_r5_figs.py       # 7 hình PDF theo stylesheet chuẩn
```

Hai bước cuối là **định dạng thuần** từ CSV, không tính toán mô phỏng, nên chạy ở đâu
cũng cho kết quả như nhau.

## ⛔ Vỏ 1584 không có tham chiếu cân bằng

`results/r5_0_msa_ladder_1584.csv` và `r5_3_convergence_small.csv` ghi giá của vô chính
phủ `PoA = TTT_UE / TTT_SO` theo số vòng MSA. Giá trị dưới 1 là **không thể xảy ra** và
đánh dấu lời giải chưa hội tụ:

| vỏ | 20 | 40 | 80 | 160 | 320 | 640 |
|---|---|---|---|---|---|---|
| 132 | **1,0265** | 1,0325 | 1,0355 | 1,0371 | 1,0379 | 1,0384 |
| 264 | 0,9976 | **1,0060** | 1,0115 | 1,0148 | 1,0166 | 1,0176 |
| 1584 | 0,7697 | 0,8872 | 0,9490 | 0,9729 | 0,9844 | — |

Khoảng cách tới 1 ở vỏ 1584 co hệ số ~0,55 mỗi lần gấp đôi số vòng, nên đạt `PoA > 0,995`
cần **hơn 2500 vòng** (~10 giờ mỗi lời giải) và vẫn dưới 1.

⇒ Bài **không** báo cáo đại lượng nào chia cho UE ở vỏ 1584. Thay vào đó dùng
`r5_4_shell1584_uefree.csv`: tỉ số so với blind, thứ hạng, và thời gian suy diễn.

## Thư mục `paper-v1-REJECTED-2026-08-16/`

Bản thảo **đã bị từ chối** 16/08/2026, giữ để đối chiếu lịch sử. Đừng dựng, đừng sửa.
Bản đang dùng nằm ngoài kho này.
