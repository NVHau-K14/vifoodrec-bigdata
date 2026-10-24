# Lần chạy gần nhất – 25/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số đếm dòng lấy từ HDFS (job dò chạy local trong container `jupyter`), kích thước BSON đo bằng `bson.encode` trên mẫu thật.

## Yêu cầu
Làm việc tiếp theo trong PROGRESS: **bước 07 (xuất MongoDB), thiết kế trước, chưa viết code.** Ghi bản đề xuất vào file này để chat claude.ai góp ý; sau khi chốt thì ghi thành D14 rồi mới viết `src/07_export_mongo.py`.

## Đã làm
- Kiểm tra cụm: đủ 9 container đang chạy. MongoDB 7.0.45 đang **trống** (database `vifood` chưa có collection). `pymongo` 4.19.0 đã có sẵn trong image Spark (cả jupyter lẫn 2 worker dùng chung image).
- Chạy 2 job dò, chỉ đọc, không ghi gì lên HDFS hay MongoDB:
  - đếm dòng và đọc schema 16 bảng sẽ xuất;
  - dựng thử document theo từng phương án trên mẫu thật (500 user, toàn bộ 5.499 món, 300 món cho `similar`), đo kích thước BSON.
- Viết bản thiết kế bên dưới. **Chưa viết code, chưa sửa compose.**

---

## BẢN THIẾT KẾ BƯỚC 07

### 1. Nguyên tắc chung
- MongoDB là **tầng phục vụ** cho API và dashboard: chỉ chứa kết quả đã tính xong (bảng nhỏ, gợi ý, số liệu). Sự kiện thô (23,2 triệu dòng) và các bảng trung gian của bước 06 (`implicit_*`, `recs_<model>_*`, `eval_*`) **không** xuất, vẫn chỉ nằm trên HDFS.
- Mốc thời gian của dashboard là **01/09/2026**: `recs_final` dùng lịch sử đến hết 08/2026 (view test), nên lịch sử nấu của user trong MongoDB cũng cắt ở mốc này (lấy từ `implicit_test`).
- Khóa `_id` dùng chính khóa nghiệp vụ (`food_id`, `user_id`), không dùng ObjectId. Như vậy chạy lại ra đúng cùng document, và tra theo khóa không cần thêm index.
- Tên collection và tên trường giữ như trên HDFS (tiếng Anh, chữ thường), giá trị giữ tiếng Việt có dấu.

### 2. Danh sách collection

| Collection | Nguồn trên HDFS | Số document | Cỡ TB/doc (đo) | Tổng (BSON, chưa nén) |
|---|---|---|---|---|
| `dishes` | `foods` + `dish_features` + `dish_stats` + `companion` | 5.499 | 2.802 B (lớn nhất 7.819 B) | 15,4 MB |
| `recs` | `recs_final` | 50.000 | 4.052 B | 202,6 MB |
| `similar` | `item_sim` | 5.499 | 3.116 B | 17,1 MB |
| `users` | `users` + `user_clusters` + `user_features_test` + `implicit_test` (lịch sử) | 50.000 | 858 B | 42,9 MB |
| `popular` | `pop_test` | 14 | | nhỏ |
| `clusters` | `cluster_profile` | 22 | | nhỏ |
| `meal_rules` | `rules_meal` | 677 | | nhỏ |
| `ingredient_rules` | `rules_ingredients` | 2.999 | | nhỏ |
| `ingredient_edges` | `ingredient_edges` | 416 | | nhỏ |
| `analysis_<bảng>` (13 collection) | 13 bảng của bước 05 (trừ `dish_stats`, đã gộp vào `dishes`) | 5.783 dòng tổng (`top_ingredients` 4.538) | | nhỏ |
| `metrics` | `metrics` (bước 06f) | 117 | | nhỏ |
| `reports` | các file `data/output/*report*.json` và `models_metrics.json` | khoảng 15 | | nhỏ |
| `overview` | đếm từ HDFS lúc xuất | 1 | | nhỏ |
| `trending` | (để dành cho Structured Streaming, bước 07 chỉ tạo index) | 0 | | |

