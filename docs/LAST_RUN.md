# Lần chạy gần nhất – 25/10/2026

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Dữ liệu hành vi là **mô phỏng**. Số liệu lấy từ pytest và phép đo trên trình duyệt của lần chạy này.

## Yêu cầu
Trả lời 3 câu hỏi của lần trước:
1. đồng ý thêm `n_cook_before` và chip "Bạn đã nấu N lần", giữ chấm màu theo nguồn;
2. ảnh: trình duyệt thường trên máy tải được `monngonmoingay.com`, còn `image.cooky.vn` hết thời gian chờ (4.291/5.499 món), nên không tải sẵn;
3. sửa 3 lỗi rồi mới làm đợt 2.

3 lỗi cần sửa:
- a. biểu đồ theo tháng ở Tổng quan: 3 series rỗng làm chú giải chiếm chỗ, cột mảnh và lệch trái; thêm luật vào `test_web_rules`;
- b. bố cục trang Gợi ý: hàng đầu gọn, rồi bộ lọc và danh sách, hồ sơ sang cột phải. Mục tiêu: ở 1440 × 1000 thấy hàng thẻ đầu; ở 390px danh sách bắt đầu trong 900px đầu. Tên persona viết hoa chữ đầu;
- c. ảnh thay thế theo nhóm món (nền màu, biểu tượng SVG, tên nhóm), timeout tải ảnh khoảng 4 giây, ghi vào skill mục 4.

Sau đó kiểm tra ở 1440 và 390, chạy pytest, commit, ghi LAST_RUN; rồi làm đợt 2.

## Đã làm
- **a. Biểu đồ theo tháng** (`web/js/charts.js`):
  - bỏ 3 series rỗng; chú giải viết bằng HTML (`MONTH_LEGEND` trong `components.js`, ô màu `.sw`);
  - cột rộng 58% mỗi ô tháng (tối đa 40px).
  - `test_web_rules.py` thêm 2 test:
    - `test_no_empty_bar_series`: tìm mọi object có `type: 'bar'` trong `web/js/*.js` (đếm ngoặc nhọn), báo lỗi nếu có `data: []` mà không có `barGap: '-100%'`;
    - `test_empty_bar_rule_catches_legend_series`: kiểm tra chính luật trên.
  - Đã chạy luật trên bản `charts.js` cũ (HEAD): bắt đúng 3 series "Train", "Tháng có Tết", "Val / test".
- **b. Trang Gợi ý** (`goi-y.html`, `goi-y.js`, `goi-y.css`):
  - hàng đầu là một thẻ gọn: nút chế độ (Người dùng có sẵn / mới) · ô "Mã người dùng" · menu "User mẫu" · nút "Xem gợi ý". Chọn trong menu là xem ngay;
  - menu "User mẫu" có 4 nhóm: "Nhóm ấm – nhiều lịch sử", "Nhóm ít lịch sử", "Nhóm lạnh – chưa có lịch sử" (3 user mỗi nhóm), và "Theo persona – chỉ để kiểm chứng" (16 user). Mỗi dòng ghi persona viết hoa chữ đầu, mã user, vùng và tuổi, ví dụ "Bận rộn – #2 · Trung, 25-34 tuổi";
  - ngay sau là thẻ "Món gợi ý" (bộ lọc, lưới thẻ món, chú giải) và thẻ chi tiết món;
  - cột phải: thẻ "Hồ sơ" và thẻ "Món hay nấu" (đủ 10 món của `history`). Màn hẹp thì 2 thẻ này xuống dưới danh sách. Chế độ "Người dùng mới" ẩn cột phải;
  - **màn hẹp, dùng chung cho mọi trang** (`theme.css`):
    - khi thanh bên nằm trên (< 792px), 7 mục xếp thành hàng chip (vẫn cao 44px, chữ 13px, chỉ mục hiện tại có chấm), hộp mô phỏng gọn lại;
    - ≤ 640px: bộ lọc thu vào nút "Bộ lọc · N đang bật" (`aria-expanded`); dòng tóm tắt nằm cạnh nút.
- **c. Ảnh thay thế** (`components.js`, `theme.css`):
  - khung ảnh luôn có ảnh thay thế ở dưới; ảnh thật hiện dần lên khi tải xong;
  - ảnh lỗi, thiếu `image_link`, hoặc quá 4 giây (`IMG_TIMEOUT_MS`, đếm từ lúc ảnh sắp vào màn hình) thì gỡ `src` và bỏ ảnh thật;
  - ảnh thay thế: nền theo nhóm món (3 tông có sẵn: herb, chili, slate), biểu tượng SVG nét mảnh riêng cho 10 nhóm, tên nhóm. Ảnh nhỏ 56 × 42 chỉ có biểu tượng;
  - `wireImgFallback(document.body)` gọi một lần trong `layout.js` cho mọi trang; `miniList` và kết quả tìm món dùng chung `dishThumb()`.
