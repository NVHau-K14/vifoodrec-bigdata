# Lần chạy gần nhất – 25/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/export_report.json` (lần chạy trên cụm).

## Yêu cầu
Chốt thiết kế bước 07 theo 7 câu trả lời:
1. `recs` 1 doc/user, bỏ `reason`;
2. `pymongo` + `foreachPartition`, ghi vào collection tạm rồi đổi tên;
3. bỏ bộ lọc calo, dùng `is_quick`, lưu `nutrition` nhưng không hiển thị;
4. xuất `truth`, nhưng endpoint gợi ý không trả trường này;
5. có `test_cooks`;
6. `mongo-express` cổng 8090, tài khoản trong `.env`;
7. `history` 10 món, xếp theo `n_cook`, bằng nhau thì món nấu gần nhất đứng trước.

Kèm 6 sửa đổi:
- a. múi giờ phiên Spark;
- b. `asDict(recursive=True)`, Decimal sang double, NaN thành null;
- c. chỉ bỏ qua `BulkWriteError` khi mọi lỗi là 11000;
- d. bù món bằng `dishes` xếp theo `stats.cook_rank`, có `explain()`;
- e. tìm món bằng `$regex` trên `name_search`;
- f. `overview` ghi chú về `dishes.stats`.

Ghi D14, thêm `mongo-express` vào compose, viết `src/07_export_mongo.py`, chạy `--local` rồi chạy trên cụm, ghi LAST_RUN, chạy `/handoff`.

## Đã làm
- **D14** trong `docs/DECISIONS.md`: bản thiết kế đã chốt, 7 câu trả lời, 6 sửa đổi, và phần "Khi cài đặt và chạy".
- **`mongo-express`** đã thêm vào `docker/docker-compose.yml`: image `mongo-express:1.0.2`, cổng máy 8090 trỏ vào cổng 8081 của container, RAM 256 MB.
  - Tài khoản và chuỗi kết nối nằm trong `.env` (`ME_CONFIG_MONGODB_URL`, `ME_CONFIG_BASICAUTH_USERNAME`, `ME_CONFIG_BASICAUTH_PASSWORD`).
  - Đã chạy: http://localhost:8090 trả 401 khi không đăng nhập, 200 khi đăng nhập `admin` / `admin123`. Cụm giờ có **10 container**.
- **`src/07_export_mongo.py`:**
  - ghi 25 collection có dữ liệu, cộng `trending` (để trống, chỉ có index);
  - có tham số `--local` (ghi database `vifood_local`), `--only`, `--db`.
- **Sửa đổi a:** `get_spark()` đã đặt `Asia/Ho_Chi_Minh` từ đầu dự án (bước 04 và 05 cũng chạy qua hàm này), nên không phải sửa. Timestamp được đổi thành chuỗi bằng `date_format` trong Spark, và report ghi lại múi giờ phiên.
- **Sửa đổi b, c:**
  - `fix_types()` ép `DecimalType` sang double và `date` sang chuỗi ngay trong Spark; gặp timestamp chưa đổi thì báo lỗi.
  - `clean()` kiểm tra lại phía Python: NaN thành None, Decimal thành float.
  - `insert_docs()` chỉ bỏ qua `BulkWriteError` khi mọi mục trong `writeErrors` có mã 11000 và không có `writeConcernErrors`.
- **Sửa đổi d, e:** đã tạo index cho truy vấn bù món và tìm món, và có `explain()` trong report (xem bên dưới). Truy vấn bù món loại 50 món đã gợi ý bằng `$nin`.
- **Sửa đổi f:** `overview.notes` có 5 ghi chú: dữ liệu mô phỏng; `dishes.stats` là thống kê cả năm mô phỏng; mốc 01/09/2026; `nutrition` là số ngẫu nhiên; `truth` chỉ để kiểm chứng.
- **Chạy `--local` 3 lần** (database `vifood_local`, bản 10% với 5.000 user), lần nào cũng thành công.
  - Lần 1 phát hiện 2 vấn đề (xem mục "Lỗi"). Lần 2 sau khi sửa, tất cả kiểm tra đạt.
  - Lần 3 sau 3 sửa nhỏ: ví dụ `history` lấy đúng user có món bằng `n_cook`; `metrics` bỏ khóa lặp; bỏ `dish_type`.
  - Ghi đè 3 lần liên tiếp đều được, tức cơ chế `__staging` rồi đổi tên chạy lại không lỗi.
- **Chạy trên cụm 1 lần:** thành công, **66,1 giây**.
- Đã cập nhật `DATA_DICTIONARY.md` (mục MongoDB và `export_report.json`) và `CLAUDE.md` (10 container, `mongo-express`, dòng bước 07 của bảng pipeline).

