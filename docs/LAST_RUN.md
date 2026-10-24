# Lần chạy gần nhất – 25/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/model_*_report.json` và `models_metrics.json` (chạy trên cụm).

## Yêu cầu
Trả lời 3 câu hỏi của bước 06:
1. Mở rộng lưới ALS implicit một lần: alpha {0,25; 0,5}, rank 128, giữ regParam 0,1. Rank 128 phải hơn rank 64 ít nhất 0,003 NDCG@10 trên val mới được chọn.
2. Phương án (b) có chỉnh: 2 vị trí cuối của top 10 trong `recs_final` dành cho content, chỉ lấy món user chưa nấu.
   - Một vị trí xếp theo sim × log1p(lượt nấu trong lịch sử).
   - Một vị trí ưu tiên món có ít hoặc không có tương tác.
   - Lý do gợi ý: "giống món X bạn đã nấu".
   - Bảng đánh giá báo cả hai phiên bản.
3. Dashboard dùng k = 8; report ghi đủ k = 3, 8, 11.

Sau đó chạy lại 06b và 06f trên cụm, cập nhật `models_metrics.json`, D13, LAST_RUN, rồi chạy `/handoff`. Việc tiếp theo là bước 07 theo kiểu thiết kế trước.

## Đã làm
- **`06b_als.py`:**
  - Lưới alpha {0,25; 0,5; 1; 5; 20; 40}, rank {32, 64, 128}, regParam cố định 0,1.
  - Thêm luật `RANK_MIN_GAIN = 0,003`: rank 128 chỉ được chọn nếu hơn rank 64 ít nhất 0,003. Luật đã chạy đúng ở cả hai chiều: ở local (chênh 0,0029) giữ rank 64; trên cụm (chênh 0,0032) chọn rank 128.
- **`06f_hybrid.py`:** thêm hàm `content_slots()` tạo phiên bản `hybrid_c2`, cách làm chi tiết trong mục "Số liệu chính".
  - `hybrid_c2` được đánh giá đủ như các mô hình khác: bảng chính, biến thể khám phá, coverage, novelty, diversity, khoảng tin cậy so với hybrid, và recall món mới.
  - `recs_final` giờ lấy từ `hybrid_c2`.
  - Lý do của vị trí content là món đã nấu giống nhất (tra `item_sim`); không có thì ghi "bạn đã xem".
- **`06e_kmeans.py`:** `user_clusters` có cột `cluster_k3`, `cluster_k8`, `cluster_k11`. `cluster_profile` có hồ sơ cho 3 giá trị k. `/data/models/kmeans` là model k = 8. Report có thêm `summary_k` và `dashboard_k`.
  - Bạn chỉ dặn chạy lại 06b và 06f, nhưng muốn dashboard dùng k = 8 và có hồ sơ cho k = 11 thì 06e cũng phải chạy lại (315 giây).
- Cả 3 file đều chạy `--local` trước, rồi chạy trên cụm theo thứ tự 06b → 06f → 06e. Tất cả thành công.
- Đã cập nhật D13 (phần "Bổ sung 25/10"), DATA_DICTIONARY (`hybrid_c2`, cột cluster, `recs_final`) và PROGRESS. Việc tiếp theo trong PROGRESS là thiết kế bước 07.

## Số liệu chính
**1. Lưới ALS implicit (val, mẫu 10.000 user, NDCG@10):**
| alpha (rank 32) | 0,25 | 0,5 | **1** | 5 | 20 | 40 |
|---|---|---|---|---|---|---|
| NDCG@10 | 0,1433 | 0,1485 | **0,1541** | 0,1506 | 0,1118 | 0,0808 |

| rank (alpha 1) | 32 | 64 | **128** |
|---|---|---|---|
| NDCG@10 | 0,1541 | 0,1591 | **0,1623** |

- Alpha 1 là đỉnh thật, không còn nằm ở biên lưới.
- Rank 128 hơn rank 64 0,0032, đạt ngưỡng 0,003, nên chọn **rank 128**. Rank vẫn ở biên trên, nhưng theo yêu cầu không mở rộng thêm.
- Độ nhạy trọng số implicit: 1/3/5 → 0,1623; 1/2/10 → 0,1620; chỉ cook → 0,1328.
- Thời gian dò ALS trên cụm tăng từ 870 lên 1.973 giây vì có rank 128.

**2. Hybrid và hybrid + content 2 vị trí (test, cùng 39.012 user):**

Cách làm `hybrid_c2`:
- vị trí 1–8 lấy từ hybrid;
- vị trí 9: món content user chưa nấu, xếp theo điểm content × log1p(lượt nấu);
- vị trí 10: món content chưa nấu và có ít tương tác (lượt nấu ≤ 43 ở view test, tức phân vị 20% của các món), xếp theo điểm content; không có thì lấy món thứ hai của vị trí 9;
- phần còn lại là hybrid đẩy lùi 2 vị trí.

