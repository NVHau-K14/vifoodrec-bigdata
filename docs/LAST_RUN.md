# Lần chạy gần nhất – 24/10/2026 22:40

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.

## Yêu cầu
Kiểm tra cụm, rồi làm việc tiếp theo trong PROGRESS: **đề xuất thiết kế bước 06, chưa viết code**. Sau đó bỏ giới hạn độ dài của file này và viết lại bản thiết kế đầy đủ, không rút gọn.

## Đã làm
- Cụm chạy đủ 9 container, HDFS không ở safe mode, `/data` đầy đủ.
- Chạy 1 job chỉ đọc (`probe_06_design`) để lấy số liệu thật cho thiết kế, xem mục "Số liệu chính". Chưa viết code bước 06.
- **Phát hiện:** mọi file do Spark ghi lên HDFS có replication **3**, vì Hadoop client mặc định là 3, còn `hadoop.env` chỉ áp cho namenode/datanode. Cụm chỉ có 2 datanode nên fsck báo thiếu 64 bản sao (32%). Không mất block nào. Xem câu hỏi 1.
- Bỏ giới hạn 80 dòng của LAST_RUN trong `CLAUDE.md` và `handoff.md` (commit `bc210e3`).

---

## Bản thiết kế bước 06 (đề xuất, chờ góp ý)

### 1. Mục tiêu và nguyên tắc
- Gợi ý món cho từng user. Mô hình chính của sản phẩm là **hybrid**; các mô hình còn lại là mốc so sánh hoặc thành phần của hybrid.
- Dữ liệu hành vi là **mô phỏng**. Mô hình không được thấy `users_truth`, chỉ dùng nó để tính ARI cho K-means.
- **Không rò rỉ thời gian:** mọi đặc trưng, popularity và mô hình chỉ dùng tháng train. Các bảng của bước 05 tính trên cả 12 tháng nên bước 06 không dùng (D09).
- Mọi bước chạy được `--local` trên bản 10% (`data/hdfs_local`, 5.000 user, 2.292.479 sự kiện) để thử trước, rồi mới chạy trên cụm.
- Seed cố định 2026. Mỗi file ghi `data/output/model_<x>_report.json` gồm độ đo, tham số đã chọn và thời gian từng phần. Thời gian này dùng cho phần đo hiệu năng (1 hay 2 worker).

### 2. Chia file
**Module dùng chung `src/rec_common.py`** (không phải một bước). Lý do tách khỏi `common.py`: `common.py` lo hạ tầng (Spark, đường dẫn, làm sạch văn bản), còn module này lo logic đánh giá gợi ý mà chỉ bước 06 dùng.
- `load_split(spark, P, name)`: đọc các bảng chia sẵn của 06a.
- `implicit_matrix(df)`: tính độ tin cậy implicit từ sự kiện (mục 4).
- `ranking_metrics(recs, truth, ks=(5, 10))`: P@K, R@K, NDCG@K, MAP@K, dùng `pyspark.ml.evaluation.RankingEvaluator`. Có tách theo nhóm user.
- `beyond_metrics(recs, item_vec, pop)`: coverage, diversity, novelty.
- `write_recs(df, name)`: ghi top-N lên HDFS theo schema thống nhất `user_id, rank, food_id, score, source`.

| File | Người | Nội dung | Ghi HDFS | Report |
|---|---|---|---|---|
| `06a_split.py` | Hậu | Chia train/val/test; ma trận implicit; bảng rating; tập "đáp án" val/test; gắn nhóm user (ấm / ít / lạnh) | `/data/results/models/splits/{train_events, train_implicit, train_ratings, trainval_implicit, trainval_ratings, val_truth, test_truth, user_groups}` | `model_split_report.json` |
| `06b_als.py` | Hậu | Random, popularity, bias baseline, ALS explicit, ALS implicit, dò tham số | `/data/models/{als_explicit, als_implicit}`, `/data/results/models/recs_{random,pop,als}/`, `.../tuning_als/` | `model_als_report.json` |
| `06c_content.py` | Ngọc | Pipeline TF-IDF, LSH, bảng món tương tự, gợi ý theo nội dung | `/data/models/content_pipeline`, `.../item_vectors/`, `.../item_sim/`, `.../recs_content/` | `model_content_report.json` |
| `06d_fpgrowth.py` | Ngọc | Luật nguyên liệu, luật "mâm cơm" | `.../rules_ingredients/`, `.../rules_meal/`, `.../companion/` | `model_fpgrowth_report.json` |
| `06e_kmeans.py` | Ngọc | Đặc trưng user, KMeans / BisectingKMeans, Silhouette, ARI | `/data/models/kmeans`, `.../user_features/`, `.../user_clusters/`, `.../cluster_profile/` | `model_kmeans_report.json` |
| `06f_hybrid.py` | Hậu | Gộp ứng viên, dò α/β/γ, cold-start, đánh giá cuối trên test, lý do gợi ý, gợi ý cuối | `.../recs_final/`, `.../metrics/` | `model_hybrid_report.json`, `models_metrics.json` (bảng tổng hợp) |
| `06g_control.py` | Hậu | (Tùy chọn) ALS trên ratings gốc so với random (D06) | – | `model_control_report.json` |

