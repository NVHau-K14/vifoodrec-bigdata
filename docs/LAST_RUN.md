# Lần chạy gần nhất – 25/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ `data/output/api_report.json`, pytest và phép đo trên trình duyệt của lần chạy này.

## Yêu cầu
Phần 1 (đã xong, commit `f524001`): đồng ý `n_cook_before` và chip "Bạn đã nấu N lần"; ảnh không tải sẵn; sửa 3 lỗi (biểu đồ theo tháng, bố cục trang Gợi ý, ảnh thay thế).

Phần 2 (lần này): **làm đợt 2 theo mục H** của bản thiết kế bước 08, ghi LAST_RUN, chạy `/handoff`. Phạm vi đợt 2:
- API E4, E5, E7, E8, E10, E11, E15, E16 (kèm nhãn và chiến lược cụm theo luật), E25;
- thay 4 trang khung (Hành vi, Món ăn, Phân khúc, Thời gian thực) bằng bản đầy đủ;
- `test_consistency`, `test_privacy` với đủ E0–E26;
- đo độ trễ (`api/bench_latency.py`) trên `vifood` và `vifood_local`, ghi `api_report.json` và `docker stats api`;
- chụp 7 trang ở 1440px và 390px vào `docs/images/`.

## Đã làm
**Phần 1 (tóm tắt, chi tiết ở commit `f524001`):**
- biểu đồ theo tháng bỏ 3 series rỗng, chú giải bằng HTML; `test_web_rules` có luật chặn series cột rỗng;
- trang Gợi ý:
  - hàng đầu gọn; menu "User mẫu" theo nhóm và theo persona ("chỉ để kiểm chứng", tên persona viết hoa chữ đầu);
  - hồ sơ và "Món hay nấu" ở cột phải;
  - kết quả đo: ở 1440 × 1000 hàng thẻ đầu kết thúc ở 740px; ở 390px danh sách bắt đầu ở 843px;
- ảnh thay thế theo 10 nhóm món, bỏ ảnh sau 4 giây; E19 có `n_cook_before`.

**Phần 2 – API (9 endpoint mới, đủ 25 endpoint E0–E26):**

| # | Endpoint | Ghi chú |
|---|---|---|
| E4 | `/api/behavior/top-dishes` | top 10 theo bữa, xếp theo lượt nấu hoặc lift |
| E5 | `/api/behavior/lift` | 4 kiểu nhóm × 6 thuộc tính; ô < 1.000 lượt nấu trả `lift = null` |
| E7 | `/api/behavior/habits` | số món mỗi phiên, nấu lại, lượt nấu mỗi user, phân bố điểm |
| E8 | `/api/dishes/summary` | aggregation `$facet` trên `dishes` + danh mục so với lượt nấu + đuôi dài |
| E10 | `/api/ingredients/top` | có hoặc bỏ gia vị |
| E11 | `/api/ingredients/graph` | cạnh FP-Growth xếp theo lift, nút kèm bậc |
| E15 | `/api/segments?k=3\|8\|11` | z giữa các cụm, nhãn, 3 đặc trưng nổi bật, đề xuất theo luật; `persona_kiem_chung` kèm `verify_only` |
| E16 | `/api/segments/8/{cluster}` | `$match cluster_k8` (index) + `$facet`: vùng, tuổi, nhóm, user mẫu |
| E25 | `/api/trending` | `trending` rỗng → `status = "chưa chạy"` |

