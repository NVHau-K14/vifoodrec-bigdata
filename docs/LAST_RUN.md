# Lần chạy gần nhất – 25/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ MongoDB `vifood` (đọc trực tiếp hôm nay) và `data/output/*.json`.

## Yêu cầu
**Lần này:** thêm quy tắc "tên thành viên và phân công chỉ có trong báo cáo Word và slide":
- ghi quy tắc vào CLAUDE.md, bỏ dòng "Nhóm: … (chia việc 50/50)";
- bỏ tên trong PROGRESS;
- commit skill `vifood-dashboard` đã sửa dòng 9;
- trong thiết kế 08: bỏ chia việc ở mục H, chỉ giữ thứ tự làm chia 2 đợt; bỏ câu hỏi 5 (Claude viết toàn bộ code);
- giữ nguyên `docs/plan/`;
- dashboard: trang Tổng quan và thanh bên không có tên nhóm hay thành viên.

**Lần trước (bản thiết kế bên dưới vẫn chờ góp ý, đã sửa theo yêu cầu lần này):**
1. Cài skill `frontend-design` từ repo `anthropics/skills` vào `.claude/skills/frontend-design/`, commit cùng `.claude/skills/vifood-dashboard/`. Ghi vào CLAUDE.md: mọi việc trong `web/` theo skill `vifood-dashboard`, skill này thắng khi khác `frontend-design`.
2. Đề xuất thiết kế bước 08 (chưa viết code), tuân theo skill `vifood-dashboard`, gồm:
   - endpoint (method, tham số, schema, collection, index);
   - thẻ và endpoint của từng trang trong 7 trang;
   - cấu trúc `web/`;
   - service `api` trong docker;
   - cách tải sẵn ECharts và font;
   - kiểm thử bằng pytest và đo độ trễ.

## Đã làm
**Lần này:**
- **Tìm tên người** trong toàn bộ repo, trừ `docs/plan/`. Tên chỉ còn ở 3 file: CLAUDE.md (dòng "Nhóm"), PROGRESS (3 chỗ), LAST_RUN (mục F, mục H, câu hỏi 5, dòng việc cần người làm).
  - Code (`src/`, `scripts/`), report JSON, DECISIONS, DATA_DICTIONARY và skill không có tên.
  - Các kết quả "hau" còn lại là "hàu" trong link ảnh món (`canh-hau-thanh-mat`, `Hau-nuong`) và chữ "hậu tố" trong DATA_DICTIONARY và `src/06a_split.py`, không phải tên người.
  - **MongoDB** (`vifood` và `vifood_local`, mọi collection, mọi document): chỉ 5 món trong `dishes` khớp mẫu tìm. Cả 5 là chữ có sẵn trong dữ liệu món, không phải tên thành viên, nên giữ nguyên:
    - 61 "Ngọc mực xóc tỏi";
    - 554 "Cá sapa nhồi ngọc kê nướng";
    - 2079 "Cơm Chiên Chay Hoàng Hậu";
    - 2607 "Cơm Chiên Ngọc Bích";
    - 4401 "Thịt Gà Hầm Thuốc Bắc" (nguyên liệu "ngọc trúc").
- **CLAUDE.md:**
  - bỏ dòng "Nhóm: …", chỉ giữ "Mục tiêu: điểm tối đa";
  - thêm quy tắc đầu tiên ở mục "Quy tắc làm việc": không ghi tên người hay ai làm phần nào trong code, dữ liệu, report, MongoDB, API, dashboard (kể cả trang Tổng quan và thanh bên) và tài liệu làm việc. `docs/plan/` giữ nguyên.
- **PROGRESS:**
  - bỏ phần chia số món theo người ở việc "Kiểm tra tay 100 món";
  - bỏ tên người ở đầu việc "Dựng notebook…";
  - mục `web/` trong "Việc tiếp theo": thay câu chia việc bằng "Claude viết toàn bộ code, chia 2 đợt".
- **Skill `vifood-dashboard`:** dòng 9 đã sửa sẵn (bỏ tên), đưa vào commit lần này.
- **Thiết kế 08:**
  - mục H chỉ còn thứ tự làm, chia 2 đợt;
  - mục F: "máy của …" thành "máy khác";
  - mục C ghi rõ thanh bên và trang Tổng quan không có tên nhóm hay thành viên;
  - bỏ câu hỏi 5, các câu sau đánh số lại.

**Lần trước:**
- **Kiểm tra cụm:** đủ 10 container đang chạy. RAM đang dùng khoảng 2,7 GB, trong đó MongoDB 643 MB.
- **Skill `frontend-design`:**
  - Lấy từ `anthropics/skills`, commit `dbd4588` (09/10/2026), gồm `SKILL.md` và `LICENSE.txt` (Apache 2.0).
  - Đã đọc toàn bộ nội dung trước khi cài. Skill chỉ có hướng dẫn thiết kế, không có script.
  - Đã commit cùng `vifood-dashboard`: commit `563e8ff`.
- **CLAUDE.md** có mục mới "Giao diện (`web/`) và endpoint cho dashboard":
  - mọi việc trong `web/` và việc thiết kế endpoint cho dashboard theo `vifood-dashboard`;
  - `frontend-design` chỉ để tham khảo; khác nhau thì `vifood-dashboard` thắng.
- **Đọc dữ liệu thật trong MongoDB** (tên trường, giá trị, index) để thiết kế endpoint. Kết quả nằm ở mục "Đề xuất thiết kế" bên dưới.
  - Phát hiện 3 chỗ skill hoặc dữ liệu chưa khớp nhau, xem mục "Cần người dùng quyết định".
- **Chưa viết code** cho `api/` và `web/`. Hai thư mục này vẫn trống (`web/css`, `web/js` chưa có file).

## Số liệu chính (đọc từ MongoDB `vifood` hôm nay)
- **`recs`:** 50.000 doc. Nguồn của 2.500.000 phần tử `items`:

  | `source` | Số phần tử | Có `because_food_id` |
  |---|---|---|
  | `als` | 2.312.304 | 291.325 (API bỏ qua, theo D14) |
  | `content_slot` | 96.346 | 96.346 |
  | `pop` | 91.350 | 0 |
  | `rep` | 0 | |

  Nguồn `rep` có trong DATA_DICTIONARY nhưng không xuất hiện trong `recs_final`. API vẫn xử lý trường hợp này cho chắc.
- **`users`:** ấm 47.130, lạnh 1.827, ít 1.043 (theo `group`). `history` trung bình 8,79 món mỗi user.
  - `profile.pref_slot` có các giá trị: sáng, trưa, tối, khuya, null.
  - `dishes.meal_types` lại dùng: sáng, trưa, tối, **ăn vặt** (không có "khuya").