- Thư mục `/data/models/...` chứa model Spark đã lưu (`.save()`). Bước 07 và API có thể nạp lại.
- Thư mục `/data/results/models/...` chứa bảng kết quả. Bước 07 sẽ xuất sang MongoDB.
- Mỗi file có `--local`; file nặng có thêm `--quick` (lưới tham số nhỏ để thử).

### 3. Chia dữ liệu và giao thức đánh giá
- **Theo thời gian:** train = 10/2025–07/2026 (10 tháng), val = 08/2026, test = 09/2026.
- **Hai pha:**
  - Dò tham số: fit trên `train`, đo trên `val`.
  - Kết quả cuối: fit lại với tham số đã chọn trên `train + val`, đo trên `test`. Tháng 8 là dữ liệu gần nhất, bỏ đi thì mô hình cuối bị cũ một tháng.
- **Món liên quan (relevant):** tập món khác nhau user **nấu** trong tháng đánh giá. Chọn `cook` vì đây là hành vi có giá trị nhất của sản phẩm; `view` quá nhiễu. Test có 204.975 cặp được nấu, mỗi user nấu 2 / 4 / 11 món (p25 / p50 / p90).
- **User được đánh giá:** user có ít nhất 1 lượt nấu trong tháng đó (val 38.796, test 39.012).
- **Có loại món đã gặp ở train không?** Đề xuất **không loại** ở bảng chính. Lý do: 56,7% cặp được nấu ở test đã gặp ở train và 26,9% đã từng được nấu (nấu lại là hành vi thật, bộ sinh có 25% nấu lại món đã lưu). Loại đi sẽ bỏ hơn nửa số món đúng.
- **Biến thể "khám phá"** (bảng phụ): bỏ món user đã nấu ở train ra khỏi cả danh sách gợi ý lẫn tập đáp án, để đo khả năng gợi ý món mới. ALS thường mạnh ở bảng chính, content mạnh hơn ở bảng này, nên đáng trình bày.
- **Nhóm user** (tính theo số sự kiện ở train, dùng để tách kết quả):

  | Nhóm | Điều kiện | val | test |
  |---|---|---|---|
  | ấm | ≥ 20 sự kiện | 36.815 | 35.660 |
  | ít dữ liệu | 1–19 | 705 | 662 |
  | lạnh | 0 | 1.276 | 2.690 |

- **RMSE/MAE:** đo trên các dòng `rate` của val/test. ALS dùng `coldStartStrategy="drop"`, nên report ghi tỷ lệ dòng bị bỏ. Bias baseline thì rơi về μ + b_i cho user lạ, nên không bỏ dòng nào.

### 4. Mô hình, kỹ thuật Spark và tham số

**4.1 Baseline (06b)**
- Random: mỗi user lấy 10 món ngẫu nhiên, seed cố định. Đây là mốc dưới.
- Popularity chung: xếp món theo số lượt nấu ở train (Spark SQL).
- Popularity theo ngữ cảnh: theo (bữa, vùng). Dùng cho cold-start và thành phần γ của hybrid.
- Bias baseline cho rating: r̂ = μ + b_u + b_i, với b_i = Σ(r − μ) / (λ + n_i) và b_u tính tương tự sau khi trừ b_i. Viết bằng Spark SQL; dò λ ∈ {5, 10, 25} trên val. Đây là mốc mà ALS explicit phải vượt (D07).