- File mới: `api/routers/segments.py`, `api/routers/realtime.py`, `api/bench_latency.py`. File sửa: `behavior.py`, `dishes.py` (thêm `ing_router`), `labels.py` (bảng đặc trưng, luật đề xuất), `main.py`.
- **Nhãn cụm theo luật** (bảng luật ở D16), k = 8:

  | Cụm | Người dùng | Nhãn | Đề xuất | Persona kiểm chứng (chỉ để kiểm chứng) |
  |---|---|---|---|---|
  | 0 | 2.705 | Nấu bữa trưa · ít phiên | Gợi ý bữa trưa; kích hoạt lại | gia đình truyền thống |
  | 1 | 2.202 | Nấu bữa sáng · hoạt động ít | Gợi ý bữa sáng; kích hoạt lại | tập gym |
  | 2 | 9.449 | Nấu đa dạng · nhiều phiên | Tăng món khám phá; giới thiệu món mới | mê hải sản |
  | 3 | 6.729 | Nhiều món chay · ít chấm điểm | Bộ sưu tập món chay | ăn chay |
  | 4 | 8.108 | Xem là nấu · nhiều canh/súp | Mâm cơm món mặn kèm canh | gia đình truyền thống |
  | 5 | 5.191 | Nhiều món ngọt, đồ uống · ít hải sản | Chè, bánh, đồ uống cho bữa phụ | hảo ngọt |
  | 6 | 4.494 | Hay nấu lẩu · thích cay | Lẩu cuối tuần; món cay, món nhậu | thích cay/nhậu |
  | 7 | 7.252 | Chuộng món nhanh · nấu bữa tối | Món nhanh; gợi ý bữa tối | bận rộn |

  Luật không đọc persona. Nhãn khớp rõ với persona ở 5 cụm (3, 4, 5, 6, 7). Cụm 0, 1, 2 khó đối chiếu hơn: nhãn nói về bữa và mức hoạt động, không nói về món; cụm 2 là cụm lớn nhất (20,5%).

**Phần 2 – 4 trang mới** (thay trang khung):
- **Hành vi ăn uống** (`hanh-vi.html`), 9 thẻ:
  - heatmap giờ × thứ (Lượt nấu / Lượt xem), phễu;
  - lượt nấu theo tháng, món theo mùa (chọn vùng, cột chồng 100%);
  - nhóm món theo tháng (10 đường, mặc định hiện 4 nhóm lớn);
  - món nấu nhiều theo bữa (sáng/trưa/tối/khuya, nhiều nhất / đặc trưng);
  - heatmap lift (chọn kiểu nhóm và thuộc tính, màu 2 đầu chili ↔ herb);
  - bảng tỷ lệ chuyển đổi theo nhóm món;
  - thói quen nấu (4 biểu đồ nhỏ).
- **Món ăn** (`mon-an.html`):
  - KPI; danh mục so với lượt nấu (3 thuộc tính); đuôi dài (có đường chia đều);
  - nguyên liệu phổ biến (công tắc "Tính cả gia vị"); đồ thị mạng nguyên liệu (force, bỏ / giữ gia vị);
  - tra cứu món: ô tìm có/không dấu, bộ lọc, "Xem thêm", bấm thẻ để xem chi tiết món (dùng chung `dishDetail()` với trang Gợi ý). Không hiện dinh dưỡng.
- **Phân khúc người dùng** (`phan-khuc.html`):
  - chọn k = 3 / 8 / 11, kèm giải thích vì sao dùng 8; đường Silhouette, ARI, NMI theo k (đánh dấu 3, 8, 11);
  - quy mô cụm; heatmap hồ sơ cụm (18 đặc trưng, màu theo z, tooltip giá trị thật);
  - thẻ từng cụm (nhãn, 3 đặc trưng nổi bật, đề xuất, dòng "Persona kiểm chứng (chỉ để kiểm chứng)");
  - người dùng trong cụm (k = 8): vùng, tuổi, nhóm, user mẫu có liên kết sang `goi-y.html?user=`.
- **Thời gian thực** (`thoi-gian-thuc.html`): trạng thái luồng, đường lượt nấu theo cửa sổ, món thịnh hành. Hiện `trending` rỗng nên cả 3 thẻ ghi trạng thái rỗng có hướng dẫn. Khi có dữ liệu thì gọi lại mỗi 10 giây, dừng khi tab bị ẩn.
- **Phần dùng chung:**
  - `charts.js` thêm `multiLines`, `stacked100`, `divergingHeatmap`, `hGroupedBars`, `simpleBars`, `forceGraph`; `lines` có `yMin`, `markX`;
  - `components.js` thêm `dishDetail()`, `hbars(..., {wrap})`, ghi chú `note` trên thẻ món;
  - `theme.css` thêm `.ctrl`, `.mini-grid`, thẻ cụm `.cl`.