- **`dishes`:** 10 nhóm món (`dish_category`), 4 loại (`dish_type_fixed`), 11 `main_protein`, `season` có 4 giá trị (không, lạnh, nóng, tết).
- **Bảng phân tích:** `lift_by_group.group_type` gồm `age_group`, `day_type`, `meal_slot`, `region`; `season_month.region` có thêm "Tất cả". `ingredient_edges.variant` gồm "bỏ gia vị" và "giữ gia vị".
- **Kiểm tra trước cho pytest:** tổng `cooks` của `analysis_trend_month_category` là 2.382.842 và tổng `views` là 18.637.934, khớp `overview.events_by_type`.
- **`explain()` của bước 07:** bù món 3 ms (IXSCAN `is_vegetarian_1_stats.cook_rank_1`), tìm món 3 ms (IXSCAN `name_search_1`), đọc `recs` theo `_id` 0 ms (IDHACK).
- **Thư viện:**
  - ECharts **5.5.1** có trên npm (bản 5.x mới nhất là 5.6.0; skill ghi 5.5.x).
  - Font: gói `@fontsource/be-vietnam-pro@5.2.8` có đủ 12 file woff2 cần dùng (4 độ đậm × 3 subset latin, latin-ext, vietnamese).
- Image `vifood-spark:4.2.0` nặng **7,13 GB**, có `pymongo` 4.19.0, `httpx` 0.28.1 và `pydantic` 2.14.1, nhưng **không có** `fastapi`, `uvicorn`, `pytest`. Cổng 8000 trên máy đang trống.

---

# Đề xuất thiết kế bước 08 (chưa code, chờ góp ý)

## A. Nguyên tắc
1. **Một service `api`** (FastAPI) phục vụ cả `/api/...` (JSON) và `web/` tĩnh trên **cùng origin** `http://localhost:8000`, nên không cần CORS (skill mục 1).
2. **API chỉ đọc MongoDB**, không đọc HDFS hay file `data/output/` (các report đã nằm trong collection `reports`). Database lấy từ biến `MONGO_DB`: phát triển dùng `vifood_local`, demo dùng `vifood`.
3. **API trả số thô, frontend định dạng** (`toLocaleString('vi-VN')` trong `js/api.js`). API không trả `score` của gợi ý, không trả `nutrition`, và **không bao giờ trả `truth` từ endpoint gợi ý hay hồ sơ user** (D14 câu 4).
4. **Câu lý do gợi ý do API sinh**, từ `source` và tên món `because_food_id` (chỉ khi `source = "content_slot"`), theo đúng bảng ở skill mục 5 (có 2 chỗ cần chốt, xem câu hỏi 1 và 2).
5. **Collection nhỏ được cache trong RAM** của API (TTL 10 phút): `overview`, `reports`, 13 bảng `analysis_*`, `metrics`, `clusters`, `popular`, và một bản "thẻ món" gọn của 5.499 món (khoảng 2–3 MB). Các truy vấn theo user (`recs`, `users`), bù món, tìm món và `similar` luôn đọc MongoDB để thể hiện index.
6. Endpoint là `def` thường (pymongo đồng bộ, FastAPI tự chạy trong threadpool). Một `MongoClient` dùng chung, `maxPoolSize=20`, `serverSelectionTimeoutMS=2000`.
7. **Lỗi:**
   - 404 khi không có user hoặc món: `{"detail": "Không tìm thấy người dùng 123"}`;
   - 422 khi tham số sai (FastAPI tự kiểm tra);
   - 503 khi MongoDB không phản hồi: `{"detail": "Không kết nối được MongoDB"}`. Frontend hiện dòng lỗi và nút "Thử lại" (skill mục 4).
8. Mỗi response có header `Server-Timing: app;dur=<ms>, db;dur=<ms>` (middleware đo), để đo độ trễ và xem trong DevTools.
9. Có trang `/docs` (OpenAPI do FastAPI sinh). Mọi endpoint khai báo `response_model` bằng Pydantic, nên `/docs` cũng là tài liệu schema và có thể chụp cho báo cáo.

## B. Danh sách endpoint
Tất cả là `GET`, trừ E20 (`POST`, vì cần gửi danh sách món đã chọn). Tiền tố `/api`.
Bộ lọc món dùng chung (gọi là **F**): `veg: bool`, `quick: bool`, `not_spicy: bool`, `meal: sáng|trưa|tối|ăn vặt`, `category: <một trong 10 nhóm món>`. Bộ lọc đổi thành truy vấn MongoDB như sau: `is_vegetarian: true`, `is_quick: true`, `is_spicy: false`, `meal_types: <bữa>`, `dish_category: <nhóm>`.

**Thẻ món (gọi là `DishCard`)**, dùng ở mọi endpoint trả món: `food_id, dish_name, image_link, dish_category, dish_type_fixed, is_vegetarian, is_quick, is_spicy, meal_types`. Projection tương ứng là `CARD_PROJ`.

### B1. Chung và Tổng quan
| # | Endpoint | Tham số | Trả về (tóm tắt schema) | Collection · index |
|---|---|---|---|---|
| E0 | `/api/health` | – | `{status, db, mongo_ms, counts: {dishes, users, recs}}` | `ping`, `estimatedDocumentCount` |
| E1 | `/api/overview` | – | Các trường của `overview` (`n_dishes, n_users, n_events, events_by_type, event_months, n_recs_rows, hdfs, reference_date, exported_at, notes`) + `pipeline: [{step, name, status, seconds}]` | `overview` (`_id`), `reports` (cache) |
| E22 | `/api/meta/filters` | – | `{categories[], meal_types[], regions[], age_groups[], dish_types[]}` | `distinct` trên `dishes`, `users` (cache) |

- **`pipeline` trong E1 suy ra từ dữ liệu, không chép cứng:**
  - bước 02–06 là "Xong" khi có report tương ứng trong `reports`, `seconds` lấy từ `total_seconds`;
  - bước 07 "Xong" khi có `overview.exported_at`;
  - bước 08 "Đang làm";
  - streaming "Chưa" khi `trending` rỗng.
- E22 giúp các chip lọc không phải chép cứng tên nhóm món trong HTML.

### B2. Hành vi ăn uống
| # | Endpoint | Tham số | Trả về | Collection · index |
|---|---|---|---|---|
| E2 | `/api/behavior/heatmap` | `metric = cooks\|views\|events` (mặc định `cooks`) | `{metric, cells: [{dow_idx, dow_vn, hour, value}] (168 ô), top: [5 ô lớn nhất]}` | `analysis_heatmap_hour_dow` (cache) |
| E3 | `/api/behavior/monthly` | `region = Tất cả\|Bắc\|Trung\|Nam` | `{months: [{month, cooks, views, split: train\|val\|test, tet_share_pct}], by_category: [{month, dish_category, cooks, cook_share_pct}], season: [{month, season, share_pct}]}` | `analysis_trend_month_category` (`month`), `analysis_season_month` (`region, month`) |
| E4 | `/api/behavior/top-dishes` | `slot = sáng\|trưa\|tối\|khuya`, `by = cooks\|lift`, `limit ≤ 10` | `[{rank, food_id, dish_name, dish_category, image_link, cooks, share_pct, lift}]` | `analysis_top_dish_by_slot` (`meal_slot, rk`); với `by = lift` thì sắp xếp theo `rk_lift`. Bảng chỉ có 19–20 dòng mỗi bữa (hợp của top 10 theo lượt nấu và top 10 theo lift), nên `limit` tối đa là 10 |
| E5 | `/api/behavior/lift` | `group_type = region\|age_group\|day_type\|meal_slot`, `attribute = dish_category\|main_protein\|main_method\|dish_type_fixed\|is_quick\|is_spicy`, `min_cooks` (mặc định 1.000) | `{groups[], values[], cells: [{group_value, value, lift, share_pct, cooks}]}` | `analysis_lift_by_group` (`group_type, group_value`) |
| E6 | `/api/behavior/funnel` | – | `{pairs: {view, favorite, cook, rate}, users: {...}, by_category: [{dish_category, favorite_per_view_pct, cook_per_view_pct, rate_per_cook_pct, avg_rating}]}` | `analysis_funnel_by_category` + `reports.analysis_report.funnel_users` |
| E7 | `/api/behavior/habits` | – | `{session_size[], repeat_by_category[], user_activity[], rating_dist[]}` | 4 collection `analysis_*` nhỏ (cache) |

