# Lần chạy gần nhất – 25/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/export_report.json`, MongoDB `vifood` và kết quả pytest của lần chạy này.
> Bản thiết kế bước 08 (mục A–H của lần trước) nay đã nằm trong **D15** (`docs/DECISIONS.md`); endpoint có trong DATA_DICTIONARY mục "API bước 08".

## Yêu cầu
Trả lời 5 câu hỏi thiết kế bước 08:
1. A: thêm `because_cooked` vào phần tử `content_slot` của `recs`, chạy lại `07 --only recs` trên cụm;
2. `pop` dùng câu của 06f, món bù ghi "Được nấu nhiều trong danh mục" (có bộ lọc thì nêu bộ lọc);
3. 3 subset font, ECharts 5.5.1;
4. thêm `js/components.js`;
5. giữ mục tiêu độ trễ.

Kèm 2 chỉnh sửa:
- a. Tổng quan giữ bố cục bản mẫu canvas, dùng lại E1, E2, E3, E6, E23;
- b. E17 thêm 2 user cho mỗi persona (`verify_only`), trang Gợi ý có hàng nút theo persona; E18, E19 không trả `truth`.

Sửa skill `vifood-dashboard` theo câu 2, 3, 4; ghi D15; làm đợt 1 theo mục H; ghi LAST_RUN kèm cách mở dashboard và kết quả pytest; chạy `/handoff`.

## Đã làm
- **Skill `vifood-dashboard`:**
  - mục 1: ECharts 5.5.1; font đủ 3 subset kèm `unicode-range`, tải bằng `scripts/08_fetch_vendor.sh`; thêm `js/components.js` vào cấu trúc;
  - mục 5: bảng câu lý do theo câu 2 (thêm dòng `fill`, `pop` dùng câu vùng-tuổi của 06f), món bù gắn `source="fill"`.
- **D15** trong `docs/DECISIONS.md`: nguyên tắc, 5 câu trả lời, 2 chỉnh sửa, và phần "Khi cài đặt đợt 1".
- **Bước 07, `recs.because_cooked`:**
  - Giá trị lấy từ câu lý do của `recs_final`, vì bảng này không giữ cờ `because_is_cooked`. Không cần chạy lại 06f.
  - Chỉ phần tử `content_slot` có trường này: `07` bỏ khóa khi giá trị null, bằng hàm `transform` chạy trong `foreachPartition`.
  - Chạy `--only` thì report được gộp vào report cũ (thêm `partial_runs`), không mất số liệu của 25 collection còn lại.
  - Đã chạy `--local --only recs` 3 lần (lần 1 và 2 dừng ở bước kiểm tra vì khóa `val`, xem mục "Lỗi"; lần 3 đạt), rồi chạy trên cụm 1 lần.
- **Service `api`:**
  - `docker/Dockerfile.api` (`python:3.12-slim`, fastapi 0.162.0, uvicorn 0.54.0, pymongo 4.19.0, pytest 9.1.1, httpx 0.28.1);
  - thêm vào compose (cổng 8000, RAM 512 MB, `API_DB`), healthcheck `/api/health`. Cụm giờ có **11 container**.
- **API** (`api/`): 16 endpoint của đợt 1: E0, E1, E2, E3, E6, E12, E13, E14, E17, E18, E19, E20, E22, E23, E24, E26.
  - Các file: `main.py` (middleware `Server-Timing`, gzip, cache header, 404 JSON cho `/api/...`, 503 khi mất MongoDB), `db.py`, `cache.py`, `text.py`, `dishes_common.py`, `reasons.py`, `labels.py`, `schemas.py`, `routers/{overview,behavior,dishes,recs,evaluation}.py`.
  - E2, E3, E6 vốn thuộc trang Hành vi (đợt 2), nhưng được làm sớm vì trang Tổng quan dùng (chỉnh sửa a). E14 làm sớm cho thẻ "top 5 món".
- **Web** (`web/`):
  - phần dùng chung: `css/theme.css` (token, `@font-face` 12 file), `js/api.js`, `js/layout.js`, `js/charts.js` (theme `vifood`), `js/components.js`, `img/placeholder-dish.svg`;
  - 3 trang đầy đủ:
    - `index.html` (Tổng quan);
    - `goi-y.html` (Gợi ý món, 2 chế độ);
    - `danh-gia.html` (Đánh giá mô hình).
  - 4 trang khung ghi "Trang đang được xây dựng" (Hành vi, Món ăn, Phân khúc, Thời gian thực), để liên kết trên thanh bên không trả 404.