**4.2 ALS explicit (06b)**
- `pyspark.ml.recommendation.ALS(implicitPrefs=False, nonnegative=False, coldStartStrategy="drop", seed=2026)` trên các dòng `rate` (train có 662.536 dòng).
- Lưới: rank {16, 32, 64} × regParam {0,05; 0,1; 0,2} = 9 lần fit, maxIter = 15. Tự viết vòng lặp dò trên val thay cho `TrainValidationSplit`, vì TVS chia ngẫu nhiên nên phá cách chia theo thời gian. Kết quả từng ô ghi vào `tuning_als/` để vẽ biểu đồ.
- Đặt `spark.sparkContext.setCheckpointDir()` và `checkpointInterval = 5` để lineage không quá dài khi maxIter lớn.

**4.3 ALS implicit (06b)**
- Độ tin cậy cho mỗi cặp (user, món): `r = log1p(1·n_view + 3·n_favorite + 5·n_cook)`. Lấy log để món xem quá nhiều lần không lấn át. Trọng số 1/3/5 phản ánh độ cam kết tăng dần. Train có 10.553.139 cặp.
- `ALS(implicitPrefs=True, alpha, rank, regParam, maxIter=10)`.
- Dò lần lượt từng tham số, cố định các tham số còn lại, khoảng 10 lần fit thay cho lưới đầy đủ 12 lần:
  - alpha {5, 20, 40};
  - rank {32, 64};
  - regParam {0,01; 0,1}.

  Chọn theo NDCG@10 trên val.
- Lấy gợi ý: `recommendForUserSubset(users đánh giá, 100)`. Top 100 làm ứng viên cho hybrid, top 10 để tính độ đo.
- Có thể thử thêm (nếu còn thời gian): giảm trọng số sự kiện cũ, w = 0,5^(số tháng trước cuối train / 3).

**4.4 Content-based (06c)**
- Văn bản mỗi món = tên món + nguyên liệu (`ingredient_list`) + `dish_tags` + `dish_category` + `main_method` + `main_protein`, chữ thường, chuẩn NFC.
- Pipeline Spark ML:
  - `RegexTokenizer(pattern="[^\\p{L}]+")` tách âm tiết tiếng Việt;
  - `NGram(n=2)` tạo cặp âm tiết ("cà chua", "thịt bò"). Gộp âm tiết đơn và bigram bằng `SQLTransformer` (`concat`);
  - `StopWordsRemover` với danh sách tự viết (của, và, với, cho, các, món, cách, làm…). Gia vị phổ biến ("muối", "dầu ăn"…) cũng bỏ, lấy lại danh sách `SEASONINGS` của bước 05;
  - `HashingTF(numFeatures=2^18)` → `IDF(minDocFreq=2)` → `Normalizer(p=2)`.
- **Ghép thêm đặc trưng có cấu trúc:** one-hot `dish_category`, `main_protein`, `main_method`, `dish_type_fixed`, `season`, `is_spicy`, `is_quick`, `is_vegetarian` qua `OneHotEncoder` và `VectorAssembler`, nhân trọng số w ∈ {0,5; 1} rồi chuẩn hóa lại.
- **Món tương tự:** `BucketedRandomProjectionLSH(bucketLength ∈ {1; 2}, numHashTables ∈ {3, 5})` trên vector đã chuẩn hóa. Với vector chuẩn hóa thì khoảng cách Euclid tương đương cosine. Dùng `approxSimilarityJoin`, mỗi món giữ 50 món gần nhất → `item_sim(food_id, sim_food_id, sim, rank)`.
- **So sánh với tính chính xác:** tính cosine đủ 5.499² ≈ 30,2M cặp bằng crossJoin rồi lấy top 50. Báo recall@20 của LSH và thời gian hai cách. Đây là điểm minh họa Big Data: LSH dùng được khi số món tăng lên.
- **Gợi ý cho user:** lấy 30 món có trọng số implicit cao nhất của user ở train, kết hợp `item_sim`: score(u, i) = Σ_j w_uj · sim(j, i). Cách này tránh nhân ma trận dense 46k × 5,5k. Join khoảng 46k × 30 × 50 ≈ 70M dòng rồi `groupBy`.
- **Lý do gợi ý:** món j đóng góp nhiều nhất vào điểm, ví dụ "vì bạn đã nấu Canh chua cá lóc".

