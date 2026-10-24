# Lần chạy gần nhất – 24/10/2026 (khuya)

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Mọi số liệu bên dưới lấy từ `data/output/model_*_report.json` và `models_metrics.json` (chạy trên cụm).

## Yêu cầu
Đọc góp ý thiết kế 06 (sửa đổi a–i) và câu trả lời 7 câu hỏi. Ghi bản đã chốt thành D12, cập nhật PROGRESS, rồi viết code theo thứ tự 06a → 06b → 06c → 06f → 06d → 06e → 06g, mỗi file chạy `--local` trước. Xong thì ghi LAST_RUN và chạy `/handoff`.

## Đã làm
**Hạ tầng (câu hỏi 1, 2):**
- `get_spark()` ghi HDFS với 2 bản sao; đã chạy `setrep -R -w 2 /data`. fsck: HEALTHY, thiếu 0 bản sao, replication trung bình 2,0.
- Đã xóa `/data/events/events_csv` (bản cũ).
- `get_spark()` đặt thêm `spark.driver.memory` (3g khi chạy local, 2g trên cụm). `Paths` có thêm `models` và `checkpoint`.

**D12** ghi bản thiết kế đã chốt, gồm đủ 7 câu trả lời và 9 sửa đổi. **D13** ghi các điều chỉnh khi cài đặt và các phát hiện.

**Code** (mỗi file chạy local trên bản 10% trước, rồi chạy trên cụm; tất cả đều thành công):
| File | Nội dung | Thời gian trên cụm |
|---|---|---|
| `src/rec_common.py` | Module dùng chung: 2 view, nhóm user, độ đo cho từng user bằng hàm mảng Spark SQL, tổng hợp theo nhóm, khoảng tin cậy ghép cặp | – |
| `06a_split.py` | Hai bộ `_val` (lịch sử = train) và `_test` (lịch sử = train + val): implicit, ratings, `user_groups`, truth, popularity, đặc trưng user | 101 giây |
| `06b_als.py` | Random, 3 kiểu popularity, nấu lại, bias, ALS explicit, ALS implicit (dò tham số + độ nhạy trọng số), đối chiếu `RankingEvaluator`, khoảng tin cậy | 1.294 giây |
| `06c_content.py` | Token (âm tiết, nguyên liệu nối `_`, đặc trưng có cấu trúc), CountVectorizer(minDF=2) → IDF → Normalizer, độ tương tự chính xác bằng chỉ mục ngược, MinHashLSH, gợi ý theo nội dung | 200 giây |
| `06f_hybrid.py` | RRF có trọng số trên 4 nguồn, dò 286 tổ hợp, luật cold-start, mọi độ đo, biến thể khám phá, coverage/novelty/diversity, khoảng tin cậy, `recs_final`, thí nghiệm món mới | 662 giây |
| `06d_fpgrowth.py` | Luật nguyên liệu (giữ và bỏ gia vị), luật mâm cơm, hit rate@3 so với 2 mốc | 34 giây |
| `06e_kmeans.py` | KMeans và BisectingKMeans với k = 2…12, Silhouette, ARI và NMI tại k tốt nhất và k = 8, hồ sơ cụm | 256 giây |
| `06g_control.py` | ALS trên ratings gốc so với đoán ngẫu nhiên, trung bình chung và bias | 61 giây |

Tài liệu: DATA_DICTIONARY có thêm mục bước 06 (20 bảng); bảng Pipeline trong CLAUDE.md, PROGRESS và D12, D13 đều đã cập nhật.

## Số liệu chính
**Chia dữ liệu (06a, kiểm tra theo sửa đổi a):** view test có 39.012 user được đánh giá, gồm ấm 36.979, ít 742 và **lạnh 1.291**. Con số 2.690 trong bản đề xuất là tính theo train; tính đúng theo train + val ra 1.291.

**Xếp hạng trên test, cùng 39.012 user cho mọi mô hình:**
| Mô hình | NDCG@10 | P@10 | R@10 | MAP@10 | NDCG@10 ấm | NDCG@10 lạnh |
|---|---|---|---|---|---|---|
| random | 0,0015 | 0,0010 | 0,0019 | 0,0006 | 0,0015 | 0,0004 |
| pop_chung | 0,0510 | 0,0286 | 0,0583 | 0,0251 | 0,0512 | 0,0473 |
| pop_gan_day (2 tháng cuối) | 0,0497 | 0,0282 | 0,0555 | 0,0244 | 0,0500 | 0,0448 |
| pop_vung_tuoi | 0,0571 | 0,0324 | 0,0655 | 0,0283 | 0,0573 | 0,0540 |
| nau_lai | 0,1317 | 0,0691 | 0,1417 | 0,0746 | 0,1362 | 0,0473 |
| als_implicit | 0,1508 | 0,0798 | 0,1692 | 0,0856 | 0,1572 | 0 |
| content | 0,0095 | 0,0065 | 0,0117 | 0,0039 | 0,0099 | 0 |
| **hybrid** | **0,1564** | **0,0828** | **0,1750** | **0,0890** | **0,1611** | 0,0540 |