- **`split` trong E3:** tháng 2026-08 là val, 2026-09 là test (lấy từ `reports.model_split_report`), các tháng còn lại là train.
- **Tháng có Tết:** được tô màu cam theo skill mục 6. Đó là tháng có `tet_share_pct` lớn nhất (2026-02, 19,17%). API trả số, frontend chọn màu.

### B3. Món ăn
| # | Endpoint | Tham số | Trả về | Collection · index |
|---|---|---|---|---|
| E8 | `/api/dishes/summary` | – | `{kpi: {n_dishes, veg_pct, quick_pct, spicy_pct, n_ingredients}, by_type[], catalog_vs_cooked: {dish_category[], main_method[], main_protein[]}, long_tail: {curve[], gini, top1_pct, top10_pct}}` | **Aggregation `$facet`** trên `dishes` (đếm theo `dish_type_fixed` và 3 cờ) + `analysis_catalog_vs_cooked` + `analysis_long_tail_curve` + `reports.analysis_report.long_tail` (cache) |
| E10 | `/api/ingredients/top` | `limit ≤ 50`, `seasoning = false\|true` | `[{ingredient, n_dishes, cooks, cook_rank}]` | `analysis_top_ingredients` (`cook_rank`) |
| E11 | `/api/ingredients/graph` | `variant = bỏ gia vị\|giữ gia vị`, `limit ≤ 150` (mặc định 80 cạnh) | `{nodes: [{name, degree}], edges: [{src, dst, lift, confidence}]}` | `ingredient_edges` (`variant, lift -1`) |
| E12 | `/api/dishes/search` | `q` (2–60 ký tự), `limit ≤ 30` | `[DishCard]`, xếp theo `stats.cook_rank` | `dishes` `$regex` trên `name_search` (index `name_search_1`) |
| E13 | `/api/dishes/{food_id}` | `n_similar ≤ 12` (mặc định 8) | `{dish: DishCard + ingredient_list, ingredients, preparation, cooking_method, serving_size, source, season, main_protein, main_method, stats, companions: [DishCard + confidence, lift], similar: [DishCard + sim]}` | `dishes` (`_id`), `similar` (`_id`), `dishes` (`$in`) |
| E14 | `/api/dishes` | F + `skip`, `limit ≤ 48` | `{total, items: [DishCard + stats.cooks]}` | `dishes` với các index `{cờ, stats.cook_rank}` |

- **E12 chuẩn hóa chuỗi gõ vào giống hệt Spark:** `unicodedata.normalize("NFC")` → `lower()` → `translate(VN_FROM → VN_TO)` (chép từ `src/07_export_mongo.py:237`) → thay `[^a-z0-9]+` bằng dấu cách → `strip`. Sau đó `re.escape` rồi mới đưa vào `$regex`.
  - Bước NFC là phần **thêm** so với Spark: bàn phím Telex trên macOS và một số trình duyệt gửi chữ ở dạng tổ hợp (NFD), như "ă" = "a" + dấu. Bỏ NFC thì `translate` không bắt được.
- **E13 không trả `nutrition`.** `stats` kèm nhãn "cả năm mô phỏng" ở frontend.

### B4. Phân khúc người dùng
| # | Endpoint | Tham số | Trả về | Collection · index |
|---|---|---|---|---|
| E15 | `/api/segments` | `k = 3\|8\|11` (mặc định 8) | `{k, quality: [{algo, k, silhouette, ari, nmi}], clusters: [{cluster, n_users, features{18}, label, strategy[], persona_kiem_chung, persona_share}]}` | `clusters` (`k, cluster`) + `reports.model_kmeans_report.search` (cache) |
| E16 | `/api/segments/8/{cluster}` | `sample ≤ 12` | `{cluster, by_region[], by_age[], by_group[], sample_users: [{user_id, region, age_group, group, profile}]}` | `users`: `$match {cluster_k8}` + `$facet` (index `cluster_k8_1`) |

- **`label` và `strategy` sinh theo luật** từ `features` của cụm, đặt trong `api/segments.py`, không viết tay cho từng cụm.
  - `label` lấy 2 đặc trưng có độ lệch lớn nhất so với trung bình các cụm, ví dụ "Nhiều món hải sản · nấu bữa tối".
  - `strategy` là 1–2 câu, chọn từ bảng luật. Ví dụ `share_chay` cao thì "Ưu tiên bộ sưu tập món chay"; `share_nhanh` cao thì "Gợi ý món nhanh vào giờ trưa ngày thường".
  - Bảng luật được ghi vào DECISIONS để báo cáo trích được.
- **E16 chỉ hỗ trợ k = 8**, vì chỉ `cluster_k8` có index. Với k = 3 và k = 11, trang chỉ hiện E15.
- **`persona_kiem_chung` chỉ có ở E15**, kèm cờ `verify_only: true`. Frontend ghi "chỉ để kiểm chứng" (skill mục 5). E16 **không** trả `truth` của từng user.

### B5. Gợi ý món
| # | Endpoint | Tham số | Trả về | Collection · index |
|---|---|---|---|---|
| E17 | `/api/users/demo` | – | `[{user_id, group, region, age_group, n_cook}]`, 3 user cho mỗi nhóm ấm, ít, lạnh | `users` (cache lúc khởi động) |
| E18 | `/api/users/{user_id}` | – | `{user_id, region, age_group, gender, group, cluster_k8, profile, history: [DishCard + n_cook, last_cook], n_test_cooks}`. **Không có `truth`** | `users` (`_id`, projection `{truth: 0}`), `dishes` (`$in`) |
| E19 | `/api/recs/{user_id}` | F + `limit` (1–20, mặc định 10) | `{user_id, filters, items: [RecItem], summary: {from_recs, from_fill, hits}}` | `recs` (`_id`, IDHACK) → `dishes` (`$in` + F) → (nếu thiếu) `dishes` (F + `$nin`, sắp xếp `stats.cook_rank`) |
| E20 | `POST /api/recs/new-user` | body `{food_ids: [1–10], region?, age_group?, limit?, ...F}` | giống E19, không có `hits` | `similar` (`$in`), `dishes` (`$in` + F), `popular` (cache) |

- **E17 chọn user mẫu một cách cố định:**
  - mỗi nhóm lấy 3 user có `user_id` nhỏ nhất trong số user có `history.2` (để hồ sơ có món);
  - với nhóm lạnh thì bỏ điều kiện có `history`;
  - kèm 5 user mẫu theo hash của bước 07 (30494, 33988, 14251, 38037, 21864) nếu có trong database.
  - `group` không có index nên mỗi nhóm phải quét 50.000 doc. Việc này chỉ chạy 1 lần lúc khởi động rồi cache.