- **`n_cook_before`:**
  - E19 trả thêm trường này khi món nằm trong `history` (`api/routers/recs.py`, `schemas.py`);
  - thẻ món hiện chip đầu tiên "Bạn đã nấu N lần" (nền herb nhạt, chữ đậm), giữ chấm màu theo nguồn. Nguồn `rep` không có chip vì câu lý do đã nói;
  - dòng chú thích dưới danh sách thêm câu "N món người này đã nấu trước đó: nấu lại cũng được tính là gợi ý trúng";
  - `test_recs` kiểm tra `n_cook_before` đúng bằng `history.n_cook`, món ngoài `history` (kể cả món bù) là null.
- **Tài liệu:**
  - skill `vifood-dashboard`: mục 3 (thanh bên ở màn hẹp), mục 4 (ảnh thay thế + bảng 10 nhóm, chip "Bạn đã nấu", bộ lọc thu gọn, chú giải biểu đồ bằng HTML), mục 5 (bố cục trang Gợi ý);
  - DECISIONS: D15 thêm phần "Sửa sau khi xem đợt 1"; DATA_DICTIONARY: `n_cook_before` trong RecItem.

## Số liệu chính
**Đo trên trình duyệt (trang Gợi ý, user #1):**

| Kích thước | Đo | Kết quả | Mục tiêu |
|---|---|---|---|
| 1440 × 1000 | đáy hàng thẻ đầu | 740px (lưới 3 cột, bắt đầu ở 439px) | ≤ 1000px |
| 390 × 844 | đầu lưới thẻ món | 843px (thanh bên cao 346px; trước khi thu gọn là 394px và lưới ở 939px) | ≤ 900px |
| 390 × 844 | `scrollWidth` | 390, không phần tử nào tràn ngang | = 390 |
| 390, mở bộ lọc | đầu lưới thẻ món | 1.086px | – |

- User #1 có 5/10 thẻ có chip: "Bạn đã nấu 13 lần" (Rau củ kho chay), 4, 3, 2, 3 lần.
- **Ảnh trong trình duyệt của Claude lần này:** ảnh `monngonmoingay.com` tải được (9 ảnh ở màn hình đầu hiện bình thường), ảnh `image.cooky.vn` vẫn treo và được thay bằng ảnh thay thế sau 4 giây. Đã thử gán `src` hỏng cho thẻ đầu: thẻ chuyển ngay sang ảnh thay thế "Món chính".
- **Tổng quan:** biểu đồ theo tháng chỉ còn 1 series (12 cột), không còn legend của ECharts; xem ở 1440 và 390 đều không tràn ngang, không thẻ nào lỗi.

**pytest:**

| Database | Kết quả | Thời gian |
|---|---|---|
| `vifood` | **41 đạt** | 9,5 giây |
| `vifood_local` | 39 đạt, 2 bỏ qua (2 phép so khớp chỉ chạy với `vifood`) | 5,1 giây |

Tăng từ 39 lên 41 test: thêm 2 test series cột rỗng. `test_recs` có thêm phép kiểm tra `n_cook_before`.

## Lỗi / sự cố và cách xử lý
- **Ở 390px, lần đo đầu danh sách bắt đầu ở 939px** (thanh bên 394px, dòng tóm tắt bộ lọc chiếm 2 dòng). Đã bỏ chấm của các mục không phải trang hiện tại, chữ mục 13px, và đặt dòng tóm tắt cạnh nút "Bộ lọc". Còn 843px.
- **Hồ sơ và "Món hay nấu" dùng chung một request**: nếu dùng chung một promise thì nút "Thử lại" sẽ chờ lại promise đã lỗi. Đã dùng `shared()` của `api.js`, request lỗi thì được gọi lại.
- Cảnh báo pytest `StarletteDeprecationWarning` vẫn còn (chỉ là thông báo).

## Cần người dùng quyết định
Không có câu hỏi mới cho phần sửa lỗi này. Đợt 2 làm tiếp ngay sau commit này; kết quả sẽ ghi đè file này.

Việc cần người làm (không đổi): kiểm tra tay 100 món; dựng notebook biểu đồ cho bước 05 và 06; xem lại trang Gợi ý và Tổng quan sau khi sửa.

## Commit
- `Buoc 08: sua bieu do theo thang, bo cuc trang Goi y, anh thay the, n_cook_before` (web/, api/, skill, DECISIONS, DATA_DICTIONARY, file này).
