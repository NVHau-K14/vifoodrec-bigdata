# Từ điển dữ liệu

Khi thêm hoặc đổi bảng, cập nhật file này. Kiểu cột ghi theo Spark.

## Vị trí trên HDFS (`hdfs://namenode:8020`)
```
/data/raw/                       4 CSV gốc (bước 01)
/data/curated/foods/             foods_v2 – danh mục món đã làm sạch (bước 02)
/data/curated/ratings_original/  ratings gốc đã sửa id (bước 02, hiện không dùng)
/data/features/dish_features/    đặc trưng món (bước 03)
/data/events/users/              hồ sơ user mô phỏng (bước 04)
/data/events/users_truth/        persona thật – CHỈ để kiểm chứng (bước 04)
/data/events/events/month=YYYY-MM/   sự kiện hành vi, 12 partition (bước 04)
/data/events/events_csv/         bản CSV của events, chỉ để so sánh dung lượng (bước 04 --csv)
/data/results/analysis/<bảng>/   kết quả phân tích hành vi (bước 05), mỗi bảng 1 file Parquet
/data/results/models/<bảng>[_val|_test]   bảng trung gian và kết quả bước 06 (xem mục bên dưới)
/data/models/{als_implicit,als_explicit,content_pipeline,kmeans}   model Spark đã lưu (bước 06)
```
Chạy `--local` thì cùng cấu trúc đó nằm trong `data/hdfs_local/`. Các bản sao nhỏ để xem trên máy nằm trong `data/processed/`.

## Dữ liệu gốc (`data/raw/`, ViFoodRec)
| File | Dòng | Ghi chú |
|---|---|---|
| `food_dataset_cookyweb.csv` | 4.296 | Thô, từ Cooky |
| `food_dataset_mnmnweb.csv` | 1.213 | Thô, từ Món Ngon Mỗi Ngày. Có thêm Sơ chế, Cách dùng, Mách nhỏ. Có ô nhiều dòng |
| `foods.csv` | 4.000 | Bản clean của tác giả, chỉ dùng để lấy `food_id` cũ |
| `ratings.csv` | 182.678 | `userId, foodId, rating`, nhiễu ngẫu nhiên (xem D02) |

## foods – `/data/curated/foods` (5.499 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `food_id` | int | Khóa chính. 0–3999: id gốc; 4001–5503: món mới |
| `dish_name` | string | Tên món, đã chuẩn hóa NFC và sửa lỗi viết hoa |
| `description` | string | Mô tả |
| `dish_type` | string | Nhãn gốc, **không đáng tin**. Dùng `dish_type_fixed` |
| `serving_size` | double | Số người ăn. Rỗng nếu ghi sai |
| `cooking_time` | int | **Số ngẫu nhiên**, không dùng |
| `ingredients` | string | Chuỗi nguyên liệu gốc, có định lượng |
| `ingredient_list` | array<string> | Tên nguyên liệu, đã bỏ định lượng và thương hiệu |
| `preparation`, `serving_tips`, `tips` | string | Chỉ món MNMN có |
| `cooking_method` | string | Văn bản cách làm |
| `dish_tags` | array<string> | Tags, chữ thường, đã bỏ trùng |
| `calories`, `fat`, `fiber`, `sugar`, `protein` | int | **Số ngẫu nhiên**, chỉ dùng để lọc hoặc minh họa |
| `image_link` | string | Ảnh món, dùng cho dashboard (19 món không có ảnh) |
| `source` | string | `cooky` hoặc `mnmn` |
| `source_stt` | int | Số thứ tự trong file raw |
| `in_original_clean` | boolean | Có trong `foods.csv` gốc |
| `dup_name_group` | double | Nhóm các món trùng tên nhưng khác công thức (372 dòng) |

## ratings_original – `/data/curated/ratings_original` (182.556 dòng)
`user_id` int, `food_id` int, `rating` double (0–5, bước 0,5). Hiện không dùng (D06).