- **`RecItem`** gồm `DishCard` và các trường:

  | Trường | Ý nghĩa |
  |---|---|
  | `rank` | thứ tự hiển thị 1..limit |
  | `rec_rank` | hạng gốc trong 50 món, null với món bù |
  | `source` | `als`, `content_slot`, `pop`, `fill` hoặc `rep` |
  | `dot` | `herb`, `chili` hoặc `neutral`, theo skill mục 5 |
  | `reason` | câu lý do |
  | `because` | `{food_id, dish_name}`, chỉ có với `content_slot` |
  | `hit` | món có trong `test_cooks`, dùng để hiện nhãn "Đã nấu T9" |

- **Thuật toán E19:**
  1. Đọc `recs.find_one({_id})`; không có thì trả 404. Đọc `users.find_one({_id}, {region, age_group, test_cooks, "history.food_id"})`.
  2. Lấy 50 `food_id` theo `rank`, rồi `dishes.find({_id: {$in: ids}, ...F}, CARD_PROJ)`. Giữ đúng thứ tự `rank` và lấy `limit` món đầu.
  3. Thiếu món thì bù bằng `dishes.find({...F, _id: {$nin: ids ∪ history}}).sort({"stats.cook_rank": 1}).limit(thiếu)`, gắn `source = "fill"`, chấm màu `neutral`. Đây là truy vấn D14 d, và `explain()` của nó đã có trong report bước 07.
  4. Sinh `reason` cho từng món theo `source`:
     - `als`: "Người có khẩu vị giống bạn cũng hay nấu món này";
     - `content_slot`: "Giống món {tên} bạn đã nấu" hoặc "…bạn đã xem" (câu hỏi 1);
     - `pop`: câu hỏi 2;
     - `fill`: câu hỏi 2;
     - `rep`: "Bạn đã nấu món này".
  5. `summary.from_recs` và `summary.from_fill` dùng cho dòng tóm tắt bên phải bộ lọc: "N món từ gợi ý cá nhân · M món bù từ danh mục phổ biến" (skill mục 4).
- **Thuật toán E20 (user mới):**
  1. Đọc `similar.find({_id: {$in: food_ids}})`, cộng `sim` theo từng món ứng viên, rồi bỏ các món đã chọn.
  2. Mỗi ứng viên nhớ món đã chọn có `sim` lớn nhất với nó, để làm lý do "Giống món {tên} bạn đã chọn" (`source = content`, chấm `chili`).
  3. Lọc bằng `dishes.find({_id: {$in: ứng viên}, ...F})` và xếp theo tổng `sim`.
  4. Thiếu thì bù từ `popular` (`vùng-tuổi|{vùng}|{tuổi}` nếu người dùng chọn vùng và tuổi, không thì `chung`), lọc lại bằng F. `popular` chỉ có 100 món, nếu vẫn thiếu thì bù tiếp bằng truy vấn `fill` của E19.
  5. Có `food_id` không tồn tại thì trả 404 và nêu id đó.

### B6. Đánh giá mô hình
| # | Endpoint | Tham số | Trả về | Collection · index |
|---|---|---|---|---|
| E23 | `/api/eval/ranking` | `view = test\|val`, `variant = chính\|khám phá\|ngoài độ chính xác`, `group = tất cả\|ấm\|ít\|lạnh` | `{rows: [{model, label, kind: chính\|baseline, metrics{...}}], ci95: [{so_sanh, metric, users, hieu, ci95: [lo, hi]}]}` | `metrics` (`view, variant, model`) + `reports.models_metrics` |
| E24 | `/api/eval/details` | – | `{rmse: {...}, als_grid: [...], hybrid_weights, lsh: [...], fpgrowth_hit: {...}, control_06g: {...}, kmeans_k: [...], timings: [{step, seconds}]}` | `reports` (cache): `model_als_report`, `model_content_report`, `model_fpgrowth_report`, `model_control_report`, `model_hybrid_report`, `model_kmeans_report`, `total_seconds` của mọi report |
| E26 | `/api/reports/{name}` | `name` thuộc danh sách 12 report | `content` nguyên bản | `reports` (`_id`). Dùng để gỡ lỗi; trang không gọi |

- **Tên mô hình để hiển thị:** API có bảng `label`, ví dụ `hybrid_c2` → "Hybrid + content 2 vị trí", `nau_lai` → "Nấu lại", `pop_vung_tuoi` → "Phổ biến theo vùng-tuổi".
- `kind` dùng để tô màu (skill mục 6): hybrid, hybrid + content và ALS là `chính` (màu herb), còn lại là `baseline` (màu neutral).

### B7. Thời gian thực
| # | Endpoint | Tham số | Trả về | Collection · index |
|---|---|---|---|---|
| E25 | `/api/trending` | `limit ≤ 20` | `{status: "chưa chạy"\|"đang chạy", updated_at, windows: [{window_end, items: [DishCard + cooks]}]}` | `trending` (`window_end -1`) |

- Hiện `trending` còn rỗng, nên E25 trả `status = "chưa chạy"` và mảng rỗng. Schema của document `trending` sẽ chốt khi thiết kế Structured Streaming. E25 có thể phải sửa lại lúc đó.

**Tổng cộng 25 endpoint.**
- Đánh số E0–E26, bỏ E9 và E21 vì đã gộp vào E8 và E13.
- 7 endpoint đọc MongoDB trực tiếp mỗi lần gọi: E12, E13, E14, E16, E18, E19, E20. Các endpoint còn lại đọc từ cache.

## C. Từng trang: thẻ và endpoint
Mọi trang có chung: thanh bên 7 mục (**không có tên nhóm hay thành viên**, ở thanh bên cũng như trang Tổng quan), hộp "Dữ liệu hành vi mô phỏng" ở cuối, đầu trang gồm nhãn nhỏ, H1 dạng câu hỏi và hai viên "Mốc dữ liệu: 01/09/2026" (lấy `reference_date` từ E1) và "Hành vi mô phỏng". Thứ tự thẻ trong bảng là thứ tự trên trang.

### 1. Tổng quan – `index.html`, H1 "Dữ liệu đi từ HDFS đến bữa ăn gợi ý như thế nào?"
| Thẻ | Nội dung | Endpoint |
|---|---|---|
| Hàng KPI | Món ăn · Người dùng · Sự kiện ("23,2 tr", dòng phụ "12 tháng mô phỏng") · Dung lượng HDFS (tổng, dòng phụ "x GB tính cả 2 bản sao") · Dòng gợi ý đã tính | E1 |
| Kiến trúc hệ thống | SVG tĩnh trong HTML: CSV → HDFS → Spark (02–06) → MongoDB → FastAPI → Dashboard. Chỉ có chữ, không có số. `aria-hidden` cho phần hình, kèm một đoạn mô tả bằng chữ | – |
| Sự kiện theo loại | Thanh ngang: view, favorite, cook, rate | E1 |
| Dung lượng HDFS theo thư mục | Thanh ngang 6 thư mục, chú thích "chưa tính bản sao" | E1 |
| Tình trạng pipeline | Danh sách 01–08 và streaming, mỗi dòng có viên trạng thái (Xong / Đang làm / Chưa) và số giây | E1 |
| Ghi chú dữ liệu | 5 câu trong `overview.notes` | E1 |