**Tổng khoảng 280 MB BSON chưa nén.** WiredTiger nén snappy nên trên đĩa sẽ nhỏ hơn; số thật sẽ lấy từ `collStats` sau khi ghi. Cache 1 GB của MongoDB chứa đủ toàn bộ, nên **giữ nguyên** giới hạn 1,5 GB RAM và cache 1 GB.

### 3. Schema từng collection

**`dishes`** (1 document = 1 món)
```js
{
  _id: 2103,                                // food_id
  dish_name: "Cà Tím Xào Tỏi", name_search: "ca tim xao toi",
  source: "cooky", image_link: "...", description: "...",
  dish_type_fixed: "Món chay", dish_category: "món chính",
  main_protein: "rau củ", proteins: [...], main_method: "xào", cooking_methods: [...],
  is_vegetarian: true, is_spicy: false, is_quick: true, season: "không", meal_types: ["trưa","tối"],
  n_ingredients: 8, method_words: 120, serving_size: 2,
  ingredient_list: [...], ingredients: "...", dish_tags: [...],
  cooking_method: "...", preparation: "...", serving_tips: "...", tips: "...",
  nutrition: { calories, fat, fiber, sugar, protein },   // so ngau nhien, xem cau hoi 3
  stats: { views, favorites, cooks, rates, avg_rating, cook_rank },  // ca 12 thang (buoc 05)
  companions: [ { food_id, rank, confidence, lift } ]    // toi da 3 mon, chi 656 mon co
}
```
- Bỏ `cooking_time` (số ngẫu nhiên), `source_stt`, `in_original_clean`, `dup_name_group` (chỉ dùng khi làm sạch).
- `name_search`: tên món chữ thường, bỏ dấu, đổi "đ" thành "d". Tạo bằng `lower()` + `translate()` có sẵn của Spark, không cần UDF. Lý do: text index của MongoDB không coi "đ" là chữ có dấu, nên gõ "dau hu" sẽ không ra "Đậu hũ" nếu chỉ dựa vào tên gốc.
- Văn bản dài (cách làm, nguyên liệu, mẹo) để chung trong document. Trang danh sách dùng projection chỉ lấy vài trường; khi bỏ các trường văn bản dài, document còn trung bình 1.003 B.
- `companions` chỉ có ở 656 món (FP-Growth bữa ăn có 677 luật, mỗi món tối đa 3 món ăn kèm). Món không có thì API lấy món canh phổ biến cùng nhóm món (giống mốc so sánh của 06d). Phần này làm ở bước 08.

**`recs`** (1 document = 1 user, mảng 50 món theo thứ tự)
```js
{
  _id: 1,                                   // user_id
  items: [
    { food_id: 48,   rank: 1,  score: 0.016393, source: "als",          because_food_id: null },
    { food_id: 2103, rank: 9,  score: 0.006818, source: "content_slot", because_food_id: 2090 },
    ...
  ]
}
```
- So sánh 3 cách lưu (đo trên 500 user):

  | Cách lưu | Cỡ TB | Tổng 50.000 user / 2,5 triệu dòng |
  |---|---|---|
  | 1 doc/user, đủ cột (có chuỗi `reason`) | 8.956 B | 447,8 MB |
  | **1 doc/user, bỏ `reason` và `reason_type`** (đề xuất) | 4.052 B | 202,6 MB |
  | 1 doc/dòng | 188 B | 469,5 MB, thêm index `_id` trên 2,5 triệu khóa |

- Chọn 1 doc/user vì API luôn đọc **cả danh sách** của một user (rồi lọc theo bộ lọc), nên một lần đọc theo `_id` là đủ. Danh sách cố định 50 món nên mảng không phình ra.
- Bỏ chuỗi `reason`: nó chỉ có 3 mẫu câu, sinh lại được từ `source` và tên món `because_food_id`. Bỏ đi giảm 55% dung lượng. `reason_type` trùng với `source` nên bỏ luôn. API sinh câu lý do theo đúng mẫu của 06f.
- Lưu ý: ở các dòng `source = "als"`, `because_food_id` đôi khi có giá trị (do 06f lấy từ bảng content của hybrid), nhưng câu lý do của ALS không dùng đến. API chỉ hiện "Giống món X bạn đã nấu" khi `source = "content_slot"`.
- Không lưu tên và ảnh món trong `recs`: API lấy 50 `food_id` rồi đọc `dishes` bằng `$in` (hoặc `$lookup`), vì danh mục chỉ có 5.499 món.