**4.5 FP-Growth (06d)**
- **(1) Nguyên liệu:** mỗi món là một giao dịch (5.499 giao dịch, trung bình 9,95 nguyên liệu). Chạy 2 lần, giữ và bỏ gia vị.
  - `FPGrowth(minSupport=0,01, minConfidence=0,3)` (0,01 ≈ 55 món), báo lift;
  - xuất cạnh (A → B, lift) để vẽ đồ thị mạng nguyên liệu trên dashboard.
- **(2) Mâm cơm:** mỗi phiên nấu từ 2 món ở train là một giao dịch (250.908 phiên, trung bình 2,35 món).
  - `FPGrowth(minSupport=0,0002 (≈ 50 phiên), minConfidence=0,1)`;
  - suy ra bảng `companion(food_id, companion_id, confidence, lift)` cho mục "món ăn kèm".
- **Đánh giá luật mâm cơm:** với các phiên mâm cơm trong test, cho món chính rồi kiểm tra món đi kèm thật có nằm trong top 3 món luật gợi ý không (hit rate@3). So với mốc là "3 món canh phổ biến nhất".

**4.6 K-means (06e)**
- Đặc trưng mỗi user, tính trên train:
  - mức hoạt động: log1p(số sự kiện), log1p(số phiên), tỷ lệ nấu/xem, tỷ lệ chấm/nấu;
  - khẩu vị (tỷ trọng trong lượt nấu): món chay, hải sản, ngọt + đồ uống, món nhanh, món cay, canh/súp, lẩu;
  - thời gian: tỷ trọng theo bữa (sáng / trưa / tối / khuya), tỷ trọng cuối tuần;
  - độ đa dạng: entropy của nhóm món đã nấu; điểm chấm trung bình (thiếu thì lấy μ).
- Chuẩn hóa bằng `StandardScaler`. Chạy `KMeans` và `BisectingKMeans` với k = 2…12, seed 2026. Chọn k theo Silhouette (`ClusteringEvaluator`), có xét thêm khả năng diễn giải.
- **ARI so với `persona_main`:** tính bảng chéo bằng Spark SQL rồi áp công thức ARI. Lưu ý ARI không thể đạt 1, vì mỗi user có cả persona phụ (trọng số 0,5) và còn chịu ảnh hưởng của vùng và tuổi.
- `cluster_profile`: trung bình từng đặc trưng theo cụm, dùng cho trang "Phân khúc người dùng" và phần đề xuất chiến lược.
- Có thể dùng thêm (tùy chọn): cụm làm ngữ cảnh popularity cho user ít dữ liệu.

**4.7 Hybrid (06f)**
- **Ứng viên:** hợp của top 100 ALS implicit, top 100 content và top 50 popularity theo (bữa, vùng) của user. Bữa ưa thích lấy từ train.
- **Chuẩn hóa điểm:** đổi điểm từng nguồn sang thang hạng trong mỗi user, s = 1 − (hạng − 1) / 100; món không có trong nguồn đó thì s = 0. Lý do: thang điểm ALS và cosine khác nhau.
- **Điểm hybrid** = α·s_ALS + β·s_content + γ·s_pop. Dò trên lưới α, β, γ ≥ 0 với tổng bằng 1, bước 0,1 (66 tổ hợp) trên val. Ứng viên đã tính sẵn nên mỗi tổ hợp chỉ là một phép tổng hợp lại, rất nhanh. Chọn theo NDCG@10 của nhóm user ấm.
- **Cold-start** (luật chuyển đổi, cũng dò trên val):

  | Tình huống | Cách gợi ý |
  |---|---|
  | User có 0 sự kiện ở train (test 2.690) | Popularity theo (vùng, nhóm tuổi, bữa), lấy từ bảng `users`. Bảng này mô hình được dùng |
  | User có 1–4 lượt nấu | Chỉ content và popularity: α = 0, β và γ dò riêng |
  | User mới trên dashboard (chọn vài món mình thích) | Content: lấy các món đã chọn làm lịch sử, tra `item_sim` |
  | Món mới | Content (dựa trên văn bản món). Dữ liệu không có món mới, xem câu hỏi 3 |

