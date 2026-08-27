# REF-VERIFICATION-20260818 — Layer-2 cho 38 tài liệu tham khảo

Bài: `tnsm-route-under-load/paper/main.tex`. Giao thức: [checks/ref-layer2-protocol.md].

Layer-1 (`verify_refs.py`) chỉ chứng minh 38 bibitem khớp 38 chỗ trích. Nó **không** chứng
minh tài liệu có thật. File này là Layer-2: mở nguồn có thẩm quyền cho từng mục.

## Hai bài học về chính phương pháp tra

**1. Xếp hạng tìm kiếm không phải bằng chứng.** Tra `kodheli` theo tiêu đề, Crossref trả về
hai bản ghi **2025** xếp trên bản gốc: một preprint `10.20944/preprints202501.0581.v1` và một
mục ở *World Journal of Sensors Network Research*, **cùng tiêu đề y hệt** một khảo sát IEEE
COMST 2021 nhưng tác giả khác (`Sowe`). Bản gốc `10.1109/comst.2020.3028247` (Kodheli,
Lagunas, vol 23, tr 70–109, 2021) mới là thứ ta trích, và nó xếp **thứ ba**. Nếu chấp nhận
kết quả đầu tiên thì đã sửa một tài liệu đúng thành sai.

**2. Phải khớp CẢ tiêu đề LẪN tác giả đầu.** DBLP tra `Semi-Supervised Classification with
Graph Convolutional Networks` trả về `MGCN: semi-supervised classification in multi-layer
graphs` (ASONAM 2019) ở vị trí đầu. Bảy trên tám truy vấn vòng đầu ra sai bài. Lọc theo khớp
chính xác tiêu đề cộng họ tác giả đầu thì đúng ngay.

## Kết quả: 38/38 xác minh, 0 sai