## dish_features – `/data/features/dish_features` (5.499 dòng)
| Cột | Kiểu | Giá trị |
|---|---|---|
| `food_id`, `dish_name`, `source` | | Như bảng foods |
| `proteins` | array<string> | Mọi nhóm đạm có trong món |
| `main_protein` | string | heo, hải sản, đậu hũ/chay, cá, gà, bò, rau củ, trứng, vịt, thịt khác, không |
| `cooking_methods` | array<string> | Mọi cách chế biến có trong món |
| `main_method` | string | hầm/nấu, chiên, nướng, xào, kho/rim, hấp, trộn/gỏi, luộc, pha/xay, khác |
| `dish_category` | string | món chính, bánh, chè/tráng miệng, bún/phở/mì/miến, canh/súp, gỏi/salad, cơm/xôi/cháo, đồ uống, lẩu, ăn vặt |
| `dish_type_fixed` | string | Món mặn, Món ngọt, Món chay, Đồ uống |
| `is_vegetarian` | boolean | Không có nguyên liệu động vật. Món ngọt và đồ uống cũng có thể là true |
| `is_spicy` | boolean | Có ớt, tiêu… |
| `n_ingredients` | int | Số nguyên liệu |
| `method_words` | int | Số chữ trong phần cách làm, đo độ phức tạp |
| `is_quick` | boolean | Món nhanh, xếp hạng trong từng nguồn (D05) |
| `season` | string | không, nóng, lạnh, tết |
| `meal_types` | array<string> | sáng, trưa, tối, ăn vặt |

## users – `/data/events/users` (50.000 dòng). Mô hình **được** dùng
| Cột | Kiểu | Giá trị |
|---|---|---|
| `user_id` | int | 1–50000 |
| `region` | string | Bắc, Trung, Nam |
| `age_group` | string | 18-24, 25-34, 35-44, 45+ |
| `gender` | string | nam, nữ |
| `device` | string | android, ios, web |
| `signup_date` | date | 28% user đăng ký trong khoảng 10/2025–09/2026 (user mới, dùng cho cold-start) |

## users_truth – `/data/events/users_truth` (50.000 dòng). **Chỉ để kiểm chứng, mô hình không được dùng**
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `user_id` | int | |
| `persona_main`, `persona_sub` | string | ăn chay, tập gym, ăn kiêng, mê hải sản, bận rộn, hảo ngọt, gia đình truyền thống, thích cay/nhậu |
| `sessions_per_year` | double | Mức hoạt động |
| `rate_prob` | double | Xác suất chấm điểm sau khi nấu |
| `churned` | boolean | User rời bỏ (12%) |
| `last_active_date` | date | Ngày hoạt động cuối |

## events – `/data/events/events` (23.164.109 dòng, partition theo `month`)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `user_id` | int | |
| `food_id` | int | |
| `event_type` | string | view, favorite, cook, rate |
| `ts` | timestamp | Giờ Việt Nam (`spark.sql.session.timeZone = Asia/Ho_Chi_Minh`) |
| `meal_slot` | string | sáng (6–9h), trưa (10–13h), tối (16–20h), khuya (21–24h) |
| `session_id` | long | `user_id × 10000 + số thứ tự phiên`, tăng dần theo thời gian |
| `rating` | float | 0,5–5, chỉ có ở `rate`, các loại khác là null |
| `month` | string | `2025-10` … `2026-09` (cột partition) |

**Chia dữ liệu cho mô hình:** train từ `2025-10` đến `2026-07`, validation `2026-08`, test `2026-09`.
Mỗi cặp user–món có tối đa một `favorite` và một `rate`. Một món có thể được `view` và `cook` nhiều lần.

## Kết quả phân tích – `/data/results/analysis/` (bước 05)
Tính trên **cả 12 tháng**, chỉ để mô tả. Bước 06 không lấy các bảng này làm đặc trưng hay baseline, vì chứa cả tháng validation và test.
Mỗi bảng có thêm bản JSON cùng tên trong `data/output/analysis/`. Hai bảng lớn chỉ xuất phần đầu: `dish_stats` 100 dòng, `top_ingredients` 200 dòng.

