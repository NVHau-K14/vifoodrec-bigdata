---
description: Kết thúc phiên làm việc – cập nhật PROGRESS, DECISIONS, DATA_DICTIONARY rồi commit
---

Kết thúc phiên làm việc. Làm lần lượt:

1. Xem `git status` và `git diff --stat` để biết phiên này đã thay đổi những gì.
2. Cập nhật `docs/PROGRESS.md`:
   - Sửa ngày ở dòng "Cập nhật lần cuối".
   - Bảng trạng thái: đổi trạng thái các bước đã xong hoặc đang làm, ghi số liệu chính lấy từ `data/output/*_report.json` (số liệu thật, không ước lượng).
   - "Việc tiếp theo": viết cụ thể để phiên sau làm được ngay mà không cần đọc lại code.
   - "Việc còn treo": tick việc đã xong, thêm việc mới phát sinh.
   - Thêm 1–3 dòng vào "Nhật ký".
   - Lỗi môi trường mới gặp cùng cách xử lý: ghi vào mục "Lỗi môi trường đã gặp" trong `CLAUDE.md`.
3. Có quyết định thiết kế mới (chọn tham số, bỏ hoặc thêm phần nào, lý do) thì thêm một mục `Dxx` vào cuối `docs/DECISIONS.md`.
4. Có bảng hoặc cột mới, hoặc đổi đường dẫn HDFS, thì cập nhật `docs/DATA_DICTIONARY.md` và bảng Pipeline trong `CLAUDE.md`.
5. Ghi đè `docs/LAST_RUN.md` theo mẫu có sẵn trong file: giữ đúng các mục (Yêu cầu, Đã làm, Số liệu chính, Lỗi / sự cố và cách xử lý, Cần người dùng quyết định, Commit), không giới hạn độ dài, số liệu lấy từ `data/output/*_report.json`. Mọi câu hỏi cần người dùng trả lời phải nằm trong mục "Cần người dùng quyết định"; không có thì ghi "Không".
6. Commit với message tiếng Việt ngắn gọn, ví dụ `Buoc 05: phan tich hanh vi bang Spark SQL`. Không push nếu người dùng chưa yêu cầu.
7. Báo lại cho người dùng trong 3–5 dòng: phiên này xong những gì, việc tiếp theo là gì, việc nào cần người làm (chụp ảnh UI, kiểm tra tay…).

$ARGUMENTS