## Số liệu chính
**Từng collection (cụm, database `vifood`; MB = 10⁶ byte; "nén" = size / storageSize):**

| Collection | Số doc | Cách ghi | Ghi (giây) | Size | TB/doc | Storage | Index | Nén |
|---|---|---|---|---|---|---|---|---|
| `recs` | 50.000 | foreachPartition (8 partition) | 11,8 | 202,6 MB | 4.052 B | 50,3 MB | 0,84 MB | 4,03 |
| `users` | 50.000 | foreachPartition (8 partition) | 12,0 | 53,8 MB | 1.075 B | 19,0 MB | 1,41 MB | 2,83 |
| `similar` | 5.499 | collect + insert_many | 2,4 | 17,1 MB | 3.116 B | 6,7 MB | 0,07 MB | 2,56 |
| `dishes` | 5.499 | collect + insert_many | 6,4 | 15,4 MB | 2.792 B | 8,3 MB | 0,95 MB (8 index) | 1,85 |
| `ingredient_rules` | 2.999 | collect | 0,4 | 0,58 MB | 194 B | 0,18 MB | 0,11 MB | 3,24 |
| `analysis_*` (13 collection) | 5.783 | collect | 0,2–0,3 mỗi bảng | 0,69 MB | | | | |
| `meal_rules` | 677 | collect | 0,3 | 0,08 MB | 121 B | | | |
| `ingredient_edges` | 416 | collect | 0,3 | 0,06 MB | 141 B | | | |
| `metrics` | 117 | collect | 0,0 | 0,03 MB | 235 B | | | |
| `clusters` | 22 | collect | 0,3 | 0,01 MB | 489 B | | | |
| `popular` | 14 | collect | 0,0 | 0,06 MB | 4.395 B | | | |
| `reports` | 12 | collect | 0,0 | 0,11 MB | 8.832 B | | | |
| `overview` | 1 | collect | 0,0 | | 1.511 B | | | |
| `trending` | 0 | chỉ tạo index | | | | | | |

- **Tổng 25 collection:** size 290,5 MB, storageSize 85,2 MB (**nén 3,41 lần**), index 4,1 MB.
- **Thời gian:** cộng thời gian ghi là 36,7 giây; kiểm tra 13,3 giây; cả job 66,1 giây (tính cả các bước Spark gom mảng và đếm).
- **So với bản thiết kế:**
  - `recs` đúng 202,6 MB như số đo trên mẫu.
  - `users` 53,8 MB, lớn hơn con số 42,9 MB dự tính, vì có thêm `group`, `test_cooks`, `truth`.
  - Tổng 290,5 MB so với khoảng 280 MB dự tính.

**Kiểm tra (`export_report.json`):**
- Số doc của từng collection khớp với số Spark đếm; job sẽ dừng nếu lệch.
- **`recs`:** 50.000 doc, tổng 2.500.000 phần tử `items`, đúng bằng số dòng `recs_final`; mỗi doc có đúng 50 món (nhỏ nhất 50, lớn nhất 50).
- **5 user mẫu theo hash** (30494, 33988, 14251, 38037 nhóm ấm; 21864 nhóm lạnh): danh sách trên MongoDB giống hệt `recs_final` trên HDFS, đúng thứ tự, cả 5 đều `identical: true`.
- **`similar`:** 274.950 phần tử, món nào cũng 50, khớp `item_sim`.
- **Toàn vẹn tham chiếu:** **0** `food_id` nằm ngoài `dishes`. Đã kiểm các `food_id` trong `recs`, `because_food_id`, `similar`, `companions`, `popular`, `history`, `test_cooks`.
- **Múi giờ (sửa đổi a):** 4.929.272 phiên; số phiên có giờ bắt đầu nằm ngoài khung `meal_slot` là **0**.
- **`users`:**

  | Trường | Số user |
  |---|---|
  | có `history` | 47.718 (tổng 439.297 món) |
  | có `test_cooks` | 39.012 (khớp số user được đánh giá ở test) |
  | có `cluster_k8` | 46.130 |
  | có `profile` | 48.173 |
  | có `truth` | 50.000 |

  Ví dụ `history` cho thấy thứ tự khi bằng `n_cook`: (5164, 5 lần), rồi (5417, 2 lần, 2026-08-28 09:11) đứng trước (1270, 2 lần, 2026-08-01 08:44).
- **`dishes`:** 656 món có `companions`; 19 món không có ảnh.

**`explain()` (sửa đổi d, e):**