**`similar`** (1 document = 1 món, 50 món tương tự theo cosine TF-IDF)
```js
{ _id: 2090, items: [ { food_id, sim, jaccard, rank }, ... 50 ] }
```
- Dùng cho mục "món tương tự" và cho **gợi ý user mới** (chọn vài món mình thích): API đọc `similar` của các món đã chọn, cộng điểm `sim`, bỏ món đã chọn, thiếu thì bù bằng `popular`. ALS không fold-in user mới, vì vậy không xuất model ALS.

**`users`** (1 document = 1 user)
```js
{
  _id: 1, region: "Bắc", age_group: "25-34", gender: "nữ", device: "android",
  signup_date: "2024-10-18",                 // chuoi ngay, xem muc 4
  group: "ấm",                               // lanh / it / am theo lich su den 08/2026 (user_groups_test)
  cluster_k3: 0, cluster_k8: 5, cluster_k11: 7,   // null voi 3.870 user khong du lich su de phan cum
  profile: { n_events, n_cook, n_rate, avg_rating, share_chay, share_haisan, share_ngot,
             share_nhanh, share_cay, pref_slot },
  history: [ { food_id, n_cook, last_cook: "2026-08-21" }, ... ],   // toi da 10 mon nau nhieu nhat
  test_cooks: [ food_id, ... ],              // mon user THAT SU nau thang 09/2026 (truth_test), chi de demo "trung"
  truth: { persona_main, persona_sub }       // CHI de kiem chung, xem cau hoi 4
}
```
- `history` giúp người xem hiểu vì sao có các gợi ý. `test_cooks` giúp dashboard đánh dấu những món được gợi ý mà user thật sự nấu trong tháng 9, minh họa trực quan cho NDCG@10. Có 39.012 user có trường này.

**Các collection nhỏ**
- `popular`: 14 document, `_id` dạng `"chung"`, `"gan_day"`, `"vung_tuoi|Bắc|25-34"`, mỗi document có mảng `items` 100 món (`food_id`, `cooks`, `rank`). Dùng cho user lạnh, gợi ý user mới và bù khi bộ lọc làm danh sách quá ngắn.
- `clusters`: 22 document (k = 3, 8, 11), `_id` dạng `"k8_c5"`, gồm `k`, `cluster`, `n_users`, trung bình 18 đặc trưng, và `persona_kiem_chung`, `persona_share` (ghi rõ là chỉ để kiểm chứng).
- `meal_rules`: `antecedent` và `consequent` là mảng `food_id`, kèm `confidence`, `lift`, `support`.
- `ingredient_rules`, `ingredient_edges`: mỗi dòng 1 document, có trường `variant` ("giữ gia vị" hoặc "bỏ gia vị"). Đồ thị mạng nguyên liệu đọc `ingredient_edges`.
- `analysis_<bảng>`: mỗi dòng 1 document, tên collection theo tên bảng bước 05 (`analysis_heatmap_hour_dow`, `analysis_lift_by_group`…). Chọn cách này thay vì gói cả bảng vào 1 document, vì API cần lọc theo trường (ví dụ `lift_by_group` theo `group_type`, `top_dish_by_slot` theo `meal_slot`). `top_ingredients` xuất đủ 4.538 dòng, không chỉ 200 dòng như file JSON.
- `metrics`: 117 dòng, chuỗi JSON ở cột `metrics` được tách thành document con để truy vấn được (ví dụ `metrics.ndcg@10`). Khóa có dấu chấm phải đổi tên (`ndcg@10` thành `ndcg_10`), vì MongoDB không cho dấu chấm trong tên trường khi truy vấn.
- `reports`: mỗi file report là 1 document, `_id` là tên file (`model_als_report`…). Trang "Đánh giá mô hình" lấy lưới dò ALS, Silhouette theo k, recall của LSH, thí nghiệm đối chứng và khoảng tin cậy từ đây.
- `overview`: 1 document cho trang Tổng quan: số món, số user, số sự kiện theo loại, số dòng `recs`, dung lượng từng thư mục trên HDFS (đọc bằng Hadoop FileSystem API qua `spark._jvm` lúc xuất, không gọi lệnh `hdfs`), thời điểm xuất.
- `trending`: để trống, bước 07 chỉ tạo index (`window_end`) để phần Streaming ghi vào sau.