| Bảng | Khóa / cột chính | Nội dung |
|---|---|---|
| `heatmap_hour_dow` | `dow_idx` (1 = T2 … 7 = CN), `dow_vn`, `hour`, `views`, `cooks`, `events` | Heatmap giờ × thứ |
| `trend_month_category` | `month`, `dish_category`, `views`, `cooks`, `cook_share_pct` | Tỷ trọng lượt nấu của từng nhóm món trong tháng |
| `season_month` | `month`, `region` (thêm `Tất cả`), `season`, `cooks`, `share_pct` | Tỷ trọng món theo nhãn mùa (tết, lạnh, nóng) |
| `top_dish_by_slot` | `meal_slot`, `rk`, `rk_lift`, `food_id`, `dish_name`, `dish_category`, `cooks`, `share_pct`, `lift`, `image_link` | Mỗi bữa có 2 kiểu xếp hạng: `rk` ≤ 10 là món nấu nhiều nhất, `rk_lift` ≤ 10 là món đặc trưng của bữa (lift cao nhất, chỉ xét 200 món nấu nhiều nhất của bữa) |
| `lift_by_group` | `group_type` (meal_slot, day_type, region, age_group), `group_value`, `attribute`, `value`, `cooks`, `share_pct`, `overall_pct`, `lift` | Lift = tỷ trọng trong nhóm / tỷ trọng chung (tính theo lượt nấu) |
| `funnel_by_category` | `dish_category` (thêm `Tất cả`), `*_events`, `*_pairs`, `favorite_per_view_pct`, `cook_per_view_pct`, `rate_per_cook_pct`, `avg_rating` | Phễu đếm theo sự kiện và theo cặp user–món |
| `dish_stats` | `food_id`, các đặc trưng món, `views`, `favorites`, `cooks`, `rates`, `avg_rating`, `image_link`, `cook_rank` | Số liệu từng món (5.499 dòng) |
| `catalog_vs_cooked` | `attribute` (main_method, dish_category, main_protein), `value`, `n_dishes`, `cooks`, `catalog_pct`, `cook_pct`, `cooks_per_dish`, `lift` | So tỷ trọng trong danh mục với tỷ trọng lượt nấu |
| `top_ingredients` | `ingredient`, `n_dishes`, `cooks`, `is_seasoning`, `cook_rank` | Nguyên liệu tính theo số lượt nấu của các món chứa nó |
| `rating_dist` | `rating`, `count`, `share_pct` | Phân bố điểm chấm |
| `session_size` | `meal_slot` (thêm `Tất cả`), `size` (1, 2, 3, 4+), `count`, `share_pct` | Số món mỗi phiên nấu ("mâm cơm") |
| `repeat_by_category` | `dish_category` (thêm `Tất cả`), `cooked_pairs`, `repeat_pairs`, `avg_times`, `repeat_pct` | Tỷ lệ nấu lại cùng một món |
| `user_activity` | `ord`, `cooks_per_user` (0, 1-5, …, >100), `users`, `avg_events`, `share_pct` | Phân bố mức hoạt động của user |
| `long_tail_curve` | `dish_pct` 1–100, `views_cum_pct`, `cooks_cum_pct` | Đường tích lũy: x% món phổ biến nhất chiếm bao nhiêu % lượt |

## Bước 06 – `/data/results/models/` (D12)
Hậu tố `_val`: lịch sử là train (10/2025–07/2026), đánh giá tháng 08/2026. Hậu tố `_test`: lịch sử là train + val (đến 08/2026), đánh giá tháng 09/2026. Bảng không có hậu tố thì không phụ thuộc view.