- **Lý do gợi ý** (cột `reason`, cho dashboard): nguồn đóng góp lớn nhất, kèm chi tiết. Ví dụ: "người có khẩu vị giống bạn cũng nấu" (ALS), "giống món X bạn đã nấu" (content), "đang được nấu nhiều vào bữa tối ở miền Nam" (popularity).
- **Bộ lọc** chay / món nhanh / bữa / nhóm món áp dụng sau khi xếp hạng, ở API. Gợi ý cuối lưu sẵn top 50 cho mỗi user, đủ để vẫn còn món sau khi lọc.
- **Đầu ra cho bước 07:** `recs_final(user_id, rank, food_id, score, s_als, s_content, s_pop, reason)`, `item_sim`, `companion`, `user_clusters`, `metrics`.

**4.8 Đối chứng ratings gốc (06g, tùy chọn)**
- ALS explicit trên `ratings_original` (182.556 dòng), chia ngẫu nhiên 80/20, so với đoán ngẫu nhiên và trung bình chung.
- Kỳ vọng RMSE khoảng 1,58 (D06), tức không khá hơn ngẫu nhiên. Đây là bằng chứng cho lý do dùng dữ liệu mô phỏng.

### 5. Bảng độ đo
| Độ đo | Áp cho | Tập | Ghi chú |
|---|---|---|---|
| RMSE, MAE | Trung bình chung, bias baseline, ALS explicit, đối chứng | val để dò, test để báo cáo | Kèm tỷ lệ dòng bị drop |
| Precision@K, Recall@K, NDCG@K, MAP@K (K = 5, 10) | Random, popularity (chung và theo ngữ cảnh), ALS implicit, content, hybrid | val để dò, test cho kết quả cuối | Bảng chính và biến thể khám phá, tách 3 nhóm user. `RankingEvaluator` |
| Coverage (% danh mục xuất hiện trong ít nhất một top 10) | Như trên | test | Popularity sẽ rất thấp |
| Diversity (1 − cosine trung bình giữa các cặp trong top 10, dùng vector content) | Như trên | test | |
| Novelty (trung bình −log₂ của tỷ trọng lượt nấu ở train) | Như trên | test | |
| Hit rate@3 món ăn kèm | Luật mâm cơm | các phiên mâm cơm trong test | So với mốc "3 canh phổ biến nhất" |
| Support, confidence, lift | Luật nguyên liệu, luật mâm cơm | train | |
| Silhouette, ARI | K-means, Bisecting K-means | train | ARI so với `persona_main` |
| Recall@20 của LSH, thời gian | Content | – | So với cosine tính chính xác |
| Thời gian chạy từng phần | Tất cả | – | Dùng cho phần đo hiệu năng |

`models_metrics.json` gom thành một bảng tổng hợp (mô hình × độ đo × tập × nhóm user) cho trang "Đánh giá mô hình" và báo cáo.

### 6. Thứ tự ưu tiên và kế hoạch chạy
1. **06a split.** Mọi bước sau đều cần.
2. **06b baseline + ALS.** Bảng độ đo đầu tiên. Kiểm tra lại kết quả cũ (bản trước 24/10: ALS thắng bias và popularity) trên dữ liệu mới.
3. **06c content.** Đầu vào của hybrid và của "món tương tự".
4. **06f hybrid + cold-start.** Mô hình chính, đánh giá cuối.
5. **06d FP-Growth.** "Món ăn kèm" và đồ thị nguyên liệu cho dashboard.
6. **06e K-means.** Trang phân khúc.
7. **06g đối chứng** (nếu làm).

Thứ tự này theo phần "rủi ro thực tế" của kế hoạch: ALS + content + hybrid + đánh giá đi trước, FP-Growth và K-means sau. Theo phân công, Ngọc có thể làm 06c, 06d, 06e song song ngay sau khi có 06a.

**Ước tính thời gian trên cụm** (4 core, executor 2GB; chỉ là ước tính, số thật sẽ ghi vào report):

| File | Ước tính |
|---|---|
| 06a | 2–3 phút |
| 06b | ALS explicit 9 lần fit × khoảng 0,5 phút; ALS implicit khoảng 10 lần fit × 2–5 phút; tổng 30–60 phút |
| 06c | 5–10 phút (gồm phần tính chính xác 30M cặp để so sánh) |
| 06d | 2–5 phút |
| 06e | 5–10 phút (11 giá trị k × 2 thuật toán) |
| 06f | 10–20 phút |

