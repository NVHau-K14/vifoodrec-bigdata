# Lần chạy gần nhất – 24/10/2026 22:10

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Lần này dài hơn 80 dòng vì nội dung chính là bản thiết kế bước 06.

## Yêu cầu
Kiểm tra cụm, rồi làm việc tiếp theo trong PROGRESS: **đề xuất thiết kế bước 06, chưa viết code**.

## Đã làm
- Cụm chạy đủ 9 container, HDFS không ở safe mode, `/data` đầy đủ.
- Chạy 1 job chỉ đọc (`probe_06_design`) để lấy số liệu thật cho thiết kế, xem bảng bên dưới. Chưa viết code bước 06.
- **Phát hiện:** mọi file do Spark ghi có replication **3**, vì Hadoop client mặc định là 3, còn `hadoop.env` chỉ áp cho namenode/datanode. Cụm chỉ có 2 datanode nên fsck báo thiếu 64 bản sao (32%). Không mất block nào. Xem câu hỏi 1.

### Số liệu dùng để thiết kế (train ≤ 07/2026, val = 08/2026, test = 09/2026)
| | train | val | test |
|---|---|---|---|
| Sự kiện view / favorite / cook / rate | 15,26M / 1,16M / 1,95M / 662.536 | 1,71M / 116.153 / 221.403 / 69.971 | 1,66M / 111.796 / 213.239 / 66.388 |
| User có hoạt động / có nấu / có chấm | 46.562 / 46.130 / 43.998 | 43.010 / 38.796 / 27.402 | 43.687 / 39.012 / 27.056 |
| User có nấu nhưng không có sự kiện nào ở train | – | 1.276 | **2.690** |
| User có nấu, chỉ có 1–19 sự kiện ở train | – | 705 | 662 |

- Cặp (user, món) trong train: 10.553.139, gồm 46.562 user × 5.499 món.
- Test có 204.975 cặp được nấu, mỗi user nấu 2 / 4 / 11 món khác nhau (p25 / p50 / p90). Trong các cặp này, **56,7%** đã gặp ở train, **26,9%** đã nấu ở train. Có 0 món chỉ xuất hiện trong test.
- FP-Growth: train có 250.908 phiên "mâm cơm" (từ 2 món), trung bình 2,35 món mỗi phiên. Mỗi món có trung bình 9,95 nguyên liệu.

### Bản thiết kế đề xuất
**Chia file.** Thêm module dùng chung `src/rec_common.py` với các hàm: `load_split()`, `implicit_matrix()`, `ranking_metrics()`, `beyond_metrics()`, `write_recs()`. Mỗi file sau đây ghi report `data/output/model_<x>_report.json`:

| File | Người | Nội dung | Ghi HDFS |
|---|---|---|---|
| `06a_split.py` | Hậu | Chia theo thời gian, ma trận implicit, tập "đáp án" val/test | `/data/results/models/splits/*` |
| `06b_als.py` | Hậu | Random, popularity (chung và theo bữa/vùng), bias baseline, ALS explicit, ALS implicit, dò tham số | `/data/models/als_*`, `.../recs_als/` |
| `06c_content.py` | Ngọc | TF-IDF + LSH, bảng món tương tự, gợi ý theo nội dung | `.../item_sim/`, `.../recs_content/` |
| `06d_fpgrowth.py` | Ngọc | Luật nguyên liệu và luật "mâm cơm" | `.../rules_ingredients/`, `.../rules_meal/` |
| `06e_kmeans.py` | Ngọc | Phân cụm user, Silhouette, ARI | `.../user_clusters/` |
| `06f_hybrid.py` | Hậu | Kết hợp, cold-start, đánh giá cuối trên test, gợi ý cuối cho MongoDB | `.../recs_final/`, `.../metrics/` |
| `06g_control.py` | Hậu | (Tùy chọn) ALS trên ratings gốc so với random (D06) | report |

**Giao thức đánh giá.**
- Dò tham số: train trên `train`, đánh giá trên `val`. Đánh giá cuối: train lại trên `train + val` rồi đo trên `test`.
- Món liên quan (relevant) = các món user **nấu** trong tháng đánh giá. User được đánh giá = user có nấu trong tháng đó (39.012 ở test).
- **Không loại món đã gặp ở train** khỏi danh sách gợi ý, vì 56,7% món đúng thuộc loại này và nấu lại là hành vi thật. Có thêm một biến thể phụ "khám phá": bỏ món đã nấu ở train ra khỏi cả danh sách gợi ý lẫn tập đáp án.
- Báo cáo kết quả riêng cho 3 nhóm user: ấm (từ 20 sự kiện ở train), ít dữ liệu (1–19), lạnh (0).
- Không dùng tháng val/test để tính bất kỳ đặc trưng nào. Không dùng `users_truth`, trừ khi tính ARI.