| Bảng | Bước | Cột chính | Nội dung |
|---|---|---|---|
| `implicit_<v>` | 06a | `user_id, food_id, n_view, n_favorite, n_cook, n_rate, last_ts` | Ma trận implicit tính từ lịch sử |
| `ratings_<v>` | 06a | `user_id, food_id, rating` | Các dòng `rate` trong lịch sử |
| `user_groups_<v>` | 06a | `user_id, region, age_group, n_events, n_cooks, n_rates, group, is_eval, tune` | Nhóm theo số sự kiện trong lịch sử: lạnh = 0, ít = 1–19, ấm ≥ 20. `tune` đánh dấu mẫu 10.000 user dùng để dò tham số |
| `truth_<v>` | 06a | `user_id, items, group, region, age_group, tune` | Món **nấu** trong tháng đánh giá (đáp án) |
| `truth_rate_<v>` | 06a | `user_id, food_id, rating` | Các dòng `rate` trong tháng đánh giá |
| `pop_<v>` | 06a | `kind` (chung, 2 tháng cuối, vùng-tuổi), `region, age_group, food_id, cooks, rank` | Top 100 popularity |
| `item_pop_<v>` | 06a | `food_id, cooks, share` | Lượt nấu của cả 5.499 món (dùng cho novelty) |
| `user_features_<v>` | 06a | `n_events, n_sessions, share_*, slot_0..3, share_weekend, cat_entropy, avg_rating, pref_slot…` | Đặc trưng hành vi của user (K-means, ngữ cảnh) |
| `recs_<model>_<v>` | 06b, 06c, 06f | `user_id, food_id, rank, score` (content có thêm `because_food_id`; hybrid có thêm `source`) | Top 100. View val gồm user được đánh giá; view test gồm mọi user (content: user có lịch sử). `model` ∈ random, pop_chung, pop_gan_day, pop_vung_tuoi, nau_lai, als_implicit, content, hybrid, **hybrid_c2** (hybrid + content ở vị trí 9–10, `source = content_slot`; D13) |
| `eval_<model>_<v>` | 06b, 06c, 06f | `user_id, group, n_truth, n_pred, p@k, r@k, ndcg@k, ap@k` (k = 5, 10) | Độ đo của **từng user**, dùng để tính khoảng tin cậy |
| `item_tokens` | 06c | `food_id, tokens` | Tập token của món (trong từ điển, minDF = 2) |
| `item_sim` | 06c | `food_id, sim_food_id, sim, jaccard, rank` | 50 món tương tự nhất theo cosine TF-IDF (tính chính xác) |
| `rules_ingredients`, `ingredient_edges` | 06d | `variant` (giữ / bỏ gia vị), `antecedent, consequent` hoặc `src, dst`, `confidence, lift, support` | Luật nguyên liệu, cạnh 1 → 1 cho đồ thị mạng |
| `rules_meal`, `companion` | 06d | `food_id, companion_id, rank, confidence, lift` | Luật "mâm cơm" và tối đa 5 món ăn kèm cho mỗi món |
| `user_clusters` | 06e | `user_id, cluster_k3, cluster_k8, cluster_k11` | Cụm của user. **Dashboard dùng `cluster_k8`** (D13) |
| `cluster_profile` | 06e | `k` (3, 8, 11), `cluster, n_users`, trung bình từng đặc trưng, `persona_pho_bien_kiem_chung, persona_share` | Hồ sơ cụm. Cột persona chỉ để kiểm chứng |
| `recs_final` | 06f | `user_id, rank, food_id, score, source, reason_type, because_food_id, reason` | **Gợi ý cuối**: top 50 cho mọi user, lấy từ `hybrid_c2`. `source` ∈ als, rep, pop, content_slot. Vị trí content: `score` là null, `because_food_id` là món đã nấu giống nhất (không có thì là món đã xem). Bước 07 xuất bảng này |
| `metrics` | 06f | `view, model, variant, group, metrics` (JSON) | Bảng độ đo tổng hợp |

## File trong `data/output/`
| File | Nội dung |
|---|---|
| `clean_report.json` | Số liệu từng bước làm sạch |
| `features_report.json` | Độ phủ và phân bố từng thuộc tính món |
| `features_check_sample.csv` | 100 món để kiểm tra tay (cột `kiem_tra`, `ghi_chu`) |
| `simulate_report.json` | Số sự kiện, phễu, rating, kiểm tra persona, mùa, dung lượng HDFS |
| `simulate_config.json` | Toàn bộ tham số và trọng số persona |
| `events_sample.csv` | Toàn bộ sự kiện của 200 user |
| `analysis_report.json` | Số liệu chính của bước 05: kiểm tra tổng, phễu theo user, lift nổi bật, đuôi dài, thời gian từng phần |
| `analysis/*.json` | Bản JSON của các bảng kết quả bước 05 (cho dashboard) |
| `analysis/explain.txt` | Kế hoạch thực thi của truy vấn phễu và truy vấn lọc theo tháng (dùng cho báo cáo) |
| `model_split_report.json`, `model_als_report.json`, `model_content_report.json`, `model_hybrid_report.json`, `model_fpgrowth_report.json`, `model_kmeans_report.json`, `model_control_report.json` | Report từng file của bước 06 |
| `models_metrics.json` | Bảng tổng hợp độ đo xếp hạng (chính, khám phá, ngoài độ chính xác) và khoảng tin cậy 95% |