### 4. Cách ghi từ Spark
- **Dùng `pymongo`, không dùng MongoDB Spark Connector.** Connector cần tải jar vào image rồi build lại; bản hỗ trợ Spark 4.x là dòng 11.x, nhưng chưa kiểm tra chạy được với Spark 4.2.0. `pymongo` đã có sẵn ở cả driver và executor.
- **Bảng lớn (`recs`, `users`, mỗi bảng 50.000 document):** Spark gom mảng (`groupBy` + `collect_list(struct)` + `sort_array`), `repartition(8)`, rồi `foreachPartition`. Mỗi partition mở 1 `MongoClient` ở executor và `insert_many` theo lô 1.000 document, `ordered=False`. Như vậy việc ghi chạy song song trên 2 worker, có thể chụp ở Spark UI cho báo cáo.
  - Chuỗi kết nối truyền từ driver vào closure, vì container worker không đọc file `.env`.
  - Nếu Spark chạy lại một task, các document đã ghi sẽ báo trùng khóa (mã 11000). Chỉ bỏ qua đúng lỗi này, lỗi khác thì dừng job. `_id` cố định nên nội dung trùng là giống hệt.
- **Bảng nhỏ (dưới 10.000 dòng):** `collect()` về driver rồi `insert_many`.
- **Chạy lại vẫn ra cùng kết quả:** ghi vào collection tạm `<tên>__staging`, tạo index, kiểm tra số document, rồi `renameCollection(<tên>, dropTarget=True)`. Đổi tên là thao tác nguyên tử, nên API không bao giờ thấy collection ghi dở. Lỗi giữa chừng thì collection cũ vẫn còn nguyên.
- **Chuyển kiểu:**
  - Spark `date` thành chuỗi `"yyyy-MM-dd"` (BSON không mã hóa được `datetime.date`, job dò đã gặp lỗi này).
  - Timestamp (`last_ts`) thành chuỗi ngày theo giờ Việt Nam, định dạng bằng `date_format` trong Spark. Collect timestamp về Python sẽ ra giờ theo múi giờ của container, dễ lệch 7 tiếng.
  - `NaN` thành `null`, vì JSON của FastAPI không chấp nhận NaN.
- Tham số dòng lệnh: `--local` (đọc `data/hdfs_local`, ghi vào database `vifood_local` để không đè dữ liệu thật), `--only dishes,recs,...` (chỉ xuất một số collection), `--db` (mặc định lấy `MONGO_DB` = `vifood`).

### 5. Index (theo các truy vấn của API)
| Collection | Index | Truy vấn |
|---|---|---|
| `recs`, `users`, `dishes`, `similar` | `_id` (có sẵn) | lấy theo `user_id` / `food_id` |
| `dishes` | text index trên `name_search`, `dish_name` (`default_language: "none"`, vì MongoDB không có bộ tách từ tiếng Việt) | ô tìm món |
| `dishes` | `{is_vegetarian: 1, "stats.cook_rank": 1}`, `{is_quick: 1, "stats.cook_rank": 1}`, `{meal_types: 1, "stats.cook_rank": 1}` (multikey), `{dish_category: 1, "stats.cook_rank": 1}` | duyệt món theo bộ lọc, xếp theo độ phổ biến |
| `users` | `{cluster_k8: 1}`, `{region: 1, age_group: 1}` | trang phân khúc, chọn user mẫu |
| `analysis_lift_by_group` | `{group_type: 1, group_value: 1}` | so sánh vùng miền, tuổi |
| `analysis_top_dish_by_slot` | `{meal_slot: 1, rk: 1}` | top món theo bữa |
| `ingredient_edges`, `ingredient_rules` | `{variant: 1, lift: -1}` | đồ thị nguyên liệu |
| `metrics` | `{view: 1, variant: 1, model: 1}` | bảng so sánh mô hình |
| `trending` | `{window_end: -1}` | phần Streaming |

