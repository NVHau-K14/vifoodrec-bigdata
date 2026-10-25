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
| `api_report.json` | Bước 08: `latency.<database>` (do `api/bench_latency.py` ghi: p50/p95/p99/max, req/s, `server_app_p95_ms`, `server_db_mean_ms` từng endpoint, mục tiêu p95 và `pass`, vòng E19 10 luồng × 100), `docker_stats_api`, `page_load_1440` (thời gian tải 7 trang), `screenshots` |
| `export_report.json` | Bước 07: số doc, cách ghi, thời gian ghi, `collStats` (size, storageSize, index) từng collection, các kiểm tra (múi giờ, toàn vẹn tham chiếu, 5 user mẫu), `explain()` của 4 truy vấn tiêu biểu, nội dung `overview`. Chạy `--only` thì gộp vào report cũ cùng database và thêm `partial_runs [{only, at, timings_s}]`; kiểm tra `recs_because_cooked` đếm phần tử theo `source` và `because_cooked` |

## MongoDB – database `vifood` (bước 07, D14)
Ghi bằng `src/07_export_mongo.py`. Chạy `--local` thì ghi vào database `vifood_local`, cùng cấu trúc. Xem dữ liệu ở http://localhost:8090 (mongo-express, tài khoản trong `.env`).
Mốc của dashboard là **01/09/2026**: `recs`, `users.history` và `users.profile` dùng lịch sử đến hết 08/2026.
Ngày giờ lưu dạng chuỗi theo giờ Việt Nam (`"yyyy-MM-dd"`, `"yyyy-MM-dd HH:mm"`). `NaN` lưu thành `null`.

| Collection | `_id` | Số doc | Trường chính | Index (ngoài `_id`) |
|---|---|---|---|---|
| `dishes` | `food_id` | 5.499 | Các cột của `foods` (bỏ `dish_type`, `cooking_time`, `source_stt`, `in_original_clean`, `dup_name_group`) và `dish_features`; `name_search` (tên chữ thường, không dấu, "đ" → "d"); `nutrition {calories, fat, fiber, sugar, protein}` (**số ngẫu nhiên, không hiển thị**); `stats {views, favorites, cooks, rates, avg_rating, cook_rank}` (**cả năm mô phỏng**, chỉ để mô tả); `companions [{rank, food_id, confidence, lift}]` (≤ 3 món, 656 món có) | text `text_ten_mon` (`name_search`, `dish_name`, `default_language: none`); `name_search`; `{is_vegetarian, stats.cook_rank}`; `{is_quick, stats.cook_rank}`; `{meal_types, stats.cook_rank}`; `{dish_category, stats.cook_rank}`; `stats.cook_rank` |
| `recs` | `user_id` | 50.000 | `items [{rank, food_id, score, source, because_food_id, because_cooked?}]`, đúng 50 món theo `rank`. `source` ∈ als, rep, pop, content_slot (bản cụm không có `rep`; bản local có). `because_cooked` (bool, D15) **chỉ có ở phần tử `content_slot`**: true khi món lý do là món đã nấu (cụm: 93.137 true, 3.209 false). Không có chuỗi lý do: API sinh câu lý do từ `source`, `because_food_id` và `because_cooked` | – |
| `similar` | `food_id` | 5.499 | `items [{rank, food_id, sim, jaccard}]`, 50 món tương tự (cosine TF-IDF) | – |
| `users` | `user_id` | 50.000 | `region, age_group, gender, device, signup_date`; `group` (lạnh/ít/ấm); `cluster_k3/k8/k11` (null với 3.870 user); `profile {n_events, n_cook, n_rate, avg_rating, share_chay, share_haisan, share_ngot, share_nhanh, share_cay, pref_slot}`; `history [{food_id, n_cook, last_cook}]` (≤ 10 món, xếp theo `n_cook` rồi `last_cook` giảm dần); `test_cooks [food_id]` (món nấu tháng 09/2026, chỉ 39.012 user có); `truth {persona_main, persona_sub}` (**chỉ để kiểm chứng, endpoint gợi ý không trả trường này**) | `cluster_k8`; `{region, age_group}`; `truth.persona_main` |
| `popular` | `"chung"`, `"2 tháng cuối"`, `"vùng-tuổi\|<vùng>\|<tuổi>"` | 14 | `kind, region, age_group, items [{rank, food_id, cooks}]` (top 100 của `pop_test`) | – |
| `clusters` | `"k<k>_c<cụm>"` | 22 | `k, cluster, n_users, features {18 đặc trưng trung bình}, persona_kiem_chung, persona_share` | `{k, cluster}` |
| `meal_rules` | ObjectId | 677 | `antecedent [food_id], consequent [food_id], confidence, lift, support` | `antecedent`; `consequent` |
| `ingredient_rules` | ObjectId | 2.999 | `variant, antecedent [str], consequent [str], confidence, lift, support` | `{variant, lift -1}` |
| `ingredient_edges` | ObjectId | 416 | `variant, src, dst, confidence, lift, support` | `{variant, lift -1}` |
| `analysis_<bảng>` | ObjectId | 5.783 (13 collection) | Mỗi dòng của 13 bảng bước 05 (trừ `dish_stats`) là 1 doc, cùng cột như trên HDFS. `top_ingredients` có đủ 4.538 dòng | `lift_by_group {group_type, group_value}`; `top_dish_by_slot {meal_slot, rk}`; `trend_month_category {month}`; `season_month {region, month}`; `top_ingredients {cook_rank}` |
| `metrics` | ObjectId | 117 | `view, model, variant, group, metrics {n_users, p@5, r@5, ndcg@5, ap@5, p@10, …}` | `{view, variant, model}` |
| `reports` | tên file (vd `model_als_report`) | 12 | `file, content` (nội dung JSON; dấu chấm trong tên trường đổi thành dấu phẩy, vd `"4,0"`) | – |
| `overview` | `"overview"` | 1 | `n_dishes, n_users, n_events, events_by_type, event_months, n_recs_rows, hdfs {thư mục: bytes, bytes_with_replicas, files}, reference_date, exported_at, notes` | – |
| `trending` | | 0 | Để dành cho Structured Streaming | `window_end -1` |

