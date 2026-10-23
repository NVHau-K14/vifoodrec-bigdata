# Lần chạy gần nhất – 24/10/2026 00:36

> File này được **ghi đè sau mỗi lần làm xong một yêu cầu** (xem quy tắc trong CLAUDE.md).
> Người dùng đọc nó ở bên chat claude.ai. Giữ đúng các mục bên dưới, tối đa khoảng 80 dòng.
> Bản này do chat claude.ai tạo, tóm tắt lại lần chạy trước của tab Code.

## Yêu cầu
Sửa lỗi "hào" ở bước 03, kẹp `quality` ở bước 04, chạy lại 03 → 04 (100%) → 05 trên cụm, sinh lại bản 10% local.

## Đã làm
- Bước 03: thêm luật CONFUSING "dầu hào" → gia vị, "su hào" → rau, rồi thêm "hào" vào nhóm hải sản. Chỉ món 511 "Canh hào thanh mát" đổi `main_protein` (đậu hũ/chay → hải sản). Không món nào đổi `is_vegetarian`. Tác dụng phụ: `method_words` giảm ở 27 món, món "Bắp bò nhúng mẻ" đổi `is_quick`.
- Bước 04: kẹp `quality` vào [−2,5; 2,5] (78 món bị kẹp). Chạy lại 100%.
- Bước 05: chạy lại trên cụm, mọi phép kiểm tra tổng đều đúng.
- Sinh lại bản 10% trong `data/hdfs_local`. Đã sao lưu rồi khôi phục 6 file xuất của bản 100% (checksum khớp).
- `features_check_sample.csv` được khôi phục về bản cũ, vì lần chạy lại chọn ra mẫu khác (`rand(42)` không ổn định).

## Số liệu chính
| Chỉ số | Giá trị |
|---|---|
| Sự kiện (100%) | 23.141.780, chạy 9,5 phút |
| Bước 05 | 106 giây |
| Bản 10% local | 2.285.167 sự kiện |
| Persona | ăn chay 100% món chay · mê hải sản 67,7% · bận rộn 92,3% |
| Món đứng đầu | "Canh hào thanh mát" 5,17% lượt nấu (trước đó 4,21%), **vẫn áp đảo** |

## Lỗi / sự cố và cách xử lý
- Kẹp `quality` không làm hết món áp đảo: món 511 vẫn đứng hạng phổ biến 1/5.499, và 81% lượt nấu của nó là phiên nấu đúng 1 món.
- Chat đã thử ở quy mô 5% với `pop_term = −0,45·log(hạng + offset)`:
  - offset 0: món đứng đầu 5,37% lượt nấu, Gini 0,741;
  - offset 10: 2,20%, Gini 0,724;
  - offset 30: 1,48%, Gini 0,711.

  Với offset 30, ALS vẫn tốt hơn baseline: RMSE 0,807 so với bias 0,834; P@10 0,022 so với popularity 0,009.

## Cần người dùng quyết định
Không. Đã chốt như sau, Code chỉ cần làm theo:
1. Bật Spark History Server **trước** khi chạy lại:
   - eventLog ghi vào `logs/spark-events/`;
   - service `spark-history` ở cổng 18080;
   - thêm `logs/` vào `.gitignore`.
2. Thêm `zipf_offset=30` vào bước 04, chạy lại 04 (100%) → 05, sinh lại bản 10% (nhớ sao lưu/khôi phục file xuất).
3. Bước 03: chọn mẫu kiểm tra tay theo `hash(food_id)`. Chỉ sửa code, không chạy lại.
4. Không đặt git config, không tạo repo GitHub. Giữ nguyên phân công 2 người trong tài liệu.
5. Ghi D11 vào DECISIONS (kèm bảng offset 0/10/30). Thêm vào "Việc còn treo": chụp ảnh UI để cuối dự án, làm cùng lúc đo hiệu năng.

## Commit
- `2a807fa`: bước 05 (qua `/handoff`), gồm cả việc xóa file docx.
- `1e741ee`: sửa "hào", kẹp quality, chạy lại 03 → 04 → 05.
- Chưa commit: chat sửa `CLAUDE.md` (thêm quy tắc LAST_RUN) và tạo file này.