### 2. Hành vi ăn uống – `hanh-vi.html`, H1 "Người dùng nấu gì, vào lúc nào?"
| Thẻ | Nội dung | Endpoint |
|---|---|---|
| Giờ nấu trong tuần | Heatmap giờ × thứ (T2…CN, nhãn giờ mỗi 3 giờ), nút phân đoạn Lượt nấu / Lượt xem | E2 |
| Lượt nấu theo tháng | Cột từ 0; train `#9CC7B0`, tháng Tết `--chili`, val/test `--slate`, có chú giải | E3 |
| Nhóm món theo tháng | Đường thể hiện `cook_share_pct` của 10 nhóm món. Mặc định chỉ hiện 4 nhóm lớn nhất, các nhóm còn lại bật trong legend | E3 |
| Món theo mùa | Chọn vùng (Tất cả / Bắc / Trung / Nam); cột chồng 100% theo `season` qua 12 tháng | E3 |
| Món nấu nhiều theo bữa | Nút phân đoạn sáng/trưa/tối/khuya và Nhiều nhất / Đặc trưng (lift); danh sách 10 món có ảnh nhỏ | E4 |
| Nhóm người dùng khác nhau ở đâu | Chọn `group_type` và `attribute`; heatmap lift (hàng = nhóm, cột = giá trị), ô hiện lift. Chú thích "lift > 1: nấu nhiều hơn mức chung" | E5 |
| Phễu chuyển đổi | Thanh ngang theo cặp user–món: xem → lưu → nấu → chấm. Dưới đó là bảng tỷ lệ theo nhóm món (bọc `overflow-x:auto`) | E6 |
| Thói quen nấu | 4 biểu đồ nhỏ: số món mỗi phiên, tỷ lệ nấu lại theo nhóm món, số lượt nấu mỗi user, phân bố rating | E7 |

### 3. Món ăn – `mon-an.html`, H1 "Danh mục có nhiều món, người dùng nấu món nào?"
| Thẻ | Nội dung | Endpoint |
|---|---|---|
| Hàng KPI | Số món · % chay · % món nhanh · % cay · Số nguyên liệu khác nhau | E8 |
| Danh mục và lượt nấu | Chọn thuộc tính (nhóm món / cách chế biến / đạm chính); cặp thanh ngang "% danh mục" và "% lượt nấu" | E8 |
| Đuôi dài | Đường tích lũy % lượt nấu theo % món, kèm Gini và "1% món đầu chiếm x%" | E8 |
| Nguyên liệu phổ biến | Thanh ngang top 20, có công tắc "Tính cả gia vị" | E10 |
| Nguyên liệu hay đi cùng nhau | Đồ thị mạng force (FP-Growth), mặc định "bỏ gia vị" | E11 |
| Tra cứu món | Ô tìm có `<label>`, gõ xong 250 ms mới gọi API (debounce). Bên dưới là lưới thẻ món theo bộ lọc F, có nút "Xem thêm" | E12, E14, E22 |
| Chi tiết món | Hiện khi bấm một thẻ: ảnh, chip, nguyên liệu, cách làm, `stats` ("cả năm mô phỏng"), món tương tự (8), món ăn kèm (≤ 3) | E13 |

Plan ban đầu đặt tên trang là "Món ăn & dinh dưỡng". Trang **không** hiện dinh dưỡng vì `nutrition` là số ngẫu nhiên (D14 câu 3). Tên trong thanh bên là "Món ăn", đúng như skill.

### 4. Phân khúc người dùng – `phan-khuc.html`, H1 "Có những kiểu người nấu ăn nào?"
| Thẻ | Nội dung | Endpoint |
|---|---|---|
| Chọn số cụm | Nút phân đoạn k = 3 / 8 / 11 (mặc định 8), kèm dòng giải thích vì sao dashboard dùng 8 | E15 |
| Chất lượng phân cụm | Đường Silhouette, ARI, NMI theo k cho KMeans; đánh dấu k = 3, 8, 11 | E15 |
| Quy mô cụm | Thanh ngang `n_users` của từng cụm, nhãn là `label` | E15 |
| Hồ sơ cụm | Heatmap cụm × 18 đặc trưng, ô tô theo độ lệch so với trung bình các cụm (mỗi cột chuẩn hóa riêng), tooltip hiện giá trị thật | E15 |
| Thẻ từng cụm | `label`, số user, 3 đặc trưng nổi bật, đề xuất chiến lược, dòng muted "Persona kiểm chứng (chỉ để kiểm chứng): …" | E15 |
| Người dùng trong cụm (k = 8) | Phân bố vùng, tuổi, nhóm ấm/ít/lạnh; vài user mẫu, mỗi user có liên kết `goi-y.html?user=<id>` | E16 |

### 5. Gợi ý món – `goi-y.html`, H1 "Hôm nay nấu gì?"
| Thẻ | Nội dung | Endpoint |
|---|---|---|
| Chọn cách gợi ý | Hai nút phân đoạn: "Người dùng có sẵn" / "Người dùng mới" | – |
| (Có sẵn) Chọn người dùng | Ô nhập mã user (`<label>`), các nút user mẫu theo nhóm ấm/ít/lạnh; đọc `?user=` trên URL | E17 |
| (Có sẵn) Hồ sơ | Vùng, tuổi, nhóm, cụm k8, bữa ưa thích, thanh ngang tỷ trọng chay/hải sản/ngọt/nhanh/cay, các món hay nấu (ảnh nhỏ) | E18 |
| (Mới) Chọn món mình thích | Ô tìm món (E12). Món đã chọn hiện thành chip có nút xóa (`aria-label`), tối đa 10 món. Có thể chọn thêm vùng và tuổi | E12, E22 |
| Bộ lọc | Chip Chay / Món nhanh / Không cay; nút phân đoạn bữa Tất cả · Sáng · Trưa · Tối · Ăn vặt; chọn nhóm món; bên phải là dòng tóm tắt | E22 |
| Danh sách gợi ý | Lưới 10 thẻ món (skill mục 4): số hạng, nhãn "Đã nấu T9" khi `hit`, chip, chấm và câu lý do. Dưới lưới là chú giải 3 màu và dòng "x/10 món có trong lượt nấu tháng 9/2026 của người này" | E19 / E20 |
| Chi tiết món đã chọn | Món tương tự, món ăn kèm, nguyên liệu | E13 |

- **Bữa mặc định là "Tất cả".** Không tự đặt theo `pref_slot`, vì `pref_slot` có "khuya" còn `meal_types` của món có "ăn vặt", hai thứ không khớp nhau. Hồ sơ vẫn hiện bữa ưa thích để người xem tự chọn.
- Mỗi lần đổi bộ lọc gọi lại E19. Request cũ chưa xong thì hủy bằng `AbortController`, để danh sách không bị request cũ ghi đè.

