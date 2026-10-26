# Lần chạy gần nhất – 26/10/2026 (khuya, sau kiểm tay 100 món)

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Số liệu lấy từ `data/output/features_check_report.json` (do `scripts/eval_features_check.py` ghi). Món ăn là món thật; kiểm tay do người dùng làm.

## Yêu cầu
Người dùng đã kiểm tay xong 100 món: bản cuối `data/output/features_check_sample.csv`, bản điền lần 1 (trước khi chốt cách chấm `is_spicy`) `data/output/features_check_sample_lan1.csv`. Quyết định: **không sửa luật 03, không chạy lại pipeline**; các lỗi tìm thấy là hướng phát triển.
0. Commit ngay 2 file; ghi vào CLAUDE.md không chạy lại 03 khi chưa sao lưu file này.
1. `scripts/eval_features_check.py`: độ chính xác theo từng thuộc tính (7 cột) và theo món, cho bản cuối và bản lần 1; ghi `features_check_report.json`. `is_spicy` thêm cách (b), định nghĩa mở rộng tự đếm từ `nguyen_lieu`, kèm danh sách món lỗi (b), ghi rõ là ước tính.
2. D19: bảng độ chính xác và các phát hiện.
3. DATA_DICTIONARY: sửa mô tả `is_spicy`, ghi giới hạn của `is_vegetarian`.
4. PROGRESS: đóng việc kiểm tay; thêm mục "Hướng phát triển".

## Đã làm
**0. Commit ngay** (`b31ad7f`, trước mọi việc khác)
- `.gitignore` thêm ngoại lệ cho `features_check_sample_lan1.csv` (thư mục `data/output/*.csv` vốn bị bỏ qua).
- Commit `features_check_sample.csv` (bản cuối) và `features_check_sample_lan1.csv`.
- `CLAUDE.md`, mục Quy tắc làm việc: "Không chạy lại 03 khi chưa sao lưu `data/output/features_check_sample.csv`".

**1. `scripts/eval_features_check.py`** (chạy trên máy, không cần Spark) → `data/output/features_check_report.json`
- Đọc cột `kiem_tra`: "đúng", hoặc danh sách thuộc tính sai. Ô trống (10 món ở bản lần 1, chưa kết luận) thì bỏ cả dòng khỏi mẫu số.
- Kiểm tra hai bản cùng thứ tự món và nhãn của máy giống hệt nhau ở cả 7 cột.
- Cách (b) cho `is_spicy`: tách `nguyen_lieu` theo dấu phẩy.
  - Cay nếu một nguyên liệu là "ớt", hoặc bắt đầu bằng "ớt " (ớt băm, ớt sừng, ớt hiểm, ớt trái, ớt khô, ớt bột…), hoặc chứa "sa tế", "kim chi".
  - Không tính ớt chuông, tương ớt, tiêu, mù tạt vàng.
- Lỗi (b) = nhãn máy khác (b). Bạn định nghĩa lỗi gồm 2 loại: máy false mà có ớt, và máy true mà chỉ có ớt chuông (dòng 76). Tôi tính thêm loại thứ 3: máy true mà không có nguyên liệu cay nào. Chỉ có 1 món như vậy, dòng 89 Salad cam tình yêu (chỉ có mù tạt vàng). Lý do: món này cũng sai theo định nghĩa (b), và bạn đã chấm sai ở bản cuối. Bỏ món này ra thì (b) là 85,0%.

**2. D19** (`docs/DECISIONS.md`): quyết định không sửa luật, bảng độ chính xác, cách (b), các phát hiện (đối chiếu với code 03).

**3. DATA_DICTIONARY**
- `is_spicy`: mô tả đúng luật (tên món, tags, nguyên liệu: ớt khô, ớt bột, ớt hiểm, ớt xiêm, sa tế, kim chi, dầu ớt…; món ngọt và đồ uống luôn false; hạt tiêu, tương ớt không tính). Giới hạn: chưa nhận "ớt" tươi đứng riêng, nhận nhầm ớt chuông khi tên món có chữ "ớt", và mù tạt vàng.
- `is_vegetarian`: giới hạn (chưa coi sữa, bơ, kem, phô mai, mật ong, gelatine, mayonnaise là động vật; hạt nêm thường bị coi là chay), độ chính xác 90%.
- `season`: ghi chú khoảng 1/4 món khác "không", và trà ấm bị gán "nóng".
- Thêm dòng cho `features_check_sample_lan1.csv` và `features_check_report.json`.