- **Khoảng tin cậy 95% của hiệu NDCG@10:**
  - hybrid − ALS = +0,0055 [0,0046; 0,0065]; chỉ tính user ấm: +0,0040 [0,0031; 0,0049];
  - hybrid − nấu lại = +0,0246 [0,0231; 0,0262];
  - ALS − nấu lại = +0,0191 [0,0172; 0,0210];
  - hybrid − popularity theo vùng-tuổi = +0,0993 [0,0975; 0,1011].
- **Biến thể khám phá, NDCG@10** (37.253 user còn món đáp án): ALS 0,0934, hybrid 0,0905, pop_vung_tuoi 0,0314, nấu lại 0,0263, content 0,0087.
- **Ngoài độ chính xác (top 10):**

  | Mô hình | Coverage | Novelty | Diversity |
  |---|---|---|---|
  | hybrid | 35,6% | 8,98 | 0,859 |
  | ALS | 32,9% | 9,18 | 0,848 |
  | content | 77,0% | 12,93 | 0,736 |
  | nấu lại | 97,6% | 10,26 | 0,895 |
  | popularity | 0,2–0,5% | – | – |

- **Kiểm tra độ đo tự viết với `RankingEvaluator`** (ALS, test): NDCG@10 0,1508 = 0,1508; P@10 0,0798 = 0,0798; MAP@10 0,0856 = 0,0856; R@10 0,1692 = 0,1692.

**ALS implicit (dò tham số trên 10.000 user của val):**
- Theo alpha (rank 32, reg 0,1): alpha 1 → 0,1541; 5 → 0,1506; 20 → 0,1118; 40 → 0,0808.
- Rank 64 → 0,1591. regParam 0,01 → 0,1521.
- **Tham số chọn: alpha 1, rank 64, reg 0,1. Cả alpha và rank đều nằm ở biên lưới** (câu hỏi 1).
- Độ nhạy trọng số implicit: 1/3/5 → 0,1591; 1/2/10 → 0,1593; chỉ cook → 0,1327. Giữ 1/3/5 vì 1/2/10 chỉ hơn 0,0002.

**Hybrid:**
- Trọng số tốt nhất: α (ALS) 0,8, δ (nấu lại) 0,2, **β (content) 0**, **γ (popularity) 0**. NDCG@10 trên mẫu val 0,1698; nếu chỉ dùng ALS thì 0,1659.
- Ứng viên phủ 62,6% số món đáp án.
- Nhóm "ít" giữ nguyên trọng số (0,0999 so với 0,0647 khi đặt α = 0).
- `recs_final`: 50.000 user × 50 món. Nguồn lý do gợi ý: als 2.408.650 dòng, pop 91.350 dòng (user lạnh); **không có dòng nào mang lý do content hoặc nấu lại** (câu hỏi 2).

**Món mới (300 món bị ẩn, 12.168 cặp ở test):** content recall@10 = 2,65%, recall@100 = 10,25%. ALS, popularity, nấu lại và **hybrid đều bằng 0**.

**Dự đoán điểm (test):**
| | Trên dòng chung (63.370) | Trên toàn bộ dòng (66.388) |
|---|---|---|
| Trung bình chung | 1,071 | 1,072 |
| Bias (λ = 5) | 0,737 | 0,740 |
| ALS explicit (rank 16, reg 0,1) | **0,684** | – |
| ALS, thiếu thì dùng bias | – | 0,689 |

ALS bỏ 4,55% số dòng vì user/món không có trong lịch sử.

**Đối chứng 06g (ratings gốc, 182.556 dòng, 101 user, 3.996 món):** đoán ngẫu nhiên 2,240; trung bình chung 1,578; bias 1,588; **ALS 1,673, kém hơn trung bình chung 6,0%**. Trên dữ liệu mô phỏng, ALS tốt hơn trung bình chung 36,1%.

