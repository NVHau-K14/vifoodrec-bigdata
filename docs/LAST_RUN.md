# Lần chạy gần nhất – 26/10/2026 (khuya)

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/screenshots.json`, `data/output/analysis/heatmap_hour_dow.json`,
> `data/output/perf_runs.jsonl` và kết quả pytest.

## Yêu cầu
Trả lời 2 câu của LAST_RUN trước:
1. Xóa `vifood_local`, đổi pytest mặc định sang `vifood` (`conftest.py`, `CLAUDE.md`).
2. Repo để riêng tư, chưa làm gì với lịch sử `.env`; ghi vào README mục "Nếu công khai repo: đổi mật khẩu MongoDB / mongo-express".

Sửa sau khi soát ảnh:
- a. `mongo_recs.png` thay bằng ảnh 1 document `recs` (mở 2–3 phần tử `items`); thêm `mongo_trending_doc.png` (1 document `trending`).
- b. `nb_06_bang_so_sanh`: bảng sát lề trái; in đậm giá trị tốt nhất từng cột thay vì cả hàng Hybrid; chú thích "Hybrid: mô hình được chọn".
- c. PROGRESS, mục "Khác với kế hoạch / hạn chế": 04 không có lượt nấu khoảng 14–16h và 1–5h; 04 ở 50% / 1 worker chậm hơn mỗi user qua 3 lần đo, chưa rõ nguyên nhân.
- d. PROGRESS: phần dữ liệu và code xong, bước tiếp theo là báo cáo Word và slide; ảnh món ăn không quan trọng, không chụp lại.

## Đã làm
**1. `vifood_local`**
- Đã xóa database `vifood_local` (trước khi xóa: 26 collection, dữ liệu 59,9 MB, lưu trữ 22,8 MB). MongoDB còn `vifood` cùng 3 database hệ thống.
- `api/tests/conftest.py`: `--db` mặc định là `vifood`, docstring sửa theo.
- `CLAUDE.md`: lệnh kiểm thử không cần `--db vifood`; ghi chú `vifood_local` đã xóa (`07 --local` vẫn ghi vào đó nếu chạy lại).
- README: lệnh pytest sửa theo.
- pytest (mặc định, tức `vifood`): **64/64 đạt**.

**2. README mục 5 "Nếu công khai repo"**
- Các commit cũ còn `.env`; `docker-compose.yml` ghi mật khẩu MongoDB mặc định.
- Trước khi công khai: đổi mật khẩu MongoDB (`admin`) và mật khẩu đăng nhập mongo-express, cập nhật `.env` và compose. Với cụm đang chạy thì phải đổi mật khẩu ngay trong MongoDB (`db.changeUserPassword`), vì biến `MONGO_INITDB_*` chỉ có tác dụng khi volume còn trống.
- Đổi mật khẩu là đủ, không cần làm sạch lịch sử.
- Mục "Dữ liệu và giấy phép" thành mục 6.

**3. Ảnh mongo-express (a)**
- **Không dùng được trang document riêng của mongo-express 1.0.2** (`/db/vifood/recs/<id>`): với `_id` không phải ObjectId (`recs` dùng số, `trending` dùng chuỗi), mongo-express báo `BSONTypeError` và **tiến trình bị sập, container dừng**. Đã `docker start mongo-express` lại (container không có chính sách tự khởi động lại).
- Cách làm thay: trên trang collection, lọc đúng 1 document theo `_id` (ô Simple, kiểu Number / String), rồi bấm mở 3 phần tử đầu của `items`. Ảnh có ô lọc, dòng "1 documents retrieved", document đã mở, thống kê và index của collection.
- `scripts/capture_screens.py`: nhóm `mongo` chụp theo cách này (hàm `expand_items`, lấy trước các nút ⊕ đang hiện rồi mới bấm; lần đầu bấm theo thứ tự nên đóng lại phần vừa mở).
  - `mongo_recs.png`: user 8111, 3/50 phần tử mở (`rank, food_id, score, source, because_food_id`).
  - `mongo_trending_doc.png`: cửa sổ `2026-09-27T17:00|all` (17:00–18:00, đông nhất ngày: 1.455 lượt nấu, 8.221 lượt xem, 908 món), 3/20 phần tử mở (`food_id, cooks, views, favorites, rank, prev_cooks`). mongo-express hiện `window_start` theo UTC (10:00 GMT = 17:00 giờ Việt Nam).

**4. Bảng so sánh mô hình (b)**
- `notebooks/06_mo_hinh.ipynb`: bảng sát lề trái của ảnh; tiêu đề và chú thích cũng canh trái.
- In đậm giá trị tốt nhất từng cột (mọi độ đo đều cao hơn là tốt hơn), **không xét Ngẫu nhiên**, vì mô hình ngẫu nhiên luôn có coverage 100%, novelty 13,90 và diversity 0,942 cao nhất. Ô in đậm:
  - Hybrid: P@10, R@10, NDCG@10, MAP@10, NDCG@10 khám phá;
  - Nấu lại: coverage 97,5%;
  - Content: novelty 12,93;
  - Phổ biến chung: diversity 0,917.
- Chú thích dưới bảng: "Hybrid: mô hình được chọn. In đậm: giá trị tốt nhất từng cột (cao hơn là tốt hơn), không xét Ngẫu nhiên…". Ảnh mới 1995 × 628 px.

**5. PROGRESS (c, d)**
- Đầu file và "Việc tiếp theo": **phần dữ liệu và code đã xong; bước tiếp theo là báo cáo Word + slide.**
- Mục đổi tên thành "Khác với kế hoạch / hạn chế (cần nêu trong báo cáo)", thêm 2 ý:
  - **Không có lượt nấu khoảng 14–16h và 1–5h.** Giờ bắt đầu phiên ở 04 lấy trong khung bữa `SLOT_HOURS`: sáng 6–9h, trưa 10–13h, tối 16–20h, khuya 21–24h. Ngoài các khung này chỉ còn sự kiện lấn giờ của phiên bắt đầu trước đó. Cả năm: 14h có 89 lượt nấu, 1h có 8, các giờ 2–5h và 15h bằng 0. Vì vậy biểu đồ ngày phát lại về 0 ở các cửa sổ kết thúc 15:00–16:00.
  - **04 ở 50% / 1 worker chậm hơn mỗi user, qua 3 lần đo:** thời gian task giai đoạn sinh 41,1–44,9 ms/user, so với 31,9 và 33,3 ms/user ở 100% / 1 worker (r1, r3). Chưa rõ nguyên nhân.
- Ghi ảnh món ăn không quan trọng, không chụp lại. Đóng các mục `vifood_local` và `.env` (repo riêng tư, xem README mục 5).

## Số liệu chính
- pytest mặc định (`vifood`): 64 đạt, 0 lỗi.
- Ảnh mới hoặc thay (tổng số ảnh giao diện trong `screenshots.json`: 33):

| File | Nội dung | Kích thước (px) | KB |
|---|---|---|---|
| `mongo_recs.png` | mongo-express: 1 document `recs` (user 8111), mở 3/50 phần tử `items` | 1440 × 2990 | 155 |
| `mongo_trending_doc.png` (mới) | mongo-express: 1 document `trending` (`2026-09-27T17:00\|all`), mở 3/20 phần tử `items` | 1440 × 2597 | 160 |
| `mongo_trending.png` | mongo-express: collection `trending` (chụp lại, không đổi nội dung) | 1440 × 1000 | 75 |
| `mongo_vifood.png` | mongo-express: database `vifood` (chụp lại sau khi xóa `vifood_local`) | 1440 × 2557 | 371 |
| `nb_06_bang_so_sanh.png` | Bảng so sánh mô hình, in đậm giá trị tốt nhất từng cột | 1995 × 628 | 133 |

- Lượt nấu theo giờ (cả năm, `heatmap_hour_dow`): 0h 28.850 · 1h 8 · 2–5h 0 · 6h 46.126 · … · 13h 145.410 · 14h 89 · 15h 0 · 16h 114.393 · 17h 295.553 · … · 21h 19.716 · 22h 48.474 · 23h 48.203.

## Lỗi / sự cố và cách xử lý
- **mongo-express sập khi mở trang document có `_id` không phải ObjectId** (lỗi của mongo-express 1.0.2, không phải dữ liệu). Container dừng hẳn; đã khởi động lại và chuyển sang chụp trang collection lọc theo `_id`. Khi demo nên tránh bấm nút xem document (biểu tượng liên kết) ở `recs`, `users`, `dishes`, `trending`… vì sẽ làm sập mongo-express; nếu lỡ bấm thì chạy `docker start mongo-express`.
- Lần chụp đầu chỉ mở được 1 phần tử `items` (bấm nút thứ hai lại đóng phần thứ nhất). Đã sửa như mục 3.
- Đầu và cuối phiên: cụm 11 container chạy (mongo-express được khởi động lại giữa phiên), không có job hay luồng nào chạy.

## Cần người dùng quyết định
Không có câu hỏi mới. Bước tiếp theo theo PROGRESS: báo cáo Word + slide.

Việc cần người làm (không đổi): kiểm tra tay 100 món trong `data/output/features_check_sample.csv`.

## Commit
- `Xoa vifood_local, pytest mac dinh vifood; anh 1 document mongo; bang so sanh mo hinh; han che cho bao cao`: `api/tests/conftest.py`, `CLAUDE.md`, `README.md`, `scripts/capture_screens.py`, `notebooks/06_mo_hinh.ipynb`, `docs/images/{mongo_recs,mongo_trending,mongo_trending_doc,mongo_vifood,nb_06_bang_so_sanh}.png`, `data/output/screenshots.json`, PROGRESS, file này.