**4. PROGRESS**
- Đóng việc kiểm tay 100 món; dòng bước 03 có độ chính xác.
- Thêm mục "Hướng phát triển (cần nêu trong báo cáo)" với 5 ý, ghi rõ mỗi thay đổi phải chạy lại 03 → 07.

## Số liệu chính
**Độ chính xác theo thuộc tính**

| Thuộc tính | Bản cuối (n = 100) | Bản lần 1 (n = 90) |
|---|---|---|
| `main_protein` | 90,0% | 92,2% |
| `main_method` | **79,0%** | 85,6% |
| `dish_category` | 95,0% | 93,3% |
| `dish_type_fixed` | 97,0% | 96,7% |
| `is_vegetarian` | 90,0% | 88,9% |
| `is_spicy` | 99,0% | 58,9% |
| `is_spicy` cách (b), **ước tính** | 84,0% (16 lỗi) | – |
| `season` | 99,0% | 100,0% |
| Trung bình 7 thuộc tính | 92,7% | – |

**Theo món**
- Bản cuối: đúng cả 7 thuộc tính **59/100**; sai 1 thuộc tính 33 món, sai 2 thuộc tính 6 món, sai 3 thuộc tính 2 món.
- Đúng 6 thuộc tính: 60% nếu bỏ `season`, cũng 60% nếu bỏ `is_spicy`.
- Bản lần 1 (n = 90): đúng cả 7 là 33,3%; bỏ `is_spicy` thì 66,7%.
- Bản lần 1 bỏ 10 món chưa kết luận: 1701, 786, 3905, 3300, 1519, 5279, 3515, 2672, 2760, 815.

**`is_spicy` cách (b)** (ước tính tự đếm từ nguyên liệu, **chưa kiểm từng món**): theo (b) có 29 món cay, máy gắn cay 17 món.

| Dòng CSV | food_id | Món | Máy | Loại lỗi | Nguyên liệu căn cứ |
|---|---|---|---|---|---|
| 2 | 806 | Bún thang | false | máy false, có ớt | ớt |
| 20 | 856 | Vịt rang tỏi | false | máy false, có ớt | ớt băm, ớt sừng |
| 37 | 4056 | Cuốn rong biển chay chấm xốt đậu phộng | false | máy false, có ớt | ớt băm |
| 39 | 2378 | Cá Diêu Hồng Chiên Muối Tỏi | false | máy false, có ớt | ớt |
| 43 | 2162 | Bò Kho | false | máy false, có ớt | ớt băm |
| 45 | 4086 | Gỏi Ổi Tai Heo | false | máy false, có ớt | ớt sừng, ớt băm |
| 49 | 3576 | Gỏi Xoài Khô Bò | false | máy false, có ớt | ớt |
| 55 | 2544 | Thịt Kho Trứng Nước Dừa | false | máy false, có ớt | ớt băm |
| 57 | 1126 | Chân giò nấu nước tương | false | máy false, có ớt | ớt trái đập dập |
| 76 | 4994 | Vịt Xào Ớt Chuông | true | máy true, chỉ có ớt chuông | ớt chuông |
| 81 | 3607 | Sườn Heo Xào Chua Ngọt Thơm Ngon | false | máy false, có ớt | ớt |
| 83 | 1410 | Trứng Chiên Rim Nước Mắm | false | máy false, có ớt | ớt sừng |
| 89 | 92 | Salad cam tình yêu | true | máy true, không có nguyên liệu cay | (chỉ mù tạt vàng) |
| 94 | 5320 | Tự Nấu Lẩu Đuôi Bò | false | máy false, có ớt | ớt |
| 95 | 1130 | Canh nấm rong biển | false | máy false, có ớt | ớt |
| 97 | 714 | Gỏi rau mầm | false | máy false, có ớt | ớt |