**Mô hình, kỹ thuật Spark và tham số**
| Mô hình | Kỹ thuật | Tham số / dò |
|---|---|---|
| Random, Popularity | Spark SQL; popularity tính theo lượt nấu ở train, có bản theo (bữa, vùng) | Không cần dò |
| Bias baseline | μ + b_u + b_i có điều chuẩn, viết bằng Spark SQL | λ ∈ {5, 10, 25} |
| ALS explicit | `ALS(implicitPrefs=False, coldStartStrategy="drop")` trên `rate` | rank {16, 32, 64} × regParam {0,05; 0,1; 0,2}; tự dò trên val |
| ALS implicit | Độ tin cậy r = log1p(1·view + 3·favorite + 5·cook) | rank {32, 64} × regParam {0,01; 0,1} × alpha {5, 20, 40}. Dò từng tham số một, khoảng 10 lần fit |
| Content | Văn bản gồm tên món, nguyên liệu, tags, nhóm món → `RegexTokenizer` tách âm tiết → `NGram(2)` → `StopWordsRemover` (danh sách tự viết) → `HashingTF(2^18)` → `IDF(minDocFreq=2)` → `Normalizer`. Ghép thêm one-hot đặc trưng món (trọng số w) | `BucketedRandomProjectionLSH` (numHashTables {3, 5}). So với tính cosine chính xác 5.499² cặp: báo recall@20 và tốc độ. Mỗi món lấy 50 món tương tự. Gợi ý cho user = Σ trọng số × độ tương tự trên 30 món nặng nhất của user |
| FP-Growth | (1) nguyên liệu: 5.499 giao dịch, chạy có và không có gia vị; (2) mâm cơm: 250.908 phiên | (1) minSupport 0,01, minConf 0,3; (2) minSupport 0,0002 (khoảng 50 phiên), minConf 0,1. Báo lift |
| K-means | Đặc trưng user lấy ở train: log số sự kiện, số phiên, tỷ trọng chay / hải sản / ngọt-đồ uống / nhanh / cay / canh, tỷ trọng theo bữa, tỷ trọng cuối tuần, entropy nhóm món, điểm chấm trung bình. Chuẩn hóa bằng `StandardScaler` | `KMeans` và `BisectingKMeans` với k = 2…12, seed 2026. Chọn k bằng Silhouette, ARI so với `persona_main` (tính bằng Spark SQL) |
| Hybrid | Mỗi mô hình lấy top 100 ứng viên rồi gộp. Điểm = α·ALS + β·content + γ·popularity theo bữa/vùng, chuẩn hóa theo hạng trong từng user | α, β, γ dò trên lưới bước 0,1 (66 tổ hợp) trên val, dùng ứng viên đã tính sẵn nên nhanh |

**Cold-start.**
- User có 0 sự kiện ở train: popularity theo (vùng, nhóm tuổi, bữa), lấy từ bảng `users`. Bảng này mô hình được dùng.
- User có 1–4 lượt nấu: chỉ dùng content (β) và popularity (γ).
- User mới trên dashboard (chọn vài món mình thích): dùng content.
- Món mới: dữ liệu không có. Đề xuất thí nghiệm giả lập ở câu hỏi 3.
- Bộ lọc chay / món nhanh / bữa áp dụng sau khi xếp hạng (dùng ở API).

**Bảng độ đo**
| Độ đo | Áp cho | Tập |
|---|---|---|
| RMSE, MAE | Trung bình chung, bias, ALS explicit, (đối chứng) | val để dò, test để báo cáo; có báo tỷ lệ dòng bị drop |
| P@K, R@K, NDCG@K, MAP@K (K = 5, 10) | Random, popularity, ALS implicit, content, hybrid | val để dò, test cho kết quả cuối; tách 3 nhóm user. Dùng `RankingEvaluator` |
| Coverage, diversity (1 − cosine trung bình trong danh sách), novelty (−log₂ mức phổ biến) | Như trên, với top 10 | test |
| Hit rate món ăn kèm (luật mâm cơm, top 3) | FP-Growth | các phiên mâm cơm trong test |
| Silhouette, ARI | K-means | train |
| Recall@20 của LSH so với tính chính xác, thời gian chạy | Content | – |

**Thứ tự ưu tiên** (mỗi bước chạy `--local` trên bản 10% trước, rồi mới lên cụm):
06a → 06b → 06c → 06f → 06d → 06e → 06g.
- Ước tính thời gian trên cụm: ALS implicit khoảng 2–5 phút mỗi lần fit trên 10,5M cặp, các bước còn lại vài phút mỗi bước. Số thật sẽ ghi vào report.
- Bước 06 không đọc các bảng của bước 05 (D09).

## Lỗi / sự cố và cách xử lý
- Lần chạy job khảo sát đầu tiên không lấy được kết quả: dòng in ra bị dính sau thanh tiến trình nên `grep "^PROBE"` không khớp. Đã chạy lại và lấy bằng `grep -o`.

## Cần người dùng quyết định
1. **Replication:** đề xuất thêm `spark.hadoop.dfs.replication=2` vào `get_spark()` và chạy `hdfs dfs -setrep -R -w 2 /data`. Làm trước khi bước 06 ghi dữ liệu, để ảnh chụp HDFS UI không báo thiếu bản sao. Đồng ý không?
2. **`/data/events/events_csv`** (1,4GB) là bản CSV của lần chạy 04 đầu tiên, đã cũ so với events hiện tại. Đề xuất xóa ngay, rồi sinh lại bằng `--csv` khi đo hiệu năng. Đồng ý không?
3. **Món mới:** có làm thí nghiệm giả lập không? Cách làm: ẩn mọi tương tác ở train của 300 món ngẫu nhiên, rồi đo hybrid/content gợi ý được những món đó tới đâu. Đề xuất: có, làm ở cuối 06f.
4. Giao thức: "không loại món đã gặp, có thêm biến thể khám phá", và "train lại trên train + val trước khi đo test". Chốt như vậy không?
5. Tên module dùng chung: `src/rec_common.py`, hay gộp vào `common.py`? Đề xuất tách riêng.
6. Thí nghiệm đối chứng 06g (ratings gốc): làm hay bỏ?

Sau khi chốt, nội dung thiết kế sẽ được ghi thành D12 trong DECISIONS rồi mới viết code.

## Commit
- `adfafbc`: chốt mẫu kiểm tra tay theo hash.
- Commit của phiên này: file này và PROGRESS. Message: `Buoc 06: de xuat thiet ke (chua code)`.
