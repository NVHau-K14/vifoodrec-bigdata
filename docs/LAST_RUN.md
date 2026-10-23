# Lần chạy gần nhất – 24/10/2026 01:40

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, tối đa khoảng 80 dòng.

## Yêu cầu
Làm 5 việc đã chốt trong LAST_RUN trước. Thêm bước ghi LAST_RUN vào `/handoff`. Commit `CLAUDE.md` và `LAST_RUN.md` do chat sửa.

## Đã làm
1. **Spark History Server** (bật trước khi chạy lại):
   - `get_spark()` trong `common.py` bật `spark.eventLog.enabled`, ghi vào `logs/spark-events/`;
   - thêm service `spark-history` vào compose, cổng 18080. Đã khởi động riêng service này, 8 container cũ không bị tạo lại;
   - thêm `logs/` vào `.gitignore`.

   History Server đã thấy đủ 3 app: `04_simulate` (cụm, 542 giây), `05_analysis` (cụm, 109 giây), `04_simulate` (local 10%).
2. **`zipf_offset = 30`** ở bước 04: `pop_term = −0,45·log(hạng + 30)`.
   - Chạy lại 04 (100%) → 05 trên cụm, rồi sinh lại bản 10% ở local.
   - Đã sao lưu 6 file xuất của bản 100%, rồi khôi phục lại (checksum khớp) và xóa thư mục backup.
   - `simulate_report.json` là bản 100%.
3. **Bước 03:** mẫu kiểm tra tay chọn theo `xxhash64(food_id, 42)`. Đã thử: chia 1 hay 7 partition đều ra cùng 100 món. Chỉ sửa code, chưa chạy lại 03.
4. Không đặt git config, không tạo repo GitHub. Phân công trong tài liệu giữ nguyên.
5. Ghi D11 vào DECISIONS (bảng offset 0/10/30 và số liệu thật ở 100%). Việc "chụp ảnh UI" trong "Việc còn treo" chuyển thành "để cuối dự án, làm cùng đo hiệu năng".

Ngoài ra:
- `/handoff` có thêm bước 5 "ghi đè `docs/LAST_RUN.md` theo mẫu";
- `CLAUDE.md` ghi cụm có 9 container và thêm dòng về `spark-history`.

## Số liệu chính
| Chỉ số | Giá trị |
|---|---|
| Sự kiện (100%) | **23.205.143**, chạy 543 giây (trước đó 23.141.780) |
| Theo loại | view 18.637.934 · cook 2.382.842 · favorite 1.385.472 · rate 798.895 |
| Món đứng đầu | "Canh hào thanh mát" **1,44%** lượt nấu (trước đó 5,17%). Kỳ vọng ~1,5%: **đạt** |
| Gini lượt nấu | **0,698** (trước đó 0,732). Kỳ vọng ~0,71: thấp hơn 0,012 |
| Top 1% / 10% món | 19,0% / 57,7% lượt nấu |
| Rating | trung bình 3,705 (trước đó 3,78), độ lệch chuẩn 1,07 |
| Persona | ăn chay 100% món chay · mê hải sản 65,2% · bận rộn 92,3% · cay/nhậu 67,0% |
| Bước 05 | 104 giây, kiểm tra tổng đều đúng. Món Tết tháng 2 chiếm 19,2%; lift: miền Trung + món cay 1,36, cuối tuần + lẩu 1,54 |
| Bản 10% local | 5.000 user, 2.292.479 sự kiện |

## Lỗi / sự cố và cách xử lý
- Gini 0,698 thấp hơn mức ~0,71 mà chat đo ở quy mô 5%. Đuôi dài vẫn rõ, nên không chỉnh thêm.
- Rating trung bình giảm 0,075 điểm. Lý do: món phổ biến (có `quality` cao) không còn chiếm nhiều lượt chấm như trước.
- Lần đầu thử mẫu hash bị lỗi do script thử đọc đường dẫn không có `file://`, nên Spark hiểu là HDFS. Lỗi ở script thử, không phải ở code bước 03. Đã sửa script và thử lại thành công.
- History Server cần khoảng 10–20 giây sau khi job xong mới đánh dấu app là hoàn tất.

## Cần người dùng quyết định
1. `features_check_sample.csv` hiện vẫn là mẫu cũ (`rand(42)`). Lần chạy 03 tiếp theo sẽ **ghi đè** bằng mẫu theo hash, gồm 100 món khác. Có nên chạy 03 một lần ngay bây giờ trước khi Hậu và Ngọc bắt đầu điền cột `kiem_tra` không? Chạy 03 không đổi `dish_features` vì code nhận dạng không đổi, nên không cần chạy lại 04 và 05.

## Commit
- `722ea49`: `CLAUDE.md` và `docs/LAST_RUN.md` do chat sửa.
- `5e516b7`: History Server, `zipf_offset = 30`, mẫu theo hash, D11, PROGRESS, handoff.md.
- Commit tiếp theo: file này.