- **ECharts và font:** `scripts/08_fetch_vendor.sh` tải về `web/vendor/`, `web/fonts/`, kèm giấy phép và `web/vendor/manifest.txt` (sha256).
- **pytest** (`api/tests/`, 8 file, 39 test): kết quả ở mục "Số liệu chính".
- **Kiểm tra trên trình duyệt** (theo skill mục 9):
  - đã xem 3 trang ở 1440px;
  - ở 390px: cả 7 trang không có phần tử nào tràn ngang, thanh bên nằm trên cùng;
  - tạm dừng MongoDB (`docker pause`): mọi thẻ hiện "Không kết nối được MongoDB" kèm nút "Thử lại"; bỏ dừng rồi bấm "Thử lại" thì thẻ tải lại được.
- **Tài liệu:**
  - CLAUDE.md: 11 container, service `api`, dòng 08 của bảng pipeline, lệnh build, restart, pytest; thêm 2 lỗi môi trường;
  - DATA_DICTIONARY: `recs.because_cooked`, `export_report.partial_runs`, mục "API bước 08";
  - PROGRESS.

### Cách mở dashboard
1. Khởi động service `api` (PowerShell, trong thư mục `docker/`). Lần đầu cần mạng để build image:
   ```
   docker compose up -d --build api
   ```
2. Mở các địa chỉ:
   - http://localhost:8000: Tổng quan;
   - http://localhost:8000/goi-y.html: Gợi ý món. Có thể thêm `?user=30494` để mở thẳng một user;
   - http://localhost:8000/danh-gia.html: Đánh giá mô hình;
   - http://localhost:8000/docs: tài liệu API (OpenAPI).
3. Đổi sang database phát triển:
   ```
   $env:API_DB="vifood_local"; docker compose up -d api
   ```
4. Sau khi sửa `api/*.py`: chạy `docker restart api`. Sau khi sửa `web/`: chỉ cần tải lại trang.
5. Chạy pytest:
   ```
   docker exec api python -m pytest -q -p no:cacheprovider api/tests --db vifood
   ```
   Bỏ `--db vifood` thì chạy trên `vifood_local`.

## Số liệu chính
**`recs.because_cooked` (cụm, `export_report.json` → `checks.recs_because_cooked`):**

| `source` | Có trường | Giá trị | Số phần tử |
|---|---|---|---|
| `als` | không | | 2.312.304 |
| `content_slot` | có | true | 93.137 |
| `content_slot` | có | false | 3.209 |
| `pop` | không | | 91.350 |

- Tỷ lệ true là 96,67%, khớp con số 96,7% của 06f.
- `recs`: 50.000 doc, 2.500.000 phần tử, 5 user mẫu vẫn `identical: true`; size **204,3 MB** (trước đó 202,6 MB), storage 49,7 MB, nén 4,11 lần.
- Lần chạy `--only recs` mất 40,3 giây; ghi `recs` mất 13,6 giây.
- Bản local (`vifood_local`): 9.303 true, 313 false; có thêm nguồn `rep` (639 phần tử, bản cụm không có).

**pytest:**

| Database | Kết quả | Thời gian |
|---|---|---|
| `vifood` | **39 đạt** | 5,2–5,8 giây |
| `vifood_local` | 37 đạt, 2 bỏ qua (2 phép so khớp chính xác chỉ chạy với `vifood`) | 5,2 giây |

