# data/sample

Vài trăm dòng mỗi bảng, trích bằng `scripts/make_sample.py` để xem cấu trúc dữ liệu mà không cần dựng cụm.
Dữ liệu hành vi (users, events, recs_final) là **mô phỏng**. Ý nghĩa từng cột: `docs/DATA_DICTIONARY.md`.
Cột mảng ghi dạng chuỗi JSON.

| File | Nguồn | Cách chọn | Số dòng | Số cột |
|---|---|---|---|---|
| `users.csv` | HDFS /data/events/users | user_id % 167 = 0 | 299 | 6 |
| `users_truth.csv` | HDFS /data/events/users_truth | cùng user với users.csv | 299 | 7 |
| `events.csv` | HDFS /data/events/events | user mẫu, 21–27/09/2026, 500 dòng đầu theo user, ts | 500 | 8 |
| `foods.csv` | HDFS /data/curated/foods | food_id % 18 = 0 | 306 | 23 |
| `dish_features.csv` | HDFS /data/features/dish_features | food_id % 18 = 0 | 306 | 16 |
| `ratings_original.csv` | HDFS /data/curated/ratings_original | 300 dòng đầu theo hash (user_id, food_id) | 300 | 3 |
| `recs_final.csv` | HDFS /data/results/models/recs_final | 6 user mẫu đầu tiên × 50 món | 300 | 8 |
| `raw_food_dataset_cookyweb.csv` | data/raw/food_dataset_cookyweb.csv | 300 dòng đầu | 300 | 15 |
| `raw_food_dataset_mnmnweb.csv` | data/raw/food_dataset_mnmnweb.csv | 300 dòng đầu | 300 | 18 |
| `raw_foods.csv` | data/raw/foods.csv | 300 dòng đầu | 300 | 16 |
| `raw_ratings.csv` | data/raw/ratings.csv | 300 dòng đầu | 300 | 3 |
