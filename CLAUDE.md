# ViFoodRec Big Data – hướng dẫn cho AI

Đồ án môn Nhập môn Big Data: **"Phân tích hành vi ăn uống và gợi ý món ăn"**.
Nhóm: Nguyễn Văn Hậu, Hứa Quách Như Ngọc (chia việc 50/50). Mục tiêu: điểm tối đa.
Dữ liệu: ViFoodRec, gồm món ăn thật (Cooky + Món Ngon Mỗi Ngày) và hành vi người dùng **mô phỏng**.

## Bắt đầu mỗi phiên
1. Đọc `docs/PROGRESS.md`: trạng thái, việc tiếp theo, việc còn treo. **Không đọc lại toàn bộ dự án.**
   Đọc thêm `docs/LAST_RUN.md` để biết lần chạy gần nhất và các câu hỏi đang chờ người dùng.
2. Kiểm tra cụm khi cần chạy job: `docker compose -f docker/docker-compose.yml ps` (đủ 10 container),
   `docker exec namenode hdfs dfs -ls -R /data | head`.
3. Chỉ mở khi cần: `docs/DECISIONS.md` (vì sao làm vậy), `docs/DATA_DICTIONARY.md` (cột của các bảng),
   `docs/plan/ke_hoach_chi_tiet.md` (phạm vi các bước còn lại), `docs/plan/yeu_cau_giang_vien.md` (rubric).

