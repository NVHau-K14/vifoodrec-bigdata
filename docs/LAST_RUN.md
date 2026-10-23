# Lần chạy gần nhất – 24/10/2026 02:05

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, tối đa khoảng 80 dòng.

## Yêu cầu
Chạy lại 03 trên cụm để ghi `features_check_sample.csv` theo mẫu hash. So sánh `dish_features` mới với bản trước, phải giống hệt từng giá trị. Sau đó chạy `/handoff`, và ghi vào PROGRESS rằng bước 06 làm theo kiểu thiết kế trước.

## Đã làm
- Sao lưu `dish_features` cũ: trên HDFS (`/tmp/bak/old_dish_features`) và bản xuất ra máy. Chạy 03 trên cụm thành công.
- So sánh bằng Spark `exceptAll` ở cả hai chiều. **Giống hệt**, không phải dừng:
  - HDFS: schema trùng, 5.499 / 5.499 dòng, cũ trừ mới = 0, mới trừ cũ = 0;
  - bản xuất `data/processed/dish_features.parquet`: cũ trừ mới = 0, mới trừ cũ = 0;
  - `features_report.json` không đổi một byte nào.
- `features_check_sample.csv` giờ là mẫu theo `xxhash64(food_id, 42)`, 100 món (3 món đầu: id 806, 1110, 2360). Không cần chạy lại 04 và 05.
- Đã xóa các bản sao lưu tạm trên HDFS và trên máy.
- `/handoff`:
  - PROGRESS: "Việc tiếp theo" số 1 là **bước 06 thiết kế trước**, kèm danh sách các phần bản thiết kế phải có. Tick mục chốt mẫu kiểm tra, ghi rằng nhóm có thể bắt đầu kiểm tra tay. Thêm nhật ký.
  - D11 ghi thêm kết quả chạy lại 03.
  - CLAUDE.md ghi thêm 2 lỗi môi trường nhỏ (`/tmp` trên HDFS, tiền tố `file://`).

## Số liệu chính
| Chỉ số | Giá trị |
|---|---|
| `dish_features` | 5.499 dòng, khác bản trước **0** dòng |
| Mẫu kiểm tra tay | 100 món, chọn theo hash. Chạy lại 03 vẫn ra đúng 100 món này |
| Dữ liệu hành vi (không đổi) | 23.205.143 sự kiện, món đứng đầu 1,44% lượt nấu, Gini 0,698 |

## Lỗi / sự cố và cách xử lý
- Lần đầu sao lưu lên HDFS bị lỗi vì chưa có thư mục `/tmp`. Chuỗi lệnh dừng ngay nên 03 chưa chạy. Đã tạo `/tmp/bak` rồi chạy lại. Lỗi này đã ghi vào CLAUDE.md.

## Cần người dùng quyết định
Không. Việc tiếp theo là bước 06, bắt đầu bằng bản đề xuất thiết kế ghi vào file này để chat góp ý, chưa viết code.

Việc cần người làm: Hậu và Ngọc có thể bắt đầu điền cột `kiem_tra` trong `data/output/features_check_sample.csv` (mỗi người 50 món).

## Commit
- `f3d01ec`: LAST_RUN sau lần chạy với `zipf_offset = 30`.
- Commit của phiên này: mẫu kiểm tra theo hash, PROGRESS, D11, CLAUDE.md, file này. Message: `Chot mau kiem tra tay theo hash (chay lai 03), handoff`.