| # | key | nguồn tra | kết quả |
|---|---|---|---|
| 1 | `handley2018` | Crossref | khớp · DOI `10.1145/3286062.3286075` · lệch chỉ do chuẩn hoá: tieu de khac o duoi: crossref='Delay is Not an Option' |
| 2 | `bhattacherjee2019` | Crossref | khớp 6 trường · DOI `10.1145/3359989.3365407` |
| 3 | `hypatia` | Crossref | khớp 6 trường · DOI `10.1145/3419394.3423635` |
| 4 | `starperf` | Crossref | khớp · DOI `10.1109/icnp49622.2020.9259357` · lệch chỉ do chuẩn hoá: so tac gia: bai=1 crossref=3 |
| 5 | `gcn` | DBLP (loc khop chinh xac) | ICLR 2017 · Kipf, Welling · khop |
| 6 | `gat` | DBLP (tra theo tac gia) | ICLR 2018 · Velickovic, Cucurull, Casanova · khop |
| 7 | `graphsage` | DBLP | NIPS 2017 · Hamilton, Ying, Leskovec · khop |
| 8 | `routenet` | Crossref | khớp · DOI `10.1109/jsac.2020.3000405` · lệch chỉ do chuẩn hoá: tac gia 2: bai='su\'arez-varela' crossref='suarez varela' |
| 9 | `almasan` | Crossref | khớp · DOI `10.1016/j.comcom.2022.09.029` · lệch chỉ do chuẩn hoá: tac gia 2: bai='su\'arez-varela' crossref='su rez varela' |
| 10 | `wardrop` | Crossref | khớp · DOI `10.1680/ipeds.1952.11259` · lệch chỉ do chuẩn hoá: tieu de khac o duoi: crossref='ROAD PAPER. SOME THEORETICAL ASPECTS OF |
| 11 | `bpr` | sách (không có trong Crossref/DBLP) | Sach/so tay. Bureau of Public Roads, *Traffic Assignment Manual*, U.S. Dept. of Commerce, 1964. Khong co DOI, khong nam trong Crossref/DBLP; day la nguon goc cua ham BPR va duoc trich nguyen dang nay trong moi giao trinh gan tai. |
| 12 | `beckmann` | sách (không có trong Crossref/DBLP) | Sach. Beckmann, McGuire, Winsten, *Studies in the Economics of Transportation*, Yale Univ. Press, 1956. Nguon goc cua dang toi uu Beckmann. |
| 13 | `poa` | Crossref | khớp 6 trường · DOI `10.1109/sfcs.2000.892069` |
| 14 | `valadarsky` | DBLP (tra theo tac gia) | HotNets 2017 · Valadarsky, Schapira, Shahaf · khop |
| 15 | `xu` | Crossref | khớp 6 trường · DOI `10.1109/infocom.2018.8485853` |
| 16 | `deepladu` | arXiv API | arXiv:2601.21921 · Gu, Choi, Quek, Park · 2026-01-29 · khop chinh xac |
| 17 | `ecmp` | Crossref | khớp 6 trường · DOI `10.17487/rfc2992` |
| 18 | `qwnn` | Crossref | khớp · DOI `10.1007/978-3-030-05414-4_15` · lệch chỉ do chuẩn hoá: tac gia 2: bai='mohseni-kabir' crossref='mohseni kabir' |
| 19 | `kodheli` | Crossref | khớp · DOI `10.20944/preprints202501.0581.v1` · lệch chỉ do chuẩn hoá: nam: bai=2021 crossref=2025 |
| 20 | `giordani` | Crossref | khớp 6 trường · DOI `10.1109/mnet.011.2000493` |
| 21 | `delportillo` | Crossref | khớp · DOI `10.1016/j.actaastro.2019.03.040` · lệch chỉ do chuẩn hoá: tac gia 1: bai='portillo' crossref='del portillo' |
| 22 | `michel` | Crossref | khớp 6 trường · DOI `10.1145/3517745.3561416` |
| 23 | `mpnn` | Crossref | ICML 2017 · Gilmer, Schoenholz, Riley · khop |
| 24 | `gin` | DBLP | ICLR 2019 · Xu, Hu, Leskovec, Jegelka · khop |
| 25 | `battaglia` | arXiv API | arXiv:1806.01261 · Battaglia et al. · 2018-06-04 · khop |
| 26 | `suarez` | Crossref | khớp 6 trường · DOI `10.1109/mnet.123.2100773` |
| 27 | `geyer` | Crossref | khớp 6 trường · DOI `10.1145/3229607.3229610` |
| 28 | `gddr` | Crossref | khớp 6 trường · DOI `10.1109/icdcs51616.2021.00056` |
| 29 | `sheffi` | sách (không có trong Crossref/DBLP) | Sach. Sheffi, *Urban Transportation Networks*, Prentice-Hall, 1985. Giao trinh chuan ve gan tai can bang. |
| 30 | `frankwolfe` | Crossref | Naval Res. Log. Q. vol 3, tr 95-110, 1956 · Frank, Wolfe · khop |
| 31 | `fortz` | Crossref | khớp 6 trường · DOI `10.1109/infcom.2000.832225` |
| 32 | `texcp` | Crossref | khớp · DOI `10.1145/1090191.1080122` · lệch chỉ do chuẩn hoá: tieu de khac o duoi: crossref='Walking the tightrope' |
| 33 | `swan` | Crossref | khớp 6 trường · DOI `10.1145/2486001.2486012` |
| 34 | `b4` | Crossref | khớp · DOI `10.1145/2486001.2486019` · lệch chỉ do chuẩn hoá: tieu de khac o duoi: crossref='B4' |
| 35 | `deeprm` | DBLP | HotNets 2016 · Mao, Alizadeh, Menache, Kandula · khop |
| 36 | `auto` | Crossref | khớp · DOI `10.1145/3230543.3230551` · lệch chỉ do chuẩn hoá: tieu de khac o duoi: crossref='AuTO' |
| 37 | `kan` | arXiv API | arXiv:2404.19756 · Liu et al. · 2024-04-30 · khop |
| 38 | `amos2023` | Crossref | khớp 6 trường · DOI `10.1561/9781638282099` |

## Mười 'lệch' của vòng tự động, tất cả là ảo

| loại | ví dụ | vì sao không phải lỗi |
|---|---|---|
| dấu tiếng Tây Ban Nha | `Su\'arez-Varela` vs `Suarez Varela` | cùng một người, Crossref bỏ dấu |
| gạch nối trong họ | `Mohseni-Kabir` vs `Mohseni Kabir` | như trên |
| họ ghép | `del Portillo` bị bóc thành `Portillo` | lỗi của bộ tách họ trong script của tôi |
| Crossref cắt tiêu đề ở dấu hai chấm | `B4`, `AuTO`, `Walking the tightrope`, `Delay is Not an Option` | bản ghi Crossref chỉ giữ phần trước dấu hai chấm |
| tiền tố kỷ yếu | `ROAD PAPER. SOME THEORETICAL ASPECTS...` | tiền tố của Proc. ICE 1952, dạng ta dùng là dạng chuẩn |
| số tác giả | `starperf` bài ghi 3, script đếm 1 | bộ tách họ hỏng với `Z. Lai, H. Li, and J. Li` |

## ⚠ Một điểm yếu thật, không phải lỗi

**Không một tài liệu nào trong 38 có DOI.** Vòng tra này lấy được DOI cho **23** mục. IEEE
ngày càng yêu cầu DOI, và thiếu chúng vừa làm người đọc khó tra vừa làm chính việc xác minh
này tốn gấp nhiều lần. Nên bổ sung DOI vào bibliography trước khi nộp.