**Rủi ro:**
- `recommendForUserSubset` hoặc phép join content 70M dòng có thể thiếu bộ nhớ trên executor 2GB. Cách xử lý: chia user theo lô (`user_id % 4`) và tăng `spark.sql.shuffle.partitions`.
- ALS implicit với rank 64 có thể chậm. Nếu vậy, giới hạn rank ≤ 32 rồi ghi lại.

---

## Số liệu chính (job khảo sát `probe_06_design`, chạy trên cụm 24/10)
| | train | val | test |
|---|---|---|---|
| Sự kiện view / favorite / cook / rate | 15.262.035 / 1.157.523 / 1.948.200 / 662.536 | 1.712.600 / 116.153 / 221.403 / 69.971 | 1.663.299 / 111.796 / 213.239 / 66.388 |
| User có hoạt động / có nấu / có chấm | 46.562 / 46.130 / 43.998 | 43.010 / 38.796 / 27.402 | 43.687 / 39.012 / 27.056 |
| User có nấu, theo số sự kiện ở train: 0 / 1–19 / 20–99 / ≥ 100 | – | 1.276 / 705 / 3.416 / 33.399 | 2.690 / 662 / 3.223 / 32.437 |
| User có nấu nhưng chưa từng nấu ở train | – | 1.588 | 2.974 |
| User có chấm nhưng chưa từng chấm ở train | – | 1.579 | 2.481 |

- User đăng ký trong năm mô phỏng: 13.991; đăng ký từ 08/2026 trở đi: 3.188.
- Món có tương tác ở train: 5.499/5.499. Món được nấu ở test mà chưa xuất hiện ở train: 0.
- Cặp (user, món) trong train: 10.553.139.
- Cặp được nấu ở test: 204.975. Trong đó 56,65% đã gặp ở train, 26,86% đã nấu ở train.
- Số món khác nhau mỗi user nấu ở test (p25 / p50 / p90): 2 / 4 / 11.
- Phiên mâm cơm ở train: 250.908, trung bình 2,35 món. Nguyên liệu trung bình mỗi món: 9,95.

## Lỗi / sự cố và cách xử lý
- Lần chạy job khảo sát đầu tiên không lấy được kết quả: dòng in ra bị dính sau thanh tiến trình của Spark nên `grep "^PROBE"` không khớp. Đã chạy lại và lấy bằng `grep -o`.
- Replication 3 trên HDFS: chưa sửa, chờ câu hỏi 1.

## Cần người dùng quyết định
1. **Replication:** đề xuất thêm `spark.hadoop.dfs.replication=2` vào `get_spark()` và chạy `hdfs dfs -setrep -R -w 2 /data`. Làm trước khi bước 06 ghi dữ liệu, để ảnh chụp HDFS UI không báo thiếu bản sao. Đồng ý không?
2. **`/data/events/events_csv`** (1,4GB) là bản CSV của lần chạy 04 đầu tiên, đã cũ so với events hiện tại. Đề xuất xóa ngay, rồi sinh lại bằng `--csv` khi đo hiệu năng. Đồng ý không?
3. **Món mới:** có làm thí nghiệm giả lập không? Cách làm: ẩn mọi tương tác ở train của 300 món ngẫu nhiên, rồi đo hybrid/content gợi ý được những món đó tới đâu. Đề xuất: có, làm ở cuối 06f.
4. **Giao thức đánh giá:**
   - "Món liên quan" là món được nấu trong tháng đánh giá.
   - Bảng chính không loại món đã gặp, có thêm biến thể khám phá.
   - Train lại trên train + val trước khi đo test.

   Chốt như vậy không?
5. **Trọng số implicit** 1 / 3 / 5 (view / favorite / cook) và **chuẩn hóa hybrid theo hạng**. Đồng ý không, hay muốn dò cả trọng số implicit?
6. **Tên module dùng chung:** `src/rec_common.py`, hay gộp vào `common.py`? Đề xuất tách riêng.
7. **Thí nghiệm đối chứng 06g** (ratings gốc): làm hay bỏ?

Sau khi chốt, nội dung thiết kế sẽ ghi thành D12 trong DECISIONS rồi mới viết code.

## Commit
- `9737df1`: bản đề xuất thiết kế đầu tiên (rút gọn).
- `bc210e3`: bỏ giới hạn độ dài LAST_RUN.
- Commit tiếp theo: file này (bản thiết kế đầy đủ). Message: `Buoc 06: thiet ke day du trong LAST_RUN`.