### 6. Đánh giá mô hình – `danh-gia.html`, H1 "Mô hình nào gợi ý trúng hơn?"
| Thẻ | Nội dung | Endpoint |
|---|---|---|
| So sánh mô hình | Thanh ngang 9 mô hình; chọn độ đo (NDCG / P / R / AP @5 / @10), nhóm user (tất cả / ấm / ít / lạnh) và view (test / val). Mô hình chính màu herb, baseline màu neutral | E23 |
| Khác biệt có ý nghĩa không | 3 hiệu NDCG@10 có khoảng tin cậy 95% (chấm và vạch), kèm đường 0 | E23 |
| Ngoài độ chính xác | Bảng coverage, novelty, diversity, recall món mới, NDCG@10 biến thể khám phá | E23 (`variant` = "ngoài độ chính xác" và "khám phá") |
| Dự đoán rating (RMSE) | Thanh ngang: trung bình chung, bias, ALS explicit | E24 |
| Dò tham số ALS implicit | Heatmap alpha × rank, ô hiện NDCG@10 trên val, đánh dấu ô được chọn | E24 |
| Content: MinHashLSH | Đường recall@20 theo số bảng băm, kèm số giây | E24 |
| Món ăn kèm (FP-Growth) | Thanh ngang hit rate@3: luật, mốc theo nhóm món, mốc 3 canh | E24 |
| Thí nghiệm đối chứng (06g) | Hai cặp thanh: ratings gốc (ALS kém hơn trung bình chung 6,0%) và mô phỏng (tốt hơn 36,1%), có một câu kết luận | E24 |
| Hiệu năng Spark | Thanh ngang thời gian từng bước trên cụm. Dòng "1 vs 2 worker, 10/50/100%" hiện viên "Chưa" cho đến khi đo xong | E24 |

### 7. Thời gian thực – `thoi-gian-thuc.html`, H1 "Món nào đang được nấu nhiều lúc này?"
| Thẻ | Nội dung | Endpoint |
|---|---|---|
| Trạng thái luồng | Viên trạng thái, cửa sổ gần nhất, thời điểm cập nhật | E25 |
| Món thịnh hành | Danh sách top món của cửa sổ gần nhất (thẻ món nhỏ) | E25 |
| Lượt nấu theo cửa sổ | Đường số lượt nấu qua các cửa sổ | E25 |

- Khi `trending` rỗng, trang hiện trạng thái rỗng có hướng dẫn: "Structured Streaming chưa chạy. Trang tự cập nhật khi có dữ liệu." Không để thẻ trống.
- Khi có dữ liệu thì trang gọi lại E25 mỗi 10 giây, và dừng khi tab bị ẩn (`visibilitychange`).

## D. Cấu trúc `web/` (theo skill mục 1)
```
web/
  index.html  hanh-vi.html  mon-an.html  phan-khuc.html  goi-y.html  danh-gia.html  thoi-gian-thuc.html
  css/theme.css          # @font-face + token :root + thanh phan dung chung (skill muc 2-4)
  css/goi-y.css          # chi bo cuc rieng (luoi the mon, 2 che do); trang khac them khi can
  js/api.js              # getJSON(path, {signal}), loi -> ApiError; fmtInt, fmtPct, fmtShort ("23,2 tr")
  js/layout.js           # dung thanh ben + dau trang, aria-current, vien "Moc du lieu" tu E1
  js/charts.js           # registerTheme('vifood'), initChart(el), heatmap(), bars(), hbars(), resize chung
  js/components.js       # (THEM, xem cau hoi 4) dishCard(), filterBar(), statusPill(), loading/error/empty
  js/<trang>.js          # 1 file moi trang, type="module"
  vendor/echarts.min.js  vendor/LICENSE-echarts.txt
  fonts/be-vietnam-pro-{latin,latin-ext,vietnamese}-{400,500,600,700}-normal.woff2  fonts/OFL.txt
  img/placeholder-dish.svg  img/logo.svg
```
- Mỗi trang HTML chỉ có khung (`<aside id="nav">`, `<header>`, các `<section>` chứa thẻ rỗng có `data-state="loading"`). `layout.js` dựng thanh bên, nên 7 trang không phải lặp lại HTML của thanh bên.
- JS dùng ES module (`<script type="module">`), không cần bước build. `echarts.min.js` nạp bằng `<script>` thường trước các module.
- `@font-face` khai báo 3 subset với `unicode-range` (lấy từ CSS của fontsource) và `font-display: swap`. Trình duyệt chỉ tải subset nào thật sự cần.
- **Kiểm tra theo skill mục 9:** mở mỗi trang ở 1440px và 390px, tắt API để xem thông báo lỗi, chạy `grep` mã màu hex. Phép `grep` hex được đưa luôn vào pytest (mục G).

## E. Service `api` trong docker
**`docker/Dockerfile.api`:**
```dockerfile
FROM python:3.12-slim
WORKDIR /home/jovyan/work
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
```

**`api/requirements.txt`:**
- `fastapi`, `uvicorn[standard]`, `pymongo==4.19.0` (cùng bản với image Spark), `pytest`, `httpx==0.28.1`;
- các bản `fastapi`, `uvicorn` và `pytest` sẽ được ghim đúng số phiên bản khi cài, sau khi xem `pip index versions`.

**Thêm vào `docker/docker-compose.yml`:**
```yaml
  api:
    build: { context: .., dockerfile: docker/Dockerfile.api }
    image: vifood-api:0.1
    container_name: api
    hostname: api
    env_file: ../.env
    environment:
      MONGO_DB: ${API_DB:-vifood}        # phat trien: API_DB=vifood_local
    command: ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
    working_dir: /home/jovyan/work
    volumes:
      - ..:/home/jovyan/work            # web/ tinh doc thang tu dia, sua HTML/JS khong can restart
    ports:
      - "8000:8000"                     # dashboard http://localhost:8000, tai lieu API http://localhost:8000/docs
    depends_on: [mongodb]
    networks: [bigdata]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits: { memory: 512m }
```

- **Image riêng `python:3.12-slim`** (khoảng 200 MB sau khi cài), không dùng lại `vifood-spark` (7,13 GB, thiếu FastAPI). Lần build đầu cần mạng, sau đó demo không cần mạng.
- **Cổng 8000** đang trống (8080, 8081, 8082 là Spark; 8090 là mongo-express; 8888 là Jupyter).
- **RAM 512 MB**, đúng con số plan dành cho api + web. Uvicorn 1 worker cộng cache dự kiến dưới 150 MB, sẽ đo bằng `docker stats` và ghi vào report.
- Tổng giới hạn RAM của cụm tăng từ 19,25 GB lên 19,75 GB. Thực tế đang dùng khoảng 2,7 GB khi không chạy job Spark.
- **Phục vụ `web/` cùng origin:**
  - `main.py` gắn router `/api` trước, sau đó mới `app.mount("/", StaticFiles(directory="web", html=True))`;
  - đường dẫn `/api/...` không tồn tại trả 404 dạng JSON, không trả `index.html`;
  - `GZipMiddleware(minimum_size=1024)`: `echarts.min.js` khoảng 1 MB, nén còn khoảng 330 KB;
  - header cache: `vendor/` và `fonts/` có `Cache-Control: max-age=604800`; HTML, CSS, JS có `no-cache`, để sửa xong chỉ cần tải lại trang.
- **Khi phát triển:**
  - sửa `web/` thì chỉ cần tải lại trang;
  - sửa `api/*.py` thì chạy `docker restart api` (khoảng 2 giây). Không dùng `--reload`, vì sự kiện đổi file từ ổ Windows qua WSL2 không đến được container một cách ổn định;
  - đổi database: `$env:API_DB="vifood_local"; docker compose up -d api` (PowerShell).
- **Cập nhật CLAUDE.md** khi cài: 11 container, cổng 8000, dòng 08 của bảng pipeline, lệnh chạy pytest.