**Phần 2 – kiểm thử, đo, ảnh chụp:**
- `api/tests/test_consistency.py` (18 test, mới); `test_privacy.py` gọi đủ E0–E26 (26 đường dẫn), thêm 2 test cho E15, E16.
- `bench_latency.py` chạy trên `vifood` (cổng 8000) và `vifood_local` (uvicorn tạm ở cổng 8001 trong container `api`, đã tắt sau khi đo).
- 14 ảnh toàn trang trong `docs/images/` (`08_<trang>_1440.png`, `08_<trang>_390.png`).
- **Tài liệu:**
  - D16 trong DECISIONS (luật nhãn và đề xuất cụm, các quyết định khi cài đặt);
  - DATA_DICTIONARY: 9 endpoint mới, `api_report.json`;
  - CLAUDE.md: lệnh đo độ trễ, lỗi Chrome headless khi chụp 390px;
  - skill mục 6: heatmap 2 đầu, danh sách hàm vẽ dùng chung.

## Số liệu chính
**Độ trễ** (`api_report.json`, 200 lần tuần tự sau 20 lần khởi động; ms đo ở client qua HTTP):

| Endpoint | Nhóm | p95 `vifood` | p95 `vifood_local` | Mục tiêu p95 | Đạt |
|---|---|---|---|---|---|
| E1 overview | cache | 2,87 | 3,30 | < 10 | có |
| E2 heatmap | cache | 3,46 | 3,65 | < 10 | có |
| E3 monthly | cache | 3,45 | 3,65 | < 10 | có |
| E4 top-dishes | cache | 2,66 | 1,70 | < 10 | có |
| E5 lift | cache | 2,48 | 2,11 | < 10 | có |
| E6 funnel | cache | 1,84 | 1,78 | < 10 | có |
| E7 habits | cache | 1,84 | 1,94 | < 10 | có |
| E8 dishes/summary | cache | 2,80 | 2,77 | < 10 | có |
| E15 segments | cache | 3,48 | 3,72 | < 10 | có |
| E17 users/demo | cache | 1,74 | 2,04 | < 10 | có |
| E22 meta/filters | cache | 1,27 | 1,09 | < 10 | có |
| E23 eval/ranking | cache | 2,57 | 1,70 | < 10 | có |
| E24 eval/details | cache | 2,01 | 1,99 | < 10 | có |
| E10 ingredients/top | MongoDB | 2,75 | 2,98 | – | |
| E11 ingredients/graph | MongoDB | 4,04 | 7,20 | – | |
| **E12 dishes/search** | MongoDB | **14,16** | 18,83 | < 50 | có |
| **E13 dishes/{id}** | MongoDB | **4,16** | 4,23 | < 50 | có |
| E14 dishes | MongoDB | 6,95 | 7,21 | – | |
| E16 segments/8/{c} | MongoDB | 56,76 | 10,08 | – | |
| **E18 users/{id}** | MongoDB | **2,94** | 2,87 | < 50 | có |
| **E19 recs/{id}** | MongoDB | **5,47** | 5,53 | < 50 | có |
| **E20 recs/new-user** | MongoDB | **9,13** | 8,98 | < 80 | có |
| E25 trending | MongoDB | 2,17 | 2,64 | – | |

- **Mọi mục tiêu đều đạt** ở cả hai database (`all_targets_met: true`).
- **Dữ liệu lớn gấp 10 lần mà độ trễ gần như không đổi**, nhờ index: `vifood` 50.000 user so với `vifood_local` 5.000 user.
  - E19 p95 5,47 ms so với 5,53 ms; phần MongoDB trung bình 1,54 ms so với 1,50 ms.
  - Riêng E16 tăng theo cỡ cụm (aggregation trên cả cụm): 56,8 ms so với 10,1 ms, MongoDB trung bình 33,6 ms so với 4,4 ms.