**Đối chiếu phát hiện với code 03** (chi tiết trong D19)
- `SPICY_ING` không có "ớt", "ớt băm", "ớt sừng". `SPICY_NAME` có "ớt", nên tên "Vịt Xào Ớt Chuông" bị gắn cay. Cả `SPICY_NAME` và `SPICY_ING` đều có "mù tạt".
- Cả 10 lỗi chay đều là máy ghi "chay" cho món có mật ong (4), sữa / sữa đặc / sữa chua, bơ, kem / whipping cream, phô mai, gelatine, mayonnaise.
  - `ANIMAL` có "gelatin", nhưng luật khớp theo ranh giới từ nên không nhận "gelatine".
  - Dòng 37: hạt nêm không ghi "chay", máy vẫn ghi chay; người kiểm chấm đúng vì không đủ căn cứ.
- `season`: danh sách "nóng" có "trà", áp cho nhóm đồ uống; chỉ "trà gừng" sang "lạnh". Vì vậy Trà Quế Hồng Táo (dòng 25) thành "nóng".
  - Ghi chú: luật không gán "nóng" cho **mọi** đồ uống, chỉ cho đồ uống có từ khóa (trà, nước ép, sinh tố, soda…). D19 ghi theo đúng code.
  - Máy: không 73, nóng 17, lạnh 7, tết 3.
- `main_method`, 21 lỗi:
  - 10 món đúng ra là "khác" (cuốn, nhúng, ngâm, làm lạnh, không nấu; máy gán luộc 4, hấp 2…);
  - 4 món đúng ra là "chiên";
  - 3 món đúng ra là "nướng";
  - 4 món nhầm giữa hầm/nấu, luộc, kho/rim, pha/xay.

## Lỗi / sự cố và cách xử lý
- `data/output/*.csv` bị `.gitignore` bỏ qua, nên bản lần 1 không tự vào Git. Đã thêm ngoại lệ trước khi commit.
- Trong thư mục `data/` có thêm `data/features_check_sample.csv` (ngày 24/10, cột `kiem_tra` trống, chưa đưa lên Git). Đây là bản trống cũ, khác cả hai bản đã điền. Tôi để nguyên, ghi vào "Việc còn treo".
- Bạn yêu cầu "theo món (đúng cả 6 thuộc tính)", nhưng file có 7 cột thuộc tính (`dish_type_fixed` cũng do luật 03 tạo). Report ghi cả "đúng cả 7" (59%) và "đúng 6 của 7" bỏ `season` hoặc bỏ `is_spicy` (đều 60%).
- Không chạy job nào trên cụm.

## Cần người dùng quyết định
1. **Báo cáo dùng con số "theo món" nào:** "đúng cả 7 thuộc tính" (59%), hay "đúng 6 thuộc tính" (60%, bỏ `season` hoặc `is_spicy`)? Đề xuất: **đúng cả 7 (59%)**, vì cả 7 cột đều do luật 03 tạo. Có thể ghi thêm 60% khi bỏ `season` (vì `season` có độ tin cậy thấp).
2. **Lỗi `is_spicy` (b) có tính dòng 89 (mù tạt vàng) không?** Tôi đang tính (84,0%, 16 lỗi); không tính thì 85,0% (15 lỗi). Đề xuất: tính, vì dòng 89 sai theo cả định nghĩa (b) lẫn chấm tay bản cuối.
3. **`data/features_check_sample.csv`** (bản trống cũ trong `data/`): xóa hay giữ? Đề xuất: xóa, để không nhầm với bản đã điền.

## Commit
- `b31ad7f` `Kiem tra tay 100 mon: ban cuoi va ban dien lan 1`: 2 file CSV, `.gitignore`.
- `D19: do chinh xac dac trung mon tu kiem tay 100 mon`: `scripts/eval_features_check.py`, `data/output/features_check_report.json`, `CLAUDE.md`, D19, DATA_DICTIONARY, PROGRESS, file này.