| Truy vấn | Kế hoạch thắng | Khóa đã duyệt | Doc đã đọc | Trả về | ms |
|---|---|---|---|---|---|
| `recs.find({_id: 30494})` | IDHACK | 1 | 1 | 1 | 0 |
| **Bù món:** `dishes.find({is_vegetarian: true, is_quick: true, meal_types: "tối", _id: {$nin: 50 món gợi ý}}).sort({stats.cook_rank: 1}).limit(10)` | LIMIT ← FETCH ← IXSCAN(`is_vegetarian_1_stats.cook_rank_1`) | 30 | 30 | 10 | 3 |
| **Tìm món:** `dishes.find({name_search: {$regex: "dau hu"}}).limit(20)` | LIMIT ← FETCH ← IXSCAN(`name_search_1`) | 2.541 | 20 | 20 | 3 |
| Text index (minh họa): `dishes.find({$text: {$search: "dau hu"}}).limit(20)` | LIMIT ← TEXT_MATCH ← FETCH ← OR ← IXSCAN(`text_ten_mon`) | 20 | 20 | 20 | 1 |

- Truy vấn bù món dùng index và đã có sẵn thứ tự `cook_rank`, nên không phải sắp xếp trong bộ nhớ (không có bước SORT). Có 281 món thỏa bộ lọc ví dụ này.
- `$regex` không neo đầu chuỗi nên phải duyệt nhiều khóa của index (2.541), nhưng chỉ đọc 20 document. Với 5.499 món thì vẫn mất 3 ms.

**`overview`:**
- 5.499 món, 50.000 user, 23.205.143 sự kiện (view 18.637.934, cook 2.382.842, favorite 1.385.472, rate 798.895).
- Dung lượng HDFS (chưa tính bản sao / tính cả 2 bản sao):

  | Thư mục | Dung lượng |
  |---|---|
  | `raw` | 19,9 / 39,9 MB |
  | `curated` | 5,5 / 11,0 MB |
  | `features` | 0,2 / 0,4 MB |
  | `events` | 274,5 / 549,0 MB |
  | `results` | 567,3 / 1.134,7 MB |
  | `models` | 31,3 / 62,5 MB |

## Lỗi / sự cố và cách xử lý
- **Lần chạy local đầu tiên báo 42.799 lượt nấu có giờ nằm ngoài khung `meal_slot`.** Đây không phải lỗi múi giờ.
  - Bước 04 chọn giờ **bắt đầu phiên** trong khung `[h0, h1)` (`04_simulate.py:409`). Các sự kiện sau trong phiên có thể lấn sang giờ kế tiếp: lượt nấu buổi sáng lúc 9h có 6.977 lượt, trưa lúc 13h có 14.797, tối lúc 20h có 18.244, khuya lúc 0h có 2.766.
  - Đã đổi sang kiểm tra giờ của sự kiện đầu tiên trong mỗi phiên: 0 phiên sai ở cả local và cụm. Đã ghi vào D14.
- **`storageSize` bằng 0 ngay sau khi ghi**, vì WiredTiger chưa checkpoint. Đã chuyển `collStats` xuống cuối job, đọc sau lệnh `fsync`.
- **Ví dụ `history` ở lần 2 chọn nhầm user chỉ có 1 món**, vì `$arrayElemAt` trên phần tử không tồn tại trả về null, mà null = null nên điều kiện vẫn đúng. Đã thêm điều kiện `history.2` phải tồn tại.
- Không có lỗi nào khi ghi. Không gặp `BulkWriteError` nào, kể cả lỗi trùng khóa.

## Cần người dùng quyết định
Không có câu hỏi bắt buộc. Có 3 điểm để biết:
1. **Database `vifood_local`** (bản 10%, 5.000 user) vẫn còn trong MongoDB, chiếm 22,8 MB trên đĩa (theo `dbStats`, chưa tính 2,2 MB index). Nó có ích khi phát triển API ở bước 08 mà không đụng dữ liệu thật. Nếu muốn xóa thì báo.
2. **`.env` đang được commit vào git**, và có mật khẩu `admin123` (MongoDB, `mongo-express`). Với đồ án chạy trên máy thì chấp nhận được, nhưng nếu đưa repo lên GitHub công khai thì nên chuyển sang `.env.example`.
3. **Việc tiếp theo là bước 08** (FastAPI + dashboard), làm theo kiểu thiết kế trước giống bước 06 và 07.

Việc cần người làm (không đổi): kiểm tra tay 100 món (Hậu 50, Ngọc 50); Ngọc dựng notebook biểu đồ cho bước 05 và 06.

## Commit
- `3c3d8e4`: đề xuất thiết kế bước 07.
- Commit của phiên này: `Buoc 07: xuat MongoDB (26 collection), mongo-express` (`src/07_export_mongo.py`, compose, `.env`, `export_report.json`, D14, DATA_DICTIONARY, CLAUDE.md, PROGRESS, file này).