- **E12** chậm nhất trong nhóm có mục tiêu (p95 14,2 ms; MongoDB 9,9 ms): `$regex` không neo đầu chuỗi phải quét cả index `name_search`.
- **E19, 10 luồng song song × 100 lần:** `vifood` p50 28,4 ms, p95 37,2 ms, 344,5 req/s; `vifood_local` p95 43,6 ms, 321,7 req/s. Uvicorn chạy 1 worker nên các request xếp hàng.
- **RAM `api`** sau khi đo: 59,2 MiB / 512 MiB.
- **Tải trang** (trình duyệt của Claude, 1440 × 1000, bộ nhớ đệm đã có ECharts và font, tức chưa phải lần tải lạnh): `load` 47–62 ms; mọi thẻ hết trạng thái tải sau 104–163 ms (Phân khúc chậm nhất). Mục tiêu là dưới 1,5 giây.

**Kiểm tra trên trình duyệt:**
- 7 trang ở 1440 và 390: không thẻ nào lỗi.
- Ở 390px: lần đầu trang Phân khúc tràn ngang (`scrollWidth` 411) vì ô chọn cụm có tên dài. Đã sửa, giờ cả 7 trang đều 390 (ảnh chụp bằng DevTools Protocol, `scrollWidth` = 390).
- Tạm dừng MongoDB (`docker pause`): trang Món ăn hiện "Không kết nối được MongoDB" kèm "Thử lại" ở 3 thẻ đọc MongoDB trực tiếp, sau 9,2 giây. Các thẻ dùng cache vẫn có số liệu. Đã bỏ dừng, `/api/health` trả ok.
- Đối chiếu số liệu: trên trang, Gini lượt nấu 0,698 và "1% món đầu chiếm 19%" (report: 19,02%), khớp `analysis_report.long_tail`. Phễu 12.474.894 cặp đã xem, khớp `analysis_funnel_by_category`.

**pytest:**

| Database | Kết quả | Thời gian |
|---|---|---|
| `vifood` | **61 đạt** | 6,2 giây |
| `vifood_local` | 58 đạt, 3 bỏ qua (3 phép so khớp chỉ chạy với `vifood`) | 5,4 giây |

| File | Số test | Mới / sửa ở lần này |
|---|---|---|
| `test_consistency.py` | 18 | **mới**: E4 thứ tự hạng và giá trị, `food_id` có trong `dishes`, `limit = 11` trả 422; E5 tỷ trọng mỗi nhóm cộng ~100%, lift = share ÷ overall, ô ít dữ liệu là null; E7 tổng tỷ trọng; E8 KPI đúng bằng đếm trực tiếp, đuôi dài tăng dần tới 100%; E10, E11 thứ tự, bậc nút = 2 × số cạnh; E15 đủ k cụm, z trung bình 0, nhãn, 1–2 đề xuất, k = 5 trả 422; E16 số user khớp `count_documents`, user mẫu đúng cụm, cụm 99 trả 404; E25 rỗng thì "chưa chạy"; với `vifood`: tổng điểm chấm = `overview`, user theo lượt nấu = phễu, `n_users` của E15 = report 06e |
| `test_privacy.py` | 6 | gọi đủ 26 đường dẫn E0–E26; persona chỉ ở E15, E17 (và E26, xem mục "Lỗi"); E16 không lộ persona |
| `test_recs.py` | 10 | (phần 1) `n_cook_before` |
| `test_web_rules.py` | 8 | (phần 1) luật series cột rỗng |
| `test_overview.py`, `test_static.py`, `test_text.py`, `test_new_user.py`, `test_indexes.py` | 6, 5, 5, 2, 1 | không đổi |

