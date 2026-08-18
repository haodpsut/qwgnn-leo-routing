# KILL-FIRST ledger — TNSM resubmission (Learning to Route Under Load → A Reality Check)

Ghi lại các phép **giết-trước** đã chạy, theo thứ tự sức-giết trên chi phí. Vòng này đặc biệt ở
chỗ nó bắt đầu **sau** một lần reject, nên vài phép giết đã chạy trong chính vòng phản biện.

---

## 1. Venue: danh sách **out-of-scope** đọc nguyên văn

TNSM (IEEE Trans. on Network and Service Management), Aims & Scope đọc ngày 17/08/2026.
Phạm vi: *management of networks, systems and services*, gồm traffic engineering, orchestration,
network automation và AI/ML cho quản lý mạng.

**Không có mục loại trừ nào chạm bài này.** Bài là traffic engineering trên mạng vệ tinh, đúng
lõi phạm vi. Đối chiếu với ca **ISJ desk-reject** (bài QKD, 06/08): ở đó danh sách loại trừ nói
rõ *máy phát cộng máy thu là MỘT hệ thống, ngoài phạm vi*, và đọc nó tốn năm phút trong khi phát
hiện ra thì đã chạy trọn pipeline. Ở đây đã đọc trước.

Thêm một bằng chứng mạnh hơn mọi suy luận: **chính TNSM đã mời nộp lại** bài này
(*"you may submit a new manuscript"*), nên câu hỏi phạm vi đã được ban biên tập trả lời.

## 2. Venue: mô hình **OA** đọc từ bảng APC của nhà xuất bản

Ràng buộc thường trực của Hảo: **không gold OA**.

Đọc cột **OA Pub Type** trong bảng APC của IEEE, không suy từ tên tạp chí. TNSM là
**hybrid (Transactions)**, không phải fully-open. Nộp đường thường **không mất phí**.

⚠ Bẫy đã ghi trong sổ: trong 157 tạp chí IEEE thuộc danh mục NAFOSTED, đúng **6** cái là gold OA,
và bốn cái có tên nghe rất bình thường (TNSRE, TQE, **JSTARS**, IEEE Photonics Journal). Tên tạp
chí không tiết lộ mô hình. Đã đọc cột, không đoán.

## 3. **Hard gate** cho từng claim

Mỗi tuyên bố phải sống sót qua phép thử của chính nó **trước** khi viết:

| tuyên bố | phép thử rẻ | kết quả |
|---|---|---|
| khoảng cách headline là thật | ép dung lượng cứng, đo lại bằng tỉ lệ giao gói | **SỐNG nhưng co**: 80,5% → 29,8% |
| hơn baseline rẻ | blind multipath, quét ε, ngân sách khớp | **CHẾT ngoài phân phối**, sống trong phân phối |
| chuyển giao quy nạp | quét τ + blind ở vỏ 1584 | **CHẾT**: blind đạt 0,994 so với 0,980 |
| chủ động dưới hotspot trôi | so với blind ở mọi mức trôi | **CHẾT ngoài phân phối**, 0/3 mọi mức |
| tăng tốc 29× | MSA khởi động ấm | **CO**: còn 2–9× |
| Mệnh đề 1 chứng thực số nào | đặt số vào `c₁H` | **RỖNG** ở mọi điểm vận hành |

Bốn tuyên bố chết trước khi viết chứ không phải sau khi phản biện đọc. Đó là điểm của mục này.

## 4. **Effects inventory (DC-5)**: hiệu ứng vật lý bị bỏ

Kiểm kê các hiệu ứng mô hình **không** có, và tác động ước lượng:

| hiệu ứng vắng mặt | hệ quả |
|---|---|
| hàng đợi và động lực gói | mô hình là **mức luồng**; BPR thay cho trễ hàng đợi |
| mất gói khi quá tải | đã thêm ở mục VI-G: ba mô hình mất gói, kết quả 29,8 / 37,0 / 37,3% |
| dung lượng liên kết không đồng nhất | dung lượng đồng nhất; chưa mô hình |
| cắt liên kết vùng cực | chỉ **1 trên 5** vỏ có độ nghiêng kích hoạt nó |
| lỗi ước lượng nhu cầu | biến thể chủ động dùng dự báo **đã biết**, không phải dự báo học được |

⚠ Chính DC-5 đã giết tiền đề của bản v1: hàm BPR mũ bốn được đánh giá ở `v/c = 9`, nơi liên kết
gói **không thể** hoạt động. Đó là hiệu ứng vắng mặt, và không cổng nội bộ nào nhìn thấy nó.

## 5. Đọc ngoài **CLAIM SHEET**

CLAIM-SHEET-READ: 18/08/2026 external-reviewer -- đọc trọn bản thảo và trả về 30 ý; bốn ý làm
đổi kết luận: (a) vỏ 1584 thiếu cả quét τ lẫn baseline blind, (b) tăng tốc đo với MSA khởi động
lạnh, (c) hàng proactive 0,737/0,984 phủ định chính đóng góp mà không câu nào nhắc, (d) thước
recovered-fraction bão hoà khi baseline mù bệnh hoạn. Bốn ý đều đã đo lại và viết vào bài.

CLAIM-SHEET-READ: 16/08/2026 TNSM-reviewer-3 -- chỉ ra hàm chi phí đánh giá ngoài miền hợp lệ và
đặc trưng cần trọn ma trận nhu cầu. Cả hai đúng, cả hai đã sửa.

## 6. **Luật 8a**: margin vs fidelity budget (biên tuyên bố so với ngân sách sai số)

| | |
|---|---|
| biên tuyên bố chính | hiệu ghép cặp `0,310` trong phân phối |
| bất định ước lượng | `sd` giữa các lượt chạy `0,020`; giữa hai máy tới `0,036` |
| hiệu ứng chưa mô hình (DC-5) | mất gói đã lượng hoá: đổi `80,5%` thành `29,8%` |
| **kết luận** | biên trong phân phối **vượt** ngân sách một bậc; biên **ngoài** phân phối (`0,002`–`0,020`) **không vượt**, nên bài báo là **ngang bằng** chứ không phải lợi thế |

Đó chính là lý do bài đổi khung từ "đề xuất phương pháp" sang "đo một ranh giới": biên chỉ đủ
lớn ở một nửa miền, và bài chỉ được phép tuyên bố ở nửa đó.

## Ghi chú về claim scope

`paper/claim-scope.json` khai `superlatives` và `exclusivity` theo lược đồ của
`check_claim_scope.py`. Mục `mechanisms` **bỏ có chủ ý**: cổng so hai dòng đơn, tuyên bố của bài
là trung vị trên tám đơn vị, ép vào sẽ kiểm một thứ yếu hơn điều bài nói.