| Độ đo | Hybrid | Hybrid + content 2 vị trí | Hiệu (c2 − hybrid) |
|---|---|---|---|
| NDCG@10 tất cả | **0,1588** | 0,1495 | −0,0092 [−0,0096; −0,0089] |
| NDCG@10 user ấm | 0,1636 | 0,1539 | −0,0097 [−0,0100; −0,0093] |
| NDCG@10 ít / lạnh | 0,1034 / 0,0540 | 0,0987 / 0,0540 | |
| P@10 / R@10 | 0,0838 / 0,1786 | 0,0744 / 0,1599 | |
| NDCG@10 biến thể khám phá | 0,0960 | 0,0846 | |
| Coverage top 10 | 41,3% | **58,0%** | +16,7 điểm % |
| Novelty | 9,13 | **9,91** | |
| Diversity | 0,854 | 0,849 | gần như không đổi |
| Recall món mới @10 (300 món ẩn) | 0 | **1,80%** | |

- Đánh đổi: mất khoảng 6% NDCG@10 để có món mới, coverage cao hơn và lý do gợi ý dạng "giống món X".
- Content đứng riêng có recall món mới @10 là 2,65% và @100 là 10,25%. Trong `hybrid_c2` chỉ có 2 vị trí, nên recall @10 và @100 đều là 1,80%.
- Trọng số hybrid mới: ALS 0,9, nấu lại 0,1, content 0, popularity 0. NDCG@10 trên val 0,1728; nếu chỉ dùng ALS thì 0,1691.

**Bảng xếp hạng đầy đủ trên test (NDCG@10):**

| Mô hình | NDCG@10 |
|---|---|
| hybrid | 0,1588 |
| ALS implicit | 0,1539 |
| hybrid + content 2 vị trí | 0,1495 |
| nấu lại | 0,1317 |
| popularity theo vùng-tuổi | 0,0571 |
| popularity chung | 0,0510 |
| popularity 2 tháng cuối | 0,0497 |
| content | 0,0095 |
| random | 0,0015 |

Khoảng tin cậy 95% của các hiệu:
- hybrid − ALS = +0,0049 [0,0042; 0,0056];
- ALS − nấu lại = +0,0221 [0,0203; 0,0240];
- hybrid − popularity theo vùng-tuổi = +0,1017 [0,0999; 0,1035].

**`recs_final`:** 50.000 user × 50 món.

| Nguồn lý do | Số dòng |
|---|---|
| als | 2.312.304 |
| content_slot | 96.346 |
| pop (user lạnh) | 91.350 |

Trong các vị trí content, 96,67% có món đã nấu làm lý do; số còn lại ghi "bạn đã xem".

**3. K-means (46.130 user; dashboard dùng k = 8):**
| k | Silhouette | ARI | NMI | Ghi chú |
|---|---|---|---|---|
| 3 | **0,227** | 0,285 | 0,365 | Silhouette cao nhất |
| 8 | 0,174 | 0,418 | 0,442 | **Dashboard**, bằng số persona |
| 11 | 0,184 | **0,504** | **0,512** | ARI cao nhất |

- k = 8: các cụm khớp với persona gia đình truyền thống 90,6%, hảo ngọt 81,8%, cay/nhậu 77,2%, bận rộn 76,9%.
- k = 11: tách persona mịn hơn, ví dụ gia đình truyền thống 94,9%, bận rộn 88,9%, cay/nhậu 88,9%, hảo ngọt 86,2%, mê hải sản 76,6%.

**Thời gian trên cụm (lần chạy này):** 06b 2.756 giây, 06f 1.386 giây (riêng thí nghiệm món mới 806 giây, vì phải fit lại ALS với rank 128), 06e 315 giây.

## Lỗi / sự cố và cách xử lý
- Lần đầu sửa 06f bằng heredoc trong bash bị lỗi phân tích chuỗi, chưa có gì được ghi vào file. Đã chuyển script sửa file sang scratchpad rồi chạy lại.
- Không có lỗi khi chạy job.

## Cần người dùng quyết định
Không. Việc tiếp theo là bước 07 (xuất MongoDB), bắt đầu bằng bản đề xuất thiết kế ghi vào file này để chat góp ý. Các phần bản thiết kế cần có đã liệt kê trong PROGRESS, mục "Việc tiếp theo".

Việc cần người làm (không đổi): kiểm tra tay 100 món (Hậu 50, Ngọc 50); Ngọc dựng notebook biểu đồ cho bước 05 và 06.

## Commit
- `9b447f2`: bước 06 lần đầu (06a–06g).
- Commit của phiên này: `Buoc 06: luoi ALS mo rong, hybrid + content 2 vi tri, k = 8` (06b, 06e, 06f, report, D13, DATA_DICTIONARY, PROGRESS, file này).