## Lỗi / sự cố và cách xử lý
- **E15 với `k` kiểu `Literal[3, 8, 11]`** luôn trả 422, vì tham số query là chuỗi. Đã đổi sang `int` và tự kiểm tra; `k` khác 3, 8, 11 trả 422.
- **`test_privacy` báo E26 có chữ "persona"**: `/api/reports/model_kmeans_report` trả nguyên report 06e, trong đó có persona phổ biến của từng cụm (số liệu gộp). Đã cho phép E26 có persona gộp nhưng vẫn cấm khóa `truth`, và ghi vào D16. E26 chỉ để gỡ lỗi, trang không gọi.
- **`vifood_local`: 4 test lệch** vì `reports` là file của cụm: tổng user của E15 (4.586 so với 46.130) và user theo lượt nấu (4.979 so với 49.815). Đã cho E15 tự cộng từ `clusters`, và chuyển các phép so với report sang chỉ chạy với `--db vifood`.
- **`bench_latency.py` lần 1 lỗi** `Client.request() takes 3 positional arguments` ở vòng khởi động. Đã sửa, lần 2 chạy đủ.
- **Trên trang:**
  - Biểu đồ mùa: chú giải xuống 2 dòng và đè lên cột. Đã chừa chỗ phía trên khi thẻ hẹp hơn 520px.
  - "Quy mô cụm": tên cụm dài làm thanh quá ngắn. Thêm `hbars(..., {wrap: true})` để nhãn xuống dòng.
  - Heatmap hồ sơ cụm: chú giải và nhãn trục bị cắt bên phải. Đã thêm lề phải và thu hẹp cột.
  - Trang Phân khúc tràn ngang ở 390px. Đã giới hạn bề rộng ô chọn trong `.ctrl`.
  - Câu đề xuất "Người dùng tích cực" trùng ý với "Khẩu vị đa dạng" (cùng ra món khám phá). Đã đổi thành "giới thiệu món mới trong danh mục trước".
- **Ảnh chụp 390px:**
  - Lần 1 dùng Chrome headless `--window-size=390`: trang được dựng rộng hơn rồi bị cắt (tiêu đề cụt).
  - Lần 2 bọc iframe: `100vh` kéo thanh bên dài bằng cả trang, dữ liệu chưa kịp tải.
  - Lần 3 điều khiển Chrome qua DevTools Protocol (giả lập thiết bị, cuộn hết trang để ảnh lazy tải, chờ 5 giây, chụp toàn trang): đúng. Đã ghi vào CLAUDE.md.
- Ảnh `image.cooky.vn` lần này tải được một phần trong trình duyệt của Claude. Ảnh nào không tải được thì sau 4 giây thành ảnh thay thế, nên ảnh chụp có thể lẫn cả hai.
- Cảnh báo pytest `StarletteDeprecationWarning` vẫn còn (chỉ là thông báo).

## Cần người dùng quyết định
1. **Bảng luật đề xuất cho cụm (D16)** là bản đầu, chọn theo hiểu biết chung về hành vi nấu ăn chứ không đo hiệu quả. Có muốn sửa câu nào trước khi đưa vào báo cáo không?
2. **E16 không có mục tiêu độ trễ** và p95 là 56,8 ms trên `vifood` (cụm 2 có 9.449 user). Giữ đọc MongoDB mỗi lần để thể hiện index (như thiết kế), hay cache 10 phút như các bảng nhỏ (sẽ còn khoảng 3 ms)?
3. **Bước tiếp theo:** thiết kế Structured Streaming (ghi `trending`, rồi E25 và trang Thời gian thực có dữ liệu thật), hay đo hiệu năng Spark (1 và 2 worker, 10/50/100%) trước?

Việc cần người làm (không đổi): kiểm tra tay 100 món; dựng notebook biểu đồ cho bước 05 và 06; xem 7 trang (có thể xem ảnh trong `docs/images/`).

## Commit
- `f524001`: sửa biểu đồ theo tháng, bố cục trang Gợi ý, ảnh thay thế, `n_cook_before` (phần 1).
- Commit của `/handoff` lần này: đợt 2 bước 08 (API, 4 trang, test, `bench_latency.py`, `api_report.json`, 14 ảnh, D16, DATA_DICTIONARY, CLAUDE.md, skill, PROGRESS, file này).