## Hạ tầng (Docker Desktop + WSL2, Windows 11, RAM 24GB)
- HDFS: `namenode` (UI http://localhost:9870, RPC `hdfs://namenode:8020`), `datanode1`, `datanode2` (replication 2).
- Spark 4.2.0 Standalone: `spark-master` (UI :8080), `spark-worker-1/2` (mỗi worker 2 core, 3GB).
- `jupyter` (http://localhost:8888, token `bigdata`) là driver; Spark UI của job đang chạy ở :4040.
- `spark-history` (http://localhost:18080): xem lại các job đã chạy xong. `get_spark()` ghi event log vào `logs/spark-events/` (đã có trong `.gitignore`).
- `mongodb` (:27017, admin/admin123), database `vifood` (`vifood_local` khi chạy `--local`).
- `mongo-express` (http://localhost:8090, tài khoản trong `.env`). Cổng 8081 trên máy là UI của `spark-worker-1`. FastAPI và web chưa có trong compose.
- Thư mục dự án được mount vào `/home/jovyan/work` ở jupyter, master, worker và namenode.
- Dữ liệu HDFS nằm trong Docker volume nên vẫn còn sau khi tắt máy.

## Pipeline
| Bước | File | Đọc | Ghi (HDFS) | Report |
|---|---|---|---|---|
| 01 Nạp | `scripts/01_ingest.sh` | `data/raw/*.csv` | `/data/raw` | – |
| 02 Làm sạch | `src/02_clean.py` | `/data/raw` | `/data/curated/{foods,ratings_original}` | `clean_report.json` |
| 03 Đặc trưng món | `src/03_features.py` | `/data/curated/foods` | `/data/features/dish_features` | `features_report.json` |
| 04 Sinh hành vi | `src/04_simulate.py` | `dish_features` | `/data/events/{events,users,users_truth}` | `simulate_report.json` |
| 05 Phân tích hành vi | `src/05_analysis.py` | `/data/events`, `dish_features`, `foods` | `/data/results/analysis/*` (14 bảng) | `analysis_report.json`, `analysis/*.json` |
| 06 Mô hình | `src/06a_split.py` … `06g_control.py`, dùng chung `src/rec_common.py` | `/data/events`, `dish_features`, `foods`, `ratings_original` | `/data/results/models/*`, `/data/models/*` | `model_*_report.json`, `models_metrics.json` |
| 07 Xuất MongoDB | `src/07_export_mongo.py` | kết quả 02–06 trên HDFS, `data/output/*report*.json` | MongoDB `vifood` (26 collection) | `export_report.json` |
| 08 API + dashboard | `api/`, `web/` (trống) | MongoDB | | |

Bản sao nhỏ để xem trên máy nằm ở `data/processed/`. Report và mẫu kiểm tra nằm ở `data/output/`.

## Cách chạy
```bash
# Khởi động cụm (PowerShell, trong thư mục docker/)
docker compose up -d
# Bước 01 (chỉ khi HDFS trống)
docker exec namenode bash /home/jovyan/work/scripts/01_ingest.sh
# Chạy một bước trên cụm (từ máy host). Cần -e PYTHONPATH, xem "Lỗi môi trường đã gặp"
docker exec -w /home/jovyan/work -e PYTHONPATH=/usr/local/spark/python/lib/py4j-0.10.9.9-src.zip:/usr/local/spark/python jupyter python src/04_simulate.py --scale 0.01
```
Script nào cũng có `--local` (Spark local, ghi vào `data/hdfs_local/`). Bước sinh dữ liệu và các bước nặng có thêm `--scale`.

## Quy ước code
- Mọi script dùng `common.py`: `get_spark()`, `Paths`, `export_single()`. Không tự viết lại đường dẫn HDFS.
- Đặt tên `src/NN_ten.py`, đầu file có docstring ghi Đầu vào, Đầu ra, cách chạy (theo mẫu 02–04).
- Chú thích trong code viết **không dấu**. Giá trị dữ liệu thì giữ tiếng Việt có dấu (vd `"Món chay"`, `"tối"`).
- Ưu tiên hàm Spark có sẵn, chỉ dùng UDF Python khi bắt buộc. Seed cố định để chạy lại ra cùng kết quả.
- Mỗi bước ghi `data/output/<buoc>_report.json` chứa số liệu kiểm tra, để dùng lại cho báo cáo.
- Dữ liệu lớn (events) chỉ nằm trên HDFS. Ra máy chỉ xuất bảng nhỏ hoặc file mẫu.

## Giao diện (`web/`) và endpoint cho dashboard
- **Mọi việc trong `web/`** (HTML, CSS, JS, biểu đồ) và việc thiết kế endpoint trả dữ liệu cho dashboard
  **phải theo skill `vifood-dashboard`** (`.claude/skills/vifood-dashboard/SKILL.md`). Đọc skill này trước khi sửa.
- Skill `frontend-design` (`.claude/skills/frontend-design/`, lấy từ `anthropics/skills`) chỉ dùng để tham khảo
  thêm. **Khi hai skill khác nhau thì `vifood-dashboard` thắng** (token màu, font, bố cục, thành phần đã chốt).

## Quy tắc làm việc
- **Không** sửa `data/raw/`. **Không** chạy `docker compose down -v` hay xóa volume, vì sẽ mất toàn bộ HDFS.
- Chạy thử `--local` hoặc `--scale 0.01` trước, rồi mới chạy đủ. Sau khi chạy, đọc report để kiểm tra.
- Tắt kernel các notebook trước khi chạy job. Cụm chỉ có 4 core, notebook đang giữ executor thì job phải xếp hàng chờ.
- Dữ liệu hành vi là **mô phỏng**, luôn ghi rõ điều này. Không rút ra kết luận từ dinh dưỡng hay `cooking_time` gốc (số ngẫu nhiên).
- Có quyết định thiết kế mới thì thêm vào `docs/DECISIONS.md`. Thêm hoặc đổi bảng thì cập nhật `docs/DATA_DICTIONARY.md`.
- Cuối phiên chạy `/handoff`: cập nhật `docs/PROGRESS.md` và commit.
- **Mỗi lần làm xong một yêu cầu**, ghi đè `docs/LAST_RUN.md` theo mẫu có sẵn trong file đó (không giới hạn độ dài, số liệu lấy từ report JSON, không ước lượng). Người dùng đọc file này ở bên chat claude.ai thay vì chụp màn hình, nên mọi câu hỏi cần người dùng trả lời phải nằm trong mục "Cần người dùng quyết định". `/handoff` cũng phải cập nhật file này.
- Trả lời người dùng bằng tiếng Việt. Tài liệu trong `docs/` viết tiếng Việt có dấu.

## Lỗi môi trường đã gặp
- `Safe mode is ON` trong khoảng 30 giây đầu sau khi khởi động: đợi rồi chạy lại.
- PowerShell tự mở rộng dấu `*`: bọc lệnh `hdfs` trong `bash -c "..."`.
- Container trùng tên với dự án cũ: `docker rm -f <tên>` (dự án cũ đã hủy, không dùng lại).
- `ModuleNotFoundError: No module named 'pyspark'` khi chạy `docker exec ... python`: PYTHONPATH chỉ được đặt cho
  tiến trình do Jupyter khởi động (terminal Jupyter thì có). Thêm `-e PYTHONPATH=...` như lệnh mẫu ở trên.
- Git Bash đổi `/home/jovyan/work` thành đường dẫn Windows (`Cwd must be an absolute path`):
  đặt `MSYS_NO_PATHCONV=1` trước lệnh `docker exec`, hoặc chạy từ PowerShell.
- `hdfs dfs -cp ... /tmp/x` báo `No such file or directory`: HDFS chưa có `/tmp`. Chạy `hdfs dfs -mkdir -p /tmp/bak` trước.
- Script thử chạy trong container đọc file trên máy phải ghi `file:///home/jovyan/work/...`. Không có `file://` thì Spark hiểu là đường dẫn HDFS.
- Không chạy cùng lúc một job `--local` và một job trên cụm. Cả hai driver đều nằm trong container `jupyter` (local 3GB, cụm 2GB), mà container chỉ có 4GB. Chạy lần lượt.
- Lọc log bằng `grep "^..."` có thể trượt, vì dòng in ra bị dính sau thanh tiến trình của Spark (`\r`). Dùng `grep -ao "\[06\][^[]*"`.
