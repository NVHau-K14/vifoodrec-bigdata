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
/data/results/                   kết quả phân tích và mô hình (bước 05 trở đi)
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

## File trong `data/output/`
| File | Nội dung |
|---|---|
| `clean_report.json` | Số liệu từng bước làm sạch |
| `features_report.json` | Độ phủ và phân bố từng thuộc tính món |
| `features_check_sample.csv` | 100 món để kiểm tra tay (cột `kiem_tra`, `ghi_chu`) |
| `simulate_report.json` | Số sự kiện, phễu, rating, kiểm tra persona, mùa, dung lượng HDFS |
| `simulate_config.json` | Toàn bộ tham số và trọng số persona |
| `events_sample.csv` | Toàn bộ sự kiện của 200 user |