| File | Số test | Kiểm tra chính |
|---|---|---|
| `test_recs.py` | 10 | 50 user theo hash (40 ấm, 5 ít, 5 lạnh) × 6 bộ lọc. Không có `truth`, `nutrition`, `score`, `persona_main`; không trùng món; mọi món thỏa bộ lọc; món bù đứng sau và không nằm trong 50 món gợi ý hay `history`; câu lý do đúng mẫu theo `source`; `hit` đúng với `test_cooks`; không lọc thì đúng 10 món đầu của `recs`; câu "đã nấu"/"đã xem" theo `because_cooked`; các lỗi 404, 422 |
| `test_text.py` | 5 | `normalize_query(dish_name) == name_search` với cả 5.499 món; chữ NFD, "Đ"; "đậu hũ", "dau hu" và bản NFD cho cùng kết quả; ký tự regex được escape |
| `test_new_user.py` | 2 | 3 bộ món × 3 bộ lọc × có/không vùng-tuổi: đủ 10 món, không gợi ý lại món đã chọn, thứ tự nguồn content → pop → fill, món `pop` thuộc đúng `popular` của vùng-tuổi; các lỗi 422, 404 |
| `test_privacy.py` | 4 | 14 endpoint không có khóa `truth`, `nutrition`; chỉ E17 có khóa chứa "persona"; giá trị persona không lọt vào hồ sơ hay gợi ý; E17 đủ 8 persona × 2 user, đúng persona, `verify_only: true` |
| `test_indexes.py` | 1 | 6 truy vấn chính dùng IXSCAN/IDHACK, không COLLSCAN; truy vấn bù món không có SORT |
| `test_static.py` | 5 | 7 trang trả 200, `no-cache`; ECharts và 12 font trả 200, có `max-age`; gzip; `/api/khong-co` trả 404 JSON; header `Server-Timing` |
| `test_web_rules.py` | 6 | skill mục 9: không mã hex ngoài `theme.css`, `charts.js`; không CDN; thanh bên đúng 7 mục, đúng thứ tự; mọi `<img>` có `alt`; mọi biểu đồ dùng theme `vifood` |
| `test_overview.py` | 6 | tổng lượt nấu và lượt xem 12 tháng bằng `overview` (2.382.842 và 18.637.934); 168 ô heatmap; NDCG@10 hybrid trên API = `models_metrics` (0,1588); khoảng tin cậy chứa hiệu |

**Một số số liệu của API và trang:**
- **API:**
  - RAM của `api` là 65,5 MB / 512 MB sau khi chạy pytest; nạp cache lúc khởi động mất 125 ms.
  - Gọi thử mỗi endpoint một lần, chưa có cache (chưa phải phép đo độ trễ, phép đo làm ở đợt 2): `Server-Timing app` 2–41 ms. E19 có bộ lọc mất 10,6 ms, trong đó MongoDB 7,5 ms.
- **Tổng quan:**
  - KPI: 5.499 món, 50.000 người dùng, 23,2 tr sự kiện, HDFS 898,7 MB (1,8 GB tính cả 2 bản sao), 2,5 tr dòng gợi ý (50 món mỗi người dùng);
  - tháng có Tết (2026-02) tô màu cam, 08/2026 và 09/2026 (val/test) tô màu slate.