## API bước 08 (`api/`, D15)
FastAPI đọc MongoDB (database `MONGO_DB`), phục vụ `/api/...` và `web/` tĩnh trên http://localhost:8000. Schema đầy đủ ở http://localhost:8000/docs.
Mọi response có header `Server-Timing: app;dur=<ms>, db;dur=<ms>`. Lỗi: 404 (không có user/món/endpoint), 422 (tham số sai), 503 (không kết nối được MongoDB).
Bộ lọc món **F** (query): `veg`, `quick`, `not_spicy` (bool), `meal` ∈ sáng, trưa, tối, ăn vặt, `category` ∈ 10 nhóm món.
**DishCard**: `food_id, dish_name, image_link, dish_category, dish_type_fixed, is_vegetarian, is_quick, is_spicy, meal_types` (không có `nutrition`).

| # | Endpoint | Collection | Đợt |
|---|---|---|---|
| E0 | `GET /api/health` | `ping`, số doc `dishes/users/recs` | 1 |
| E1 | `GET /api/overview` | `overview`, `reports` (tiến độ pipeline suy ra từ report), `trending` | 1 |
| E2 | `GET /api/behavior/heatmap?metric=cooks\|views\|events` | `analysis_heatmap_hour_dow` | 1 |
| E3 | `GET /api/behavior/monthly?region=` | `analysis_trend_month_category`, `analysis_season_month`, `reports.model_split_report` | 1 |
| E6 | `GET /api/behavior/funnel` | `analysis_funnel_by_category`, `reports.analysis_report` | 1 |
| E12 | `GET /api/dishes/search?q=&limit=` | `dishes` (`$regex` trên `name_search`) | 1 |
| E13 | `GET /api/dishes/{food_id}?n_similar=` | `dishes`, `similar` | 1 |
| E14 | `GET /api/dishes?F&skip&limit` | `dishes` (xếp theo `stats.cook_rank`) | 1 |
| E17 | `GET /api/users/demo` | `users` (3 user/nhóm, 2 user/persona kèm `verify_only: true`) | 1 |
| E18 | `GET /api/users/{user_id}` | `users` (projection `{truth: 0}`), không có persona | 1 |
| E19 | `GET /api/recs/{user_id}?F&limit` | `recs`, `users`, `dishes` (`$in` + F, bù món `$nin` + `stats.cook_rank`) | 1 |
| E20 | `POST /api/recs/new-user` body `{food_ids, region?, age_group?, limit?, F}` | `similar`, `dishes`, `popular` | 1 |
| E22 | `GET /api/meta/filters` | `distinct` trên `dishes`, `users` | 1 |
| E23 | `GET /api/eval/ranking?view&variant&group` | `metrics`, `reports.models_metrics` | 1 |
| E24 | `GET /api/eval/details` | `reports` (ALS, content, FP-Growth, đối chứng, hybrid, K-means, thời gian) | 1 |
| E26 | `GET /api/reports/{name}` | `reports` | 1 |
| E4 | `GET /api/behavior/top-dishes?slot=sáng\|trưa\|tối\|khuya&by=cooks\|lift&limit≤10` | `analysis_top_dish_by_slot` (cache), thẻ món từ `dishes` | 2 |
| E5 | `GET /api/behavior/lift?group_type&attribute&min_cooks` | `analysis_lift_by_group` (cache). `cells[].lift` = null khi `cooks < min_cooks` (mặc định 1.000) | 2 |
| E7 | `GET /api/behavior/habits` | `analysis_session_size`, `analysis_repeat_by_category`, `analysis_user_activity`, `analysis_rating_dist`, `reports.analysis_report` (cache) | 2 |
| E8 | `GET /api/dishes/summary` | `$facet` trên `dishes` (cache) + `analysis_catalog_vs_cooked`, `analysis_long_tail_curve`, `reports.analysis_report` | 2 |
| E10 | `GET /api/ingredients/top?limit≤50&seasoning` | `analysis_top_ingredients` (index `cook_rank`) | 2 |
| E11 | `GET /api/ingredients/graph?variant=bỏ gia vị\|giữ gia vị&limit≤150` | `ingredient_edges` (index `variant, lift -1`) | 2 |
| E15 | `GET /api/segments?k=3\|8\|11` | `clusters` (cache), `reports.model_kmeans_report`. Mỗi cụm: `features`, `z` (độ lệch giữa các cụm), `label`, `top_features`, `strategy` (luật D16), `persona_kiem_chung` + `verify_only` | 2 |
| E16 | `GET /api/segments/8/{cluster}?sample≤12` | `users` (`$match cluster_k8` theo index + `$facet`), không có persona | 2 |
| E25 | `GET /api/trending?limit&windows` | `trending` (index `window_end -1`); rỗng thì `status = "chưa chạy"` | 2 |

**RecItem** (E19, E20) = DishCard + `rank, rec_rank, source (als|content_slot|pop|fill|rep|content), dot (herb|chili|neutral), reason, because {food_id, dish_name}?, hit, n_cook_before`. `n_cook_before` (chỉ E19): số lần đã nấu trước 01/09/2026 nếu món nằm trong `users.history` (10 món nấu nhiều nhất), không thì null; dashboard hiện chip "Bạn đã nấu N lần". `summary {from_recs, from_fill, from_popular, hits, n_test_cooks}`.