Danh mục chỉ có 5.499 món nên các index của `dishes` có tác dụng minh họa là chính. Report sẽ ghi kết quả `explain()` của 3 truy vấn tiêu biểu (`recs` theo `_id`, `dishes` theo bộ lọc chay + bữa, tìm tên món) để chứng minh dùng IXSCAN, không quét toàn bộ (COLLSCAN). Có thể đưa vào báo cáo.

### 6. Kiểm tra sau khi ghi (`data/output/export_report.json`)
- Số document từng collection khớp với số Spark đếm trên HDFS (`recs` 50.000; tổng số phần tử `items` 2.500.000; `dishes` 5.499; `similar` 5.499, mỗi món 50…).
- Toàn vẹn tham chiếu, tính bằng Spark trước khi ghi (anti-join phải ra 0): mọi `food_id` trong `recs`, `similar`, `companions`, `popular`, `history` đều có trong `dishes`.
- Lấy mẫu 5 user cố định (theo hash, gồm cả user lạnh): danh sách 50 món đọc từ MongoDB phải giống hệt `recs_final` trên HDFS, đúng thứ tự.
- `collStats` của từng collection: `count`, `size`, `storageSize`, `totalIndexSize`, để có số thật về dung lượng và tỷ lệ nén.
- Danh sách index và kết quả `explain()` ở mục 5. Thời gian ghi từng collection.

### 7. Docker compose
- Thêm service **`mongo-express`** (image `mongo-express:1.0.2`, cần tải image về). Cổng máy **8090** trỏ vào cổng 8081 trong container, vì cổng 8081 trên máy đang dùng cho UI của `spark-worker-1`.
  - Đăng nhập kiểu basic auth, dùng `admin` / `admin123` như MongoDB; tài khoản đặt trong `.env`.
  - Giới hạn RAM 256 MB, `depends_on: mongodb`.
- MongoDB giữ nguyên: giới hạn 1,5 GB, cache 1 GB (dữ liệu khoảng 280 MB, đủ chỗ).
- Tổng RAM cấp cho các container tăng thêm 0,25 GB.

### 8. Những gì API bước 08 sẽ đọc (để bước 07 xuất đủ ngay từ đầu)
| Trang dashboard | Collection |
|---|---|
| Tổng quan | `overview`, `reports` |
| Hành vi ăn uống | `analysis_heatmap_hour_dow`, `analysis_trend_month_category`, `analysis_season_month`, `analysis_top_dish_by_slot`, `analysis_lift_by_group`, `analysis_funnel_by_category`, `analysis_session_size`, `analysis_repeat_by_category`, `analysis_user_activity`, `analysis_long_tail_curve`, `analysis_rating_dist` |
| Món ăn | `dishes` (thống kê bằng aggregation `$group` của MongoDB), `analysis_catalog_vs_cooked`, `analysis_top_ingredients`, `ingredient_edges`, `ingredient_rules` |
| Phân khúc người dùng | `clusters`, `users` (đếm theo `cluster_k8`) |
| Gợi ý món ăn (user có sẵn) | `users` (hồ sơ, lịch sử, `test_cooks`), `recs`, `dishes`, `similar`, `dishes.companions`, `popular` (bù khi lọc) |
| Gợi ý món ăn (user mới) | `similar` của các món đã chọn, `popular`, `dishes` |
| Đánh giá mô hình | `metrics`, `reports` (`models_metrics`, `model_*_report`) |
| Thời gian thực (nâng cao) | `trending` |

Bộ lọc trên trang gợi ý: API lấy 50 món của user, lọc theo thuộc tính trong `dishes`. Nếu còn dưới 10 món thì bù bằng `popular` (theo vùng-tuổi) qua cùng bộ lọc, có ghi rõ nguồn là "phổ biến".

