# Lần chạy gần nhất – 26/10/2026 (khuya, chốt kiểm tay)

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, không giới hạn độ dài.
> Số liệu lấy từ `data/output/features_check_report.json`. Món ăn là món thật; kiểm tay do người dùng làm.

## Yêu cầu
Trả lời 3 câu của LAST_RUN trước:
1. Báo cáo dùng "đúng cả 7 thuộc tính" 59%, ghi thêm 60% khi bỏ `season` (mẫu `season` nhỏ).
2. `is_spicy` (b) tính cả dòng 89: 84,0%, 16 lỗi.
3. `data/features_check_sample.csv` (bản trống cũ): mặc kệ, không động tới.

Ghi vào PROGRESS: phần dữ liệu và code đã xong hoàn toàn, kể cả kiểm tay; không còn việc nào cần chạy trên cụm.

## Đã làm
- **D19** (`docs/DECISIONS.md`): thêm đoạn "Chốt cách báo cáo".
  - Số chính theo món: đúng cả 7 thuộc tính, **59%**.
  - Ghi thêm **60% khi bỏ `season`**, vì chỉ 27/100 món có mùa khác "không".
  - `is_spicy` cách (b): **84,0%, 16 lỗi**, tính cả dòng 89.
- **PROGRESS:**
  - đầu file và "Việc tiếp theo": **phần dữ liệu và code đã xong hoàn toàn, kể cả kiểm tay 100 món; không còn việc nào cần chạy trên cụm**; bước tiếp theo là báo cáo Word + slide, số liệu lấy từ D10–D19;
  - mục `data/features_check_sample.csv`: đóng, ghi "người dùng chốt để nguyên, không động tới". File vẫn nằm ở `data/`, không xóa, không commit;
  - thêm một dòng nhật ký.
- `features_check_report.json` không đổi: đã có sẵn cả hai con số và tính dòng 89, không cần chạy lại script.
- Không chạy gì trên cụm.

## Số liệu chính
| Chỉ số (bản cuối, n = 100) | Giá trị dùng trong báo cáo |
|---|---|
| Món đúng cả 7 thuộc tính | **59%** (số chính) |
| Món đúng 6 thuộc tính, bỏ `season` | 60% (ghi thêm; mẫu `season` nhỏ: 27/100 món khác "không") |
| `is_spicy` cách (b), ước tính từ nguyên liệu | **84,0%**, 16 lỗi (14 máy false mà có ớt, 1 chỉ có ớt chuông, 1 chỉ có mù tạt vàng) |
| Theo thuộc tính | main_protein 90%, main_method 79%, dish_category 95%, dish_type_fixed 97%, is_vegetarian 90%, is_spicy 99%, season 99% |

## Lỗi / sự cố và cách xử lý
Không có.

## Cần người dùng quyết định
Không có câu hỏi mới. Bước tiếp theo: báo cáo Word + slide.

## Commit
- `Chot cach bao cao kiem tay; du lieu va code xong hoan toan`: D19, PROGRESS, file này.