**Content:**
- Từ điển 2.862 token: 992 âm tiết, 1.829 nguyên liệu, 41 nhãn đặc trưng. Trung bình 15,6 token mỗi món.
- TF-IDF tính bằng SQL khớp pipeline Spark (sai khác lớn nhất 1,1e-16).
- Tính chính xác: 10,9M cặp có độ tương tự khác 0, mất 37 giây.
- MinHashLSH recall@20: 3 bảng băm 0,789 (14 giây); 5 bảng 0,868 (17 giây); 10 bảng 0,993 (36 giây). Ở 5.499 món, LSH chưa nhanh hơn tính chính xác.
- Món content gợi ý có hạng phổ biến trung vị 1.598, món user thật sự nấu là 410 (chạy trên bản 10%). Đây là lý do content xếp hạng kém.

**FP-Growth:**
- Mâm cơm: 279.148 phiên, 677 luật, 656 món có món ăn kèm.
- Hit rate@3 trên 67.308 lượt hỏi ở test: **luật 0,219**; luật thiếu thì dùng mốc theo nhóm món 0,240; mốc theo nhóm món 0,076; mốc 3 canh phổ biến 0,035. Luật phủ 64,5% số lượt hỏi; tính riêng phần có luật thì đạt 0,339.
- Nguyên liệu: giữ gia vị có 2.963 luật, bỏ gia vị có 36 luật. Ví dụ: men nở → bột mì (lift 8,7), lá dứa → nước cốt dừa (lift 7,6).

**K-means (46.130 user):**
- Silhouette cao nhất ở **k = 3** (0,227; ARI 0,285; NMI 0,365).
- Tại k = 8: KMeans có ARI 0,418, NMI 0,442; BisectingKMeans có ARI 0,377.
- Các cụm k = 8 khớp với persona: gia đình truyền thống 90,6%, hảo ngọt 81,8%, cay/nhậu 77,2%, bận rộn 76,9% (cụm có tỷ trọng món nhanh 0,85), ăn chay 47,1% (cụm có tỷ trọng món chay 0,90).
- ARI cao nhất đạt ở k = 11 (0,504).

## Lỗi / sự cố và cách xử lý
- 06b local lần đầu bị lỗi tên tham số (`reg` và `regParam`). Đã sửa và chạy lại.
- 06c local lần đầu bị lỗi `F.when("cột")`: Spark 4 yêu cầu Column. Đã sửa thành `F.col(...)`.
- Content xếp hạng rất kém. Đã kiểm tra code (khớp pipeline, món tương tự hợp lý); nguyên nhân là phương pháp bỏ qua độ phổ biến. Ghi trong D13.
- Không chạy song song job local và job cụm được, vì bộ nhớ container jupyter có hạn. Đã ghi vào CLAUDE.md.

## Cần người dùng quyết định
1. **Lưới ALS implicit chạm biên:** alpha tốt nhất là 1 (giá trị nhỏ nhất) và rank tốt nhất là 64 (giá trị lớn nhất). Đề xuất: mở rộng thêm một lần, alpha {0,25; 0,5} và rank 128. Chi phí khoảng 4 lần fit, cộng chạy lại 06f. Mở rộng hay giữ nguyên?
2. **Content có trọng số 0 trong hybrid.** Hệ quả: món mới không bao giờ được gợi ý, và lý do gợi ý chỉ có "als" hoặc "pop". Các lựa chọn:
   - (a) giữ nguyên, tối ưu độ chính xác thuần;
   - (b) **dành 2 vị trí cuối của top 10 cho content** (món chưa nấu, có lý do "giống món X"). Đo mức giảm NDCG@10 trên test và mức tăng coverage, novelty, recall món mới. **Đề xuất (b)**, chỉ áp cho `recs_final` và dashboard; bảng đánh giá báo cả hai phiên bản;
   - (c) cộng điểm content cho món có ít tương tác.
3. **K cho trang "Phân khúc người dùng":** k = 3 (Silhouette cao nhất) hay k = 8 (ARI 0,42, các cụm diễn giải được theo persona)? Đề xuất: dashboard dùng **k = 8**, báo cáo trình bày cả hai.

Việc cần người làm (không đổi): kiểm tra tay 100 món (Hậu 50, Ngọc 50); Ngọc dựng notebook biểu đồ cho bước 05 và 06.

## Commit
- `c276f42`, `bc210e3`: bản thiết kế đầy đủ, bỏ giới hạn độ dài LAST_RUN.
- Commit của phiên này: `Buoc 06: 06a-06g, hybrid, danh gia tren cum` (code, report, D12, D13, PROGRESS, DATA_DICTIONARY, CLAUDE.md, file này).