- **Gợi ý, bộ lọc rất hẹp** (chay + bữa sáng + đồ uống, user #1): 1 món từ gợi ý và 9 món bù, câu lý do "Món chay, bữa sáng, đồ uống được nấu nhiều trong danh mục".
- **E17:** 3 user mỗi nhóm (ấm 1, 2, 3; ít 36, 561, 1760; lạnh 4, 44, 78) và 2 user cho mỗi persona trong 8 persona.

## Lỗi / sự cố và cách xử lý
- **`07 --local --only recs` lần 1 và 2 dừng ở bước kiểm tra** (`KeyError: 'val'`), vì `$group` của MongoDB bỏ khóa khi trường không tồn tại. Đã đổi sang `.get("val")`. Collection vẫn được ghi đúng trước khi lỗi, vì bước ghi chạy trước bước kiểm tra.
- **Report local và report cụm ghi chung một file** `export_report.json`. Đã sao lưu report của cụm trước khi chạy local rồi chép lại trước khi chạy trên cụm. Đã ghi lưu ý này vào CLAUDE.md.
- **Trên trang:**
  - Thanh ngang không hiện phần màu, vì `span.fill` là phần tử inline. Đã thêm `display:block`.
  - Khung "Người dùng mới" vẫn hiện khi đã bị ẩn, vì `section.row{display:flex}` thắng thuộc tính `hidden`. Đã thêm `[hidden]{display:none!important}`.
  - Hai biểu đồ ALS nằm chồng lên nhau. Đã thêm class `.split`.
- **Nút "Thử lại" không gọi lại API**, vì nhiều thẻ dùng chung một promise đã lỗi. Đã thêm `shared()` trong `api.js`: request lỗi thì bỏ promise đó, nên bấm "Thử lại" sẽ gọi API lần nữa. Đã thử lại bằng cách tạm dừng MongoDB.
- **Biểu đồ khoảng tin cậy không đọc được**: 7 phép so sánh có độ lớn chênh nhau khoảng 30 lần, nhãn trục chồng lên nhau. Đã đổi sang bảng "So sánh | Hiệu | KTC 95% | Kết luận".
- **Chú thích ban đầu ghi sai cách tính khoảng tin cậy.** Bản nháp ghi "bootstrap", nhưng `rec_common.paired_ci` dùng hiệu ghép cặp theo user, ±1,96 × sai số chuẩn. Đã sửa chú thích.
- **pytest trên `vifood_local` lệch 2 phép so khớp:**
  - các bảng `analysis_*` lệch `overview` 1.145 lượt nấu (235.981 so với 237.126);
  - NDCG hybrid trong `reports` (file của cụm) là 0,1588, còn trong `metrics` (kết quả local) là 0,1577.

  Đây là do dữ liệu local không đồng bộ, không phải lỗi API. Hai test này giờ chỉ chạy với `--db vifood`. Đã ghi vào việc còn treo.
- **Ảnh món không tải được trong môi trường này**: `image.cooky.vn` và `monngonmoingay.com` báo `ERR_CONNECTION_TIMED_OUT` trong trình duyệt của Claude, `curl` từ máy cũng lỗi 56. Ô ảnh vẫn có nền màu theo loại món, và ảnh lỗi được thay bằng `placeholder-dish.svg`. Chưa kiểm tra bằng trình duyệt thường của người dùng.
- **Cảnh báo pytest** `StarletteDeprecationWarning` (httpx với TestClient): chỉ là thông báo, không ảnh hưởng kết quả.

## Cần người dùng quyết định
1. **Món đã nấu trong gợi ý.**
   - Có 26,3% số ô trong top 10 gợi ý là món người dùng đã nấu (nằm trong `history`). Đo trên 5.000 user đầu tiên có lịch sử: 4.761 user có ít nhất 1 món như vậy. User #1 có 5/10 món, ví dụ "Rau củ kho chay" đã nấu 13 lần.
   - Đây là đúng thiết kế bước 06: nấu lại được tính là trúng, và chiếm 18,7% số cặp đã nấu. Nhưng thẻ món lại ghi "Người có khẩu vị giống bạn cũng hay nấu món này", nghe lạ với món đã nấu 13 lần.
   - Đề xuất: E19 trả thêm `n_cook_before` khi món có trong `history`, thẻ món hiện thêm chip "Bạn đã nấu 13 lần" (giữ nguyên chấm màu theo nguồn). Lưu ý `history` chỉ có 10 món nấu nhiều nhất, nên món nấu ít hơn sẽ không có chip.
   - Đồng ý không, hay giữ như hiện tại?
2. **Kiểm tra ảnh món bằng trình duyệt thường.** Mở http://localhost:8000/goi-y.html bằng Chrome hoặc Edge trên máy để xem ảnh có hiện không. Nếu không hiện, có thể chuyển sang tải sẵn ảnh của 5.499 món vào `web/img/dishes/`, nhưng việc này cần mạng và tốn dung lượng.
3. **Đợt 2** (4 trang còn lại, đo độ trễ): làm tiếp theo đúng mục H của thiết kế, sau khi xem đợt 1.

Việc cần người làm (không đổi): kiểm tra tay 100 món; dựng notebook biểu đồ cho bước 05 và 06; xem 3 trang của đợt 1 và so với bản mẫu canvas.

## Commit
- `90963df`: đề xuất thiết kế bước 08; `8fea7c9`: quy tắc không ghi tên thành viên.
- Commit của phiên này: `Buoc 08 dot 1: service api, Tong quan, Goi y mon, Danh gia mo hinh` (D15, skill, `07` + `export_report.json`, `api/`, `web/`, `docker/`, `scripts/08_fetch_vendor.sh`, CLAUDE.md, PROGRESS, DATA_DICTIONARY, file này).