---

## Số liệu chính
| Bảng trên HDFS | Số dòng |
|---|---|
| `recs_final` | 2.500.000 (50.000 user × 50) |
| `item_sim` | 274.950 (5.499 × 50) |
| `companion` | 677 (656 món, tối đa 3 món ăn kèm/món) |
| `rules_meal` / `rules_ingredients` / `ingredient_edges` | 677 / 2.999 / 416 |
| `user_clusters` | 46.130 |
| `user_features_test` | 48.173 |
| `cluster_profile` | 22 (k = 3, 8, 11) |
| `metrics` | 117 |
| `pop_test` | 1.400 |
| `dish_stats` / `top_ingredients` / `lift_by_group` / `top_dish_by_slot` | 5.499 / 4.538 / 507 / 78 |

Kích thước BSON đo được: xem bảng ở mục 2 và mục 3 (`recs`).

## Lỗi / sự cố và cách xử lý
- Lần dò đầu: in JSON tiếng Việt ra console Windows bị `UnicodeEncodeError` (cp1252). Đã chạy lại với `PYTHONIOENCODING=utf-8`.
- Lúc đo `users`: `bson.encode` báo lỗi với `datetime.date` (cột `signup_date`). Đã chuyển sang datetime để đo, và ghi vào thiết kế (mục 4) là sẽ đổi ngày thành chuỗi.
- Không có lỗi nào khác. Không ghi gì lên HDFS hay MongoDB.

## Cần người dùng quyết định
1. **Cách lưu `recs`:** 1 document/user với mảng 50 món, bỏ chuỗi `reason` để API tự sinh lại (202,6 MB)? Hai phương án còn lại: giữ chuỗi `reason` (447,8 MB), hoặc 1 document/dòng (469,5 MB). **Đề xuất: 1 doc/user, bỏ `reason`.**
2. **Cách ghi:** `pymongo` với `foreachPartition` cho `recs` và `users`, `collect()` cho bảng nhỏ, ghi vào collection tạm rồi đổi tên. Không dùng Spark Connector. **Đề xuất: đồng ý.**
3. **Dinh dưỡng và thời gian nấu:** kế hoạch ban đầu có bộ lọc "calo / thời gian nấu", nhưng cả hai đều là số ngẫu nhiên.
   - **Đề xuất:** bỏ bộ lọc calo; thay "thời gian nấu" bằng `is_quick` ("món nhanh").
   - Bộ lọc còn lại: chay, món nhanh, không cay, bữa, nhóm món.
   - Vẫn lưu `nutrition` trong `dishes` nhưng dashboard **không hiển thị**; báo cáo nêu lý do.
   - Phương án khác: hiển thị kèm ghi chú "số liệu gốc không chính xác".
4. **Persona thật (`users_truth`) có xuất vào MongoDB không?**
   - **Đề xuất:** có, đặt trong `users.truth` và `clusters.persona_kiem_chung`, ghi rõ "chỉ để kiểm chứng".
   - Dùng ở trang Phân khúc, để minh họa cụm K-means khớp persona (ARI) và để chọn user mẫu khi demo ("xem gợi ý cho một user ăn chay").
   - Mô hình không đọc trường này.
5. **`test_cooks` (món user thật sự nấu tháng 9) trong `users`:** dùng để dashboard đánh dấu gợi ý "trúng". **Đề xuất: có.**
6. **`mongo-express`:** tải image `mongo-express:1.0.2`, cổng 8090, đăng nhập `admin` / `admin123`. **Đề xuất: đồng ý.** Hoặc đổi cổng hay tài khoản.
7. **Lịch sử trong `users.history`:** 10 món nấu nhiều nhất đến hết 08/2026. **Đề xuất: 10.** Có thể đổi số món, hoặc lấy theo lần nấu gần nhất.

Việc cần người làm (không đổi): kiểm tra tay 100 món (Hậu 50, Ngọc 50); Ngọc dựng notebook biểu đồ cho bước 05 và 06.

## Commit
- Commit của phiên này: `Buoc 07: de xuat thiet ke (chua code)` (LAST_RUN, PROGRESS).