**Cấu trúc `api/`:**
```
api/
  main.py          # tao app, middleware (Server-Timing, gzip, cache header), gan router, mount web/
  db.py            # MongoClient dung chung, get_db(), doc MONGO_URI / MONGO_DB
  cache.py         # cache TTL 10 phut cho collection nho, the mon gon cua 5.499 mon
  text.py          # normalize_query(), VN_FROM / VN_TO chep tu 07
  reasons.py       # cau ly do theo source, mau mau cham
  labels.py        # ten hien thi cua mo hinh, nhan va chien luoc cum
  schemas.py       # Pydantic: DishCard, RecItem, ...
  routers/{overview,behavior,dishes,segments,recs,eval,realtime}.py
  bench_latency.py # do do tre (muc G)
  tests/conftest.py tests/test_*.py
  requirements.txt
```
Chú thích trong code viết không dấu, theo quy ước của dự án.

## F. Tải sẵn ECharts và font
Tải một lần bằng script `scripts/08_fetch_vendor.sh`, chạy trong container `api` hoặc Git Bash trên máy. Sau đó **commit cả file vào git**, để máy khác hay máy demo không cần mạng.

```bash
# echarts 5.5.1 (skill ghi 5.5.x), kem giay phep Apache 2.0
curl -fL -o web/vendor/echarts.min.js     https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js
curl -fL -o web/vendor/LICENSE-echarts.txt https://cdn.jsdelivr.net/npm/echarts@5.5.1/LICENSE
# Be Vietnam Pro 400/500/600/700 x 3 subset tu @fontsource/be-vietnam-pro@5.2.8 (12 file woff2), kem OFL
for w in 400 500 600 700; do for s in latin latin-ext vietnamese; do
  curl -fL -o web/fonts/be-vietnam-pro-$s-$w-normal.woff2 \
    https://cdn.jsdelivr.net/npm/@fontsource/be-vietnam-pro@5.2.8/files/be-vietnam-pro-$s-$w-normal.woff2
done; done
curl -fL -o web/fonts/OFL.txt https://cdn.jsdelivr.net/npm/@fontsource/be-vietnam-pro@5.2.8/LICENSE
```
- **Cần cả 3 subset, không chỉ "vietnamese":** subset vietnamese của Google Fonts chỉ chứa các chữ có dấu riêng của tiếng Việt, còn chữ a–z và số nằm trong subset latin. Skill ghi "subset vietnamese" là thiếu (câu hỏi 3).
- `unicode-range` của từng subset chép từ file CSS của fontsource (`400.css` và các file cùng loại) vào `theme.css`.
- Script in kích thước và `sha256sum` của từng file, và ghi lại vào `data/output/api_report.json`. Dự kiến ECharts khoảng 1 MB, 12 file font tổng khoảng 250 KB.
- Kiểm tra không phụ thuộc mạng: pytest quét `web/*.html` và `web/css/*.css`, báo lỗi nếu có `http://` hoặc `https://` ngoài `image_link` (ảnh món vẫn lấy từ `image.cooky.vn`, theo skill mục 4). Mất mạng thì ảnh rơi về `placeholder-dish.svg`.

## G. Kiểm thử và đo độ trễ
**pytest** (`docker exec api pytest -q api/tests`):
- Dùng `fastapi.testclient.TestClient(app)`, chạy ngay trong tiến trình, gọi MongoDB thật.
- Mặc định chạy trên `vifood_local` (nhanh, không đụng bản demo). Thêm `--db vifood` để chạy trên bản đủ.
- Các phép kiểm tra là **bất biến**, đúng với cả hai database. Chỉ vài phép so số cụ thể (5 user mẫu, NDCG của hybrid) chạy khi database là `vifood`.

| File | Kiểm tra |
|---|---|
| `test_text.py` | `normalize_query(dish_name) == name_search` với **cả 5.499 món**. Chữ NFD, "Đ" hoa, khoảng trắng thừa và ký tự regex (`(`, `.*`) đều được xử lý. "đậu hũ" và "dau hu" ra cùng kết quả |
| `test_recs.py` | Lấy 50 user theo hash, trộn cả 3 nhóm, kết hợp 6 bộ lọc. Mỗi response phải: không có khóa `truth` ở bất kỳ tầng nào (quét đệ quy); đủ `limit` món; không trùng món; món nào cũng thỏa bộ lọc (đối chiếu lại `dishes`); món `fill` không nằm trong 50 món gợi ý hay trong `history`; câu lý do đúng mẫu theo `source`; `content_slot` có `because`; `hit` đúng bằng việc món có trong `test_cooks` |
| | Không lọc thì 10 món đầu phải trùng `recs.items[:10]`. Bộ lọc rất hẹp (đồ uống + sáng + chay) thì món bù được lấp đầy và `summary` đúng. User không tồn tại trả 404; `limit = 0` hoặc `limit = 21` trả 422 |
| `test_new_user.py` | Món đã chọn không xuất hiện trong kết quả. 0 món hoặc 11 món trả 422; id không tồn tại trả 404. Có chọn vùng và tuổi thì món bù lấy từ `popular` của vùng-tuổi đó |
| `test_privacy.py` | Gọi mọi endpoint (E0–E26) với tham số mặc định. Chỉ E15 được có chữ `persona` và phải kèm `verify_only: true`; không response nào có `truth` hay `nutrition` |
| `test_consistency.py` | Tổng lượt nấu qua 12 tháng của E3 bằng `overview.events_by_type.cook`. E2 có đúng 168 ô, đủ 7 × 24. NDCG@10 của hybrid trong E23 bằng giá trị trong `models_metrics`. Các `food_id` trong E4, E13, E19 đều có trong `dishes` |
| `test_indexes.py` | `explain()` của 5 truy vấn chính (đọc recs, lọc `$in`, bù món, tìm món, user theo cụm) dùng IXSCAN hoặc IDHACK, không có COLLSCAN, không có SORT trong bộ nhớ ở truy vấn bù món |
| `test_static.py` | `/` trả `index.html`; 7 trang trả 200; `vendor/echarts.min.js` và 12 file font trả 200; `/api/khong-co` trả 404 JSON |
| `test_web_rules.py` | Các luật của skill mục 9 và mục 1: không có mã hex ngoài `theme.css` và `charts.js`; không có CDN; mỗi trang có đủ 7 liên kết trong thanh bên đúng thứ tự (kiểm tra sau khi `layout.js` dựng, hoặc kiểm tra mảng trong `layout.js`); mỗi `<img>` có `alt`; không có `lorem` |

**Đo độ trễ** (`api/bench_latency.py`):
- Chạy trong container `api`, gọi `http://localhost:8000` qua HTTP thật bằng `httpx`.
- Mỗi endpoint: gọi khởi động 20 lần, sau đó **200 lần tuần tự**. Riêng E19 thêm một vòng **10 luồng song song × 100 lần** (mô phỏng 10 người xem cùng lúc).
- Ghi p50, p95, p99, max (ms), số request mỗi giây, và phần thời gian `db` lấy từ header `Server-Timing`. Kết quả ghi vào `data/output/api_report.json`.
- Tham số E19: 200 user theo hash, xoay vòng 6 tổ hợp bộ lọc, trong đó có 1 tổ hợp chắc chắn phải bù món. E12: 50 chuỗi tìm lấy từ tên món thật (2–3 từ đầu).
- Mục tiêu dự kiến (sẽ thay bằng số đo thật):
  - endpoint dùng cache p95 < 10 ms;
  - E12, E13, E18, E19 p95 < 50 ms;
  - E20 p95 < 80 ms (đọc 1–10 doc `similar`);
  - trang tải lần đầu (đo trong trình duyệt bằng `performance.getEntriesByType('navigation')`) dưới 1,5 giây.
- Đo cả trên `vifood` (50.000 user) và `vifood_local` (5.000 user), để thấy độ trễ gần như không đổi khi dữ liệu lớn gấp 10 lần, nhờ index.
- Ghi `docker stats api` (RAM) sau khi đo.

## H. Thứ tự làm (Claude viết toàn bộ code, chia 2 đợt)
Trước đợt 1: ghi D15 vào DECISIONS và sửa skill theo các câu trả lời (nếu có).

**Đợt 1: khung + Tổng quan + Gợi ý món + Đánh giá mô hình**
1. **Khung:**
   - `docker/Dockerfile.api`, service `api` trong compose, `main.py`, `db.py`, `cache.py`, E0, mount `web/`;
   - `scripts/08_fetch_vendor.sh` tải ECharts và font.
   - Kiểm tra: `http://localhost:8000` hiện trang trống có font đúng, `/docs` mở được.
2. **Phần dùng chung của web:** `theme.css`, `layout.js`, `api.js`, `charts.js`, `components.js`, `img/`.
3. **Tổng quan:** E1, E22 và trang `index.html`. Đối chiếu giao diện với bản mẫu canvas.
4. **Gợi ý món:** E12, E13, E17, E18, E19, E20, `text.py`, `reasons.py` và trang `goi-y.html`.
5. **Đánh giá mô hình:** E23, E24, E26 và trang `danh-gia.html`.
6. **Test của đợt 1:** `test_text`, `test_recs`, `test_new_user`, `test_privacy` (các endpoint đã có), `test_indexes`, `test_static`, `test_web_rules`.
7. Kiểm tra 3 trang theo skill mục 9 (1440px và 390px, tắt API, `grep` hex). Ghi LAST_RUN, dừng lại để người dùng xem.

**Đợt 2: các trang còn lại + đo độ trễ**
1. **Hành vi ăn uống:** E2–E7, trang `hanh-vi.html`.
2. **Món ăn:** E8, E10, E11, E14, trang `mon-an.html` (E12, E13 đã có từ đợt 1).
3. **Phân khúc người dùng:** E15, E16, `labels.py` (nhãn và chiến lược cụm), trang `phan-khuc.html`.
4. **Thời gian thực:** E25, trang `thoi-gian-thuc.html` (trạng thái rỗng cho đến khi có streaming).
5. **Test còn lại:** `test_consistency`, `test_privacy` với đủ E0–E26.
6. **Đo độ trễ:** `bench_latency.py` trên `vifood` và `vifood_local`, ghi `data/output/api_report.json` và `docker stats api`.
7. **Kết thúc bước 08:** chụp 7 trang ở 1440px và 390px vào `docs/images/`; cập nhật DATA_DICTIONARY (mục API), CLAUDE.md (11 container, cổng 8000, dòng 08 của bảng pipeline, lệnh pytest) và PROGRESS.

---

## Lỗi / sự cố và cách xử lý
- **Lần này:** bộ kiểm tra an toàn của Claude Code tạm thời không cho chạy lệnh shell (lỗi tạm thời, không phải bị từ chối). Vì vậy việc tìm tên trong file làm bằng công cụ tìm file. Thử lại sau thì lệnh chạy được, nên đã quét MongoDB và commit bình thường.
- **Lần trước:** không có lỗi. Máy không có `gh` CLI, nên skill được lấy bằng `git clone --sparse` vào thư mục tạm rồi mới chép vào dự án.

## Cần người dùng quyết định
1. **Câu lý do "đã nấu" hay "đã xem" cho `content_slot`.**
   - Skill mục 5 muốn ghi "Giống món X bạn đã nấu" hoặc "…bạn đã xem". Bước 06f có tính cờ `because_is_cooked` (96,7% là món đã nấu), nhưng bước 07 không xuất cờ này vào `recs`. API vì vậy không biết chắc nên dùng câu nào.
   - Phương án:
     - **(A, khuyên dùng)** sửa 07: thêm `because_cooked: true/false` vào phần tử `content_slot` của `recs.items` (chỉ 96.346 phần tử, khoảng 2 MB), rồi chạy lại `07 --only recs` trên cụm (khoảng 12 giây ghi);
     - (B) API tự đoán: `because_food_id` nằm trong `users.history` thì ghi "đã nấu", không thì "đã xem". Cách này sai với một phần user, vì `history` chỉ giữ 10 món;
     - (C) bỏ phân biệt, luôn ghi "Giống món X bạn từng quan tâm".
2. **Câu lý do cho `pop` và món bù.** Skill ghi:
   - `pop`: "Đang được nấu nhiều vào bữa {bữa} ở {vùng}";
   - món bù: "Đang được nấu nhiều ở vùng của bạn".

   Dữ liệu thật thì khác:
   - `pop` trong `recs` lấy từ phổ biến theo **vùng-tuổi**, không theo bữa. Bước 06f đã sinh câu "Đang được nhiều người {tuổi} tuổi ở miền {vùng} nấu".
   - Món bù xếp theo `stats.cook_rank` **toàn danh mục, cả năm**, không theo vùng. Ghi "ở vùng của bạn" là sai.

   Đề xuất:
   - `pop` dùng đúng câu của 06f;
   - món bù ghi "Được nấu nhiều trong danh mục". Khi có bộ lọc thì nêu bộ lọc, ví dụ "Món chay được nấu nhiều trong danh mục".
   - Sau đó sửa bảng ở skill mục 5 cho khớp.

   Đồng ý không?
3. **Sửa skill mục 1 về font:** đổi "subset vietnamese" thành "3 subset latin, latin-ext, vietnamese" (lý do ở mục F), và ghi rõ ECharts 5.5.1. Đồng ý không?
4. **Thêm `js/components.js`** (thẻ món, thanh lọc, viên trạng thái, trạng thái tải/lỗi/rỗng), vì 3 trang cùng dùng thẻ món. Skill mục 1 chưa có file này. Nếu đồng ý thì ghi thêm vào skill.
5. **Mục tiêu độ trễ ở mục G** (p95 < 50 ms cho gợi ý): giữ như vậy, hay muốn đặt mục tiêu khác để ghi vào báo cáo?

Có thể trả lời ngắn, ví dụ "1A, 2 đồng ý, 3 đồng ý, 4 đồng ý, 5 giữ".

Việc cần người làm (không đổi): kiểm tra tay 100 món; dựng notebook biểu đồ cho bước 05 và 06.

## Commit
- `563e8ff`: skill `frontend-design` (từ `anthropics/skills`) và `vifood-dashboard`, quy tắc trong CLAUDE.md.
- `90963df`: đề xuất thiết kế bước 08 (chưa code).
- Commit lần này: `Quy tac: khong ghi ten thanh vien ngoai bao cao` (CLAUDE.md, PROGRESS, LAST_RUN, skill `vifood-dashboard`).
